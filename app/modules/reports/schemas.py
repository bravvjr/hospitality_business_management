"""Reports API schemas (Phase 2a)."""
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GroupBy = Literal["day", "week", "month"]


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
