"""POS / order domain models (ADR-006).

One order/sale domain shared by POS and future online store. Money is integer
minor units + ISO-4217 currency. Completing a sale records a payment and
deducts inventory via append-only stock_movements.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # open | completed | voided
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # pos | online (future)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="pos")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cashier_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Order id={self.id} status={self.status!r}>"


class OrderItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    # Immutable snapshots at add/update time.
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    to_base_factor_snapshot: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OrderItem id={self.id} product_id={self.product_id}>"


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # cash | mpesa
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    provider_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    order: Mapped["Order"] = relationship(back_populates="payments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment id={self.id} method={self.method!r} status={self.status!r}>"
