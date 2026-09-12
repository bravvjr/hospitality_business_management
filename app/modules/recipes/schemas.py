"""Pydantic schemas for the recipes module."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventory.schemas import ProductRead, UnitRead


class RecipeItemCreateRequest(BaseModel):
    ingredient_product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_id: uuid.UUID
    sort_order: int = Field(default=0, ge=0)


class RecipeItemUpdateRequest(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_id: uuid.UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)


class RecipeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_product_id: uuid.UUID
    ingredient_product: ProductRead
    quantity: Decimal
    unit: UnitRead
    sort_order: int
    created_at: datetime
    updated_at: datetime


class RecipeCreateRequest(BaseModel):
    product_id: uuid.UUID
    yields_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[RecipeItemCreateRequest] = Field(default_factory=list)


class RecipeUpdateRequest(BaseModel):
    yields_quantity: Decimal | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    notes: str | None = Field(default=None, max_length=2000)


class RecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    product_id: uuid.UUID
    product: ProductRead
    yields_quantity: Decimal
    status: str
    notes: str | None
    items: list[RecipeItemRead]
    created_at: datetime
    updated_at: datetime


class RecipeCostLineRead(BaseModel):
    recipe_item_id: uuid.UUID
    ingredient_product_id: uuid.UUID
    ingredient_name: str
    quantity: Decimal
    unit: UnitRead
    unit_cost_minor: int | None
    line_cost_minor: int | None
    currency: str | None


class RecipeCostRead(BaseModel):
    recipe_id: uuid.UUID
    product_id: uuid.UUID
    currency: str
    yields_quantity: Decimal
    total_cost_minor: int | None
    cost_per_yield_minor: int | None
    sell_price_minor: int | None
    margin_minor: int | None
    margin_percent: Decimal | None
    is_complete: bool
    lines: list[RecipeCostLineRead]


class RecipeSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    product_id: uuid.UUID
    product: ProductRead
    yields_quantity: Decimal
    status: str
    item_count: int
    created_at: datetime
    updated_at: datetime
