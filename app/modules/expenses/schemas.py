"""Pydantic schemas for the expenses module."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ExpenseCategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ExpenseCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ExpenseCreateRequest(BaseModel):
    category_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    description: str = Field(min_length=1, max_length=500)
    expense_date: date
    note: str | None = Field(default=None, max_length=500)


class ExpenseUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    amount_minor: int | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    expense_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    category: ExpenseCategoryRead
    amount_minor: int
    currency: str
    description: str
    expense_date: date
    recorded_by_user_id: uuid.UUID | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class ExpenseSummaryRead(BaseModel):
    currency: str
    total_minor: int
    expense_count: int
    from_date: date
    to_date: date
