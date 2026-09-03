"""Tenant model — the first-class multi-tenancy boundary (ADR-002 / ADR-012).

Self-referential `parent_tenant_id` supports the tenant -> sub-tenant hierarchy.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    sub_tenants: Mapped[list["Tenant"]] = relationship(back_populates="parent")
    parent: Mapped["Tenant | None"] = relationship(
        back_populates="sub_tenants", remote_side="Tenant.id"
    )

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return f"<Tenant id={self.id} name={self.name!r}>"


class TenantClosure(Base):
    """Closure table for tenant hierarchy (ancestor/descendant pairs)."""

    __tablename__ = "tenant_closure"

    ancestor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    descendant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    depth: Mapped[int] = mapped_column(nullable=False)


class TenantEntitlement(Base):
    """Enabled platform modules for a tenant (ADR-012 subproducts)."""

    __tablename__ = "tenant_entitlements"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    module_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
