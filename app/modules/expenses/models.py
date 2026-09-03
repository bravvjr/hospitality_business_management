"""Expense models (Phase 1 finance MVP).

Money is stored as integer minor units + ISO-4217 currency (ADR-004).
"""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin


class ExpenseCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_expense_categories_tenant_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExpenseCategory id={self.id} name={self.name!r}>"


class Expense(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category: Mapped["ExpenseCategory"] = relationship(back_populates="expenses")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Expense id={self.id} amount_minor={self.amount_minor}>"
