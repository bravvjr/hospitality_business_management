"""Pydantic schemas for the tenant module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    name: str
    base_currency: str = "KES"
    parent_tenant_id: uuid.UUID | None = None


class TenantCreate(TenantBase):
    pass


class SubTenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_currency: str = Field(default="KES", min_length=3, max_length=3)


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
