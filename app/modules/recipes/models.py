"""Recipe / BOM models (ADR-005 Phase 2).

A recipe links a sellable product (meal) to ingredient lines with quantities
in recipe units. Automated consumption on POS sale is wired in a follow-up slice.
"""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.modules.inventory.models import Product, Unit


class Recipe(UUIDMixin, TimestampMixin, Base):
    """Bill of materials for a sellable product (meal / menu item)."""

    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", name="uq_recipes_tenant_product"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Quantity of the meal this recipe produces (usually 1 serving).
    yields_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 6), nullable=False, default=Decimal("1")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    items: Mapped[list["RecipeItem"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeItem.sort_order",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recipe id={self.id} product_id={self.product_id}>"


class RecipeItem(UUIDMixin, TimestampMixin, Base):
    """One ingredient line on a recipe."""

    __tablename__ = "recipe_items"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id",
            "ingredient_product_id",
            name="uq_recipe_items_recipe_ingredient",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped["Recipe"] = relationship(back_populates="items")
    ingredient_product: Mapped["Product"] = relationship(
        "Product", foreign_keys=[ingredient_product_id]
    )
    unit: Mapped["Unit"] = relationship("Unit")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RecipeItem recipe_id={self.recipe_id} "
            f"ingredient_product_id={self.ingredient_product_id}>"
        )
