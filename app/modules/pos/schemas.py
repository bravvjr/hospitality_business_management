"""Pydantic schemas for the POS / order module."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreateRequest(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_id: uuid.UUID | None = None


class OrderItemUpdateRequest(BaseModel):
    quantity: Decimal = Field(gt=0)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    unit_id: uuid.UUID
    quantity: Decimal
    unit_price_minor: int
    line_total_minor: int
    currency: str


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: str
    amount_minor: int
    currency: str
    status: str
    provider_ref: str | None
    paid_at: datetime | None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    status: str
    channel: str
    currency: str
    subtotal_minor: int
    total_minor: int
    cashier_user_id: uuid.UUID | None
    completed_at: datetime | None
    note: str | None
    items: list[OrderItemRead]
    payments: list[PaymentRead]
    created_at: datetime
    updated_at: datetime
    # Set on cash complete when amount_tendered_minor > total_minor.
    change_minor: int | None = None


class OrderCreateRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CompleteSaleRequest(BaseModel):
    payment_method: str = Field(pattern="^(cash|mpesa)$")
    # For cash: amount tendered in minor units (must be >= total). Defaults to total.
    amount_tendered_minor: int | None = Field(default=None, ge=0)
