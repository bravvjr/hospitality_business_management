"""POS / sales business logic (ADR-006)."""
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.service import InventoryError, InventoryService
from app.modules.pos.models import Order, OrderItem, Payment
from app.modules.pos.repository import PosRepository
from app.modules.pos.schemas import (
    CompleteSaleRequest,
    OrderCreateRequest,
    OrderItemCreateRequest,
    OrderItemUpdateRequest,
    OrderRead,
)
from app.modules.tenant.repository import TenantRepository


class PosError(Exception):
    """Business rule violation for POS operations."""


class PosNotFoundError(PosError):
    """Requested order/item was not found in the current tenant."""


STATUS_OPEN = "open"
STATUS_COMPLETED = "completed"
METHOD_CASH = "cash"
METHOD_MPESA = "mpesa"


def _line_total_minor(*, quantity: Decimal, unit_price_minor: int) -> int:
    # quantity may be fractional; round half-up to nearest minor unit.
    total = (quantity * Decimal(unit_price_minor)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(total)


class PosService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PosRepository(session)
        self._inventory = InventoryService(session)
        self._tenants = TenantRepository(session)

    async def create_order(
        self,
        *,
        tenant_id: uuid.UUID,
        cashier_user_id: uuid.UUID,
        payload: OrderCreateRequest,
    ) -> OrderRead:
        currency = payload.currency
        if currency is None:
            tenant = await self._tenants.get(tenant_id)
            if tenant is None:
                raise PosError("Tenant is unavailable")
            currency = tenant.base_currency
        order = Order(
            tenant_id=tenant_id,
            status=STATUS_OPEN,
            channel="pos",
            currency=currency.upper(),
            cashier_user_id=cashier_user_id,
            note=payload.note,
        )
        await self._repo.add(order)
        await self._session.commit()
        return await self.get_order(tenant_id=tenant_id, order_id=order.id)

    async def get_order(self, *, tenant_id: uuid.UUID, order_id: uuid.UUID) -> OrderRead:
        order = await self._repo.get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise PosNotFoundError("Order not found")
        return OrderRead.model_validate(order)

    async def list_orders(
        self,
        *,
        tenant_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OrderRead], int]:
        orders, total = await self._repo.list_orders(
            tenant_id=tenant_id, status=status, limit=limit, offset=offset
        )
        return [OrderRead.model_validate(o) for o in orders], total

    async def add_item(
        self,
        *,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        payload: OrderItemCreateRequest,
    ) -> OrderRead:
        order = await self._require_open_order(tenant_id=tenant_id, order_id=order_id)
        product = await self._inventory.get_product(
            tenant_id=tenant_id, product_id=payload.product_id
        )
        if product.status != "active":
            raise PosError("Product is not active")
        if product.unit_price_minor is None or product.currency is None:
            raise PosError("Product has no sell price configured")
        if product.currency.upper() != order.currency.upper():
            raise PosError("Product currency does not match order currency")

        unit_id = payload.unit_id or product.base_unit_id
        product_unit = await self._inventory.get_product_unit(
            tenant_id=tenant_id, product_id=product.id, unit_id=unit_id
        )
        if product_unit is None:
            raise PosError("Unit is not configured for this product")

        # Merge into existing line for same product+unit.
        existing = next(
            (
                i
                for i in order.items
                if i.product_id == product.id and i.unit_id == unit_id
            ),
            None,
        )
        if existing is not None:
            existing.quantity = Decimal(existing.quantity) + payload.quantity
            existing.line_total_minor = _line_total_minor(
                quantity=Decimal(existing.quantity),
                unit_price_minor=existing.unit_price_minor,
            )
        else:
            item = OrderItem(
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_id=unit_id,
                quantity=payload.quantity,
                to_base_factor_snapshot=product_unit.to_base_factor,
                unit_price_minor=product.unit_price_minor,
                line_total_minor=_line_total_minor(
                    quantity=payload.quantity,
                    unit_price_minor=product.unit_price_minor,
                ),
                currency=order.currency,
            )
            order.items.append(item)

        self._recompute_totals(order)
        await self._session.commit()
        return await self.get_order(tenant_id=tenant_id, order_id=order.id)

    async def update_item(
        self,
        *,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: OrderItemUpdateRequest,
    ) -> OrderRead:
        order = await self._require_open_order(tenant_id=tenant_id, order_id=order_id)
        item = await self._repo.get_item(
            tenant_id=tenant_id, order_id=order_id, item_id=item_id
        )
        if item is None:
            raise PosNotFoundError("Order item not found")
        item.quantity = payload.quantity
        item.line_total_minor = _line_total_minor(
            quantity=payload.quantity, unit_price_minor=item.unit_price_minor
        )
        # Refresh order.items relationship for totals.
        order = await self._require_open_order(tenant_id=tenant_id, order_id=order_id)
        self._recompute_totals(order)
        await self._session.commit()
        return await self.get_order(tenant_id=tenant_id, order_id=order.id)

    async def remove_item(
        self,
        *,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> OrderRead:
        order = await self._require_open_order(tenant_id=tenant_id, order_id=order_id)
        item = next((i for i in order.items if i.id == item_id), None)
        if item is None:
            raise PosNotFoundError("Order item not found")
        order.items.remove(item)
        self._recompute_totals(order)
        await self._session.commit()
        return await self.get_order(tenant_id=tenant_id, order_id=order.id)

    async def complete_sale(
        self,
        *,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        payload: CompleteSaleRequest,
    ) -> OrderRead:
        order = await self._require_open_order(tenant_id=tenant_id, order_id=order_id)
        if not order.items:
            raise PosError("Cannot complete an empty order")

        if payload.payment_method == METHOD_MPESA:
            # Daraja STK + async callback is the source of truth (ADR-006).
            # Cash path is Phase 1; M-Pesa initiation lands with the payments module.
            raise PosError(
                "M-Pesa STK Push is not enabled yet; complete the sale with cash"
            )

        tendered = payload.amount_tendered_minor
        if tendered is None:
            tendered = order.total_minor
        if tendered < order.total_minor:
            raise PosError("Amount tendered is less than order total")

        # Deduct inventory for each line (same DB transaction).
        try:
            for item in order.items:
                await self._inventory.record_sale_deduction(
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    product_id=item.product_id,
                    quantity=Decimal(item.quantity),
                    unit_id=item.unit_id,
                    source_document_id=str(order.id),
                    idempotency_key=f"sale:{order.id}:{item.id}",
                    commit=False,
                )
        except InventoryError as exc:
            await self._session.rollback()
            raise PosError(str(exc)) from exc

        now = datetime.now(UTC)
        payment = Payment(
            tenant_id=tenant_id,
            order_id=order.id,
            method=METHOD_CASH,
            amount_minor=tendered,
            currency=order.currency,
            status="completed",
            paid_at=now,
        )
        order.payments.append(payment)
        order.status = STATUS_COMPLETED
        order.completed_at = now
        order.cashier_user_id = actor_user_id
        await self._session.commit()
        return await self.get_order(tenant_id=tenant_id, order_id=order.id)

    async def _require_open_order(
        self, *, tenant_id: uuid.UUID, order_id: uuid.UUID
    ) -> Order:
        order = await self._repo.get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise PosNotFoundError("Order not found")
        if order.status != STATUS_OPEN:
            raise PosError("Order is not open")
        return order

    @staticmethod
    def _recompute_totals(order: Order) -> None:
        subtotal = sum(int(i.line_total_minor) for i in order.items)
        order.subtotal_minor = subtotal
        order.total_minor = subtotal
