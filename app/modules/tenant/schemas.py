"""Pydantic schemas for the tenant module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    name: str
    base_currency: str = "KES"
    parent_tenant_id: uuid.UUID | None = None


class TenantCreate(TenantBase):
    pass


class TenantRead(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
