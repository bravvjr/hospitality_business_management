"""Pydantic schemas for dashboard responses."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DashboardSummaryRead(BaseModel):
    date: date
    currency: str
    sales_total_minor: int
    sales_count: int
    expenses_total_minor: int
    expenses_count: int
    net_position_minor: int
    low_stock_count: int


class DashboardRecentSaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    total_minor: int
    currency: str
    completed_at: datetime
    item_count: int


class DashboardRecentExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_minor: int
    currency: str
    description: str
    expense_date: date
    category_name: str


class DashboardRecentRead(BaseModel):
    sales: list[DashboardRecentSaleRead]
    expenses: list[DashboardRecentExpenseRead]


class DashboardLowStockRead(BaseModel):
    product_id: uuid.UUID
    product_name: str
    quantity_base: str
    reorder_level_base: str | None
    unit_symbol: str
