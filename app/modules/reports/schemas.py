"""Reports API schemas (Phase 2a/2b)."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GroupBy = Literal["day", "week", "month"]
SalesSortBy = Literal["revenue", "quantity"]


class SalesBucketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    total_minor: int
    order_count: int


class SalesSummaryRead(BaseModel):
    currency: str
    from_date: date
    to_date: date
    total_minor: int
    order_count: int
    average_ticket_minor: int
    buckets: list[SalesBucketRead] = Field(default_factory=list)


class CategoryExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: uuid.UUID
    category_name: str
    total_minor: int
    expense_count: int


class ExpensesByCategoryRead(BaseModel):
    currency: str
    from_date: date
    to_date: date
    categories: list[CategoryExpenseRead]


class PnlRead(BaseModel):
    currency: str
    from_date: date
    to_date: date
    revenue_minor: int
    expense_minor: int
    net_minor: int
    order_count: int
    expense_count: int


class ProductSalesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    total_minor: int
    quantity: Decimal
    line_count: int


class SalesByProductRead(BaseModel):
    currency: str
    from_date: date
    to_date: date
    products: list[ProductSalesRead]


class PaymentMethodSalesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: str
    total_minor: int
    payment_count: int


class SalesByPaymentMethodRead(BaseModel):
    currency: str
    from_date: date
    to_date: date
    methods: list[PaymentMethodSalesRead]


class MovementTypeSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movement_type: str
    movement_count: int
    total_quantity_delta_base: Decimal


class InventoryMovementSummaryRead(BaseModel):
    from_date: date
    to_date: date
    movement_type: str | None = None
    types: list[MovementTypeSummaryRead]
