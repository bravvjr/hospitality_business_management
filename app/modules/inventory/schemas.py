"""Pydantic schemas for the inventory module."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    symbol: str


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_unit_id: uuid.UUID
    sku: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    reorder_level_base: Decimal | None = Field(default=None, ge=0)
    unit_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    reorder_level_base: Decimal | None = Field(default=None, ge=0)
    unit_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    sku: str | None
    category: str | None
    base_unit: UnitRead
    reorder_level_base: Decimal | None
    unit_price_minor: int | None
    currency: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProductUnitCreateRequest(BaseModel):
    unit_id: uuid.UUID
    to_base_factor: Decimal = Field(gt=0)
    is_stock: bool = False
    is_purchase: bool = False
    is_recipe: bool = False
    is_sales: bool = False


class ProductUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    unit: UnitRead
    to_base_factor: Decimal
    is_stock: bool
    is_purchase: bool
    is_recipe: bool
    is_sales: bool


class StockMovementCreateRequest(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=50)
    note: str | None = Field(default=None, max_length=2000)
    source_document_type: str | None = Field(default=None, max_length=50)
    source_document_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockAdjustmentRequest(BaseModel):
    """Adjustment quantity is signed: positive increases stock, negative decreases."""

    product_id: uuid.UUID
    quantity: Decimal
    unit_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=50)
    note: str | None = Field(default=None, max_length=2000)
    source_document_type: str | None = Field(default=None, max_length=50)
    source_document_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: str
    quantity_delta_base: Decimal
    entered_quantity: Decimal
    entered_unit: UnitRead
    to_base_factor_snapshot: Decimal
    reason: str
    note: str | None
    source_document_type: str | None
    source_document_id: str | None
    actor_user_id: uuid.UUID | None
    idempotency_key: str | None
    created_at: datetime


class StockLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    base_unit: UnitRead
    quantity_base: Decimal
    reorder_level_base: Decimal | None
    is_low_stock: bool
