"""Tenant model — the first-class multi-tenancy boundary (ADR-002 / ADR-012).

Self-referential `parent_tenant_id` supports the tenant -> sub-tenant hierarchy.
"""
import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    sub_tenants: Mapped[list["Tenant"]] = relationship(
        back_populates="parent",
    )
    parent: Mapped["Tenant | None"] = relationship(
        back_populates="sub_tenants",
        remote_side="Tenant.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return f"<Tenant id={self.id} name={self.name!r}>"
