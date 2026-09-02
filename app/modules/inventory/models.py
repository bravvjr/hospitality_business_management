"""Inventory models (ADR-005).

Global units dictionary + tenant-scoped products, product UoM conversions,
append-only stock_movements ledger, and derived stock_levels.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin


class Unit(UUIDMixin, TimestampMixin, Base):
    """Global unit of measure (kg, g, L, piece, …). Not tenant-scoped."""

    __tablename__ = "units"

    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Unit key={self.key!r}>"


class Product(UUIDMixin, TimestampMixin, Base):
    """Tenant-scoped inventory item / sellable product."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    # Reorder threshold in base units (NULL = no low-stock tracking).
    reorder_level_base: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    # Sell price in minor units (e.g. cents); NULL = not for sale / unset.
    unit_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    base_unit: Mapped["Unit"] = relationship()
    product_units: Mapped[list["ProductUnit"]] = relationship(back_populates="product")
    stock_level: Mapped["StockLevel | None"] = relationship(back_populates="product")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id} name={self.name!r}>"


class ProductUnit(UUIDMixin, TimestampMixin, Base):
    """Per-product conversion from a unit into the product's base unit."""

    __tablename__ = "product_units"
    __table_args__ = (
        UniqueConstraint("product_id", "unit_id", name="uq_product_units_product_unit"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    # Multiply entered quantity by this factor to get base-unit quantity.
    to_base_factor: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    is_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_recipe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sales: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product: Mapped["Product"] = relationship(back_populates="product_units")
    unit: Mapped["Unit"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProductUnit product_id={self.product_id} unit_id={self.unit_id}>"


class StockMovement(UUIDMixin, Base):
    """Append-only inventory ledger row (ADR-005). Never update or delete."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_stock_movements_tenant_idempotency",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # receipt | adjustment | usage | sale | transfer | reversal
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Signed quantity in the product's base unit after conversion.
    quantity_delta_base: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    # Immutable UoM snapshot of what the actor entered.
    entered_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    entered_unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    to_base_factor_snapshot: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship()
    entered_unit: Mapped["Unit"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StockMovement id={self.id} type={self.movement_type!r} "
            f"delta={self.quantity_delta_base}>"
        )


class StockLevel(UUIDMixin, TimestampMixin, Base):
    """Derived on-hand quantity per product (base units)."""

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", name="uq_stock_levels_tenant_product"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity_base: Mapped[Decimal] = mapped_column(
        Numeric(24, 6), nullable=False, default=Decimal("0")
    )

    product: Mapped["Product"] = relationship(back_populates="stock_level")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockLevel product_id={self.product_id} qty={self.quantity_base}>"
