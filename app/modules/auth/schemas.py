"""Pydantic schemas for the auth module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tenant_name: str = Field(min_length=1, max_length=200)
    base_currency: str = Field(default="KES", min_length=3, max_length=3)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    tenant_id: uuid.UUID | None = None


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    status: str
    created_at: datetime


class TenantSummary(BaseModel):
    id: uuid.UUID
    name: str
    base_currency: str


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    role: RoleRead


class SessionRead(BaseModel):
    user: UserRead
    tenant: TenantSummary
    membership: MembershipRead


class MessageResponse(BaseModel):
    message: str


class StaffCreateRequest(BaseModel):
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_key: str = Field(min_length=1, max_length=50)


class StaffUpdateRequest(BaseModel):
    role_key: str = Field(min_length=1, max_length=50)


class StaffStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


class StaffMemberRead(BaseModel):
    membership: MembershipRead
    user: UserRead
