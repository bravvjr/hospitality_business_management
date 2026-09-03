"""Data access for expense entities."""
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.expenses.models import Expense, ExpenseCategory


class ExpenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_categories(
        self, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[ExpenseCategory], int]:
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ExpenseCategory)
                    .where(ExpenseCategory.tenant_id == tenant_id)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            select(ExpenseCategory)
            .where(ExpenseCategory.tenant_id == tenant_id)
            .order_by(ExpenseCategory.name.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def get_category(
        self, *, tenant_id: uuid.UUID, category_id: uuid.UUID
    ) -> ExpenseCategory | None:
        result = await self._session.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.tenant_id == tenant_id,
                ExpenseCategory.id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_category_by_name(
        self, *, tenant_id: uuid.UUID, name: str
    ) -> ExpenseCategory | None:
        result = await self._session.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.tenant_id == tenant_id,
                ExpenseCategory.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_expenses(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int,
        offset: int,
        category_id: uuid.UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[list[Expense], int]:
        filters = [Expense.tenant_id == tenant_id]
        if category_id is not None:
            filters.append(Expense.category_id == category_id)
        if from_date is not None:
            filters.append(Expense.expense_date >= from_date)
        if to_date is not None:
            filters.append(Expense.expense_date <= to_date)

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Expense).where(*filters)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            select(Expense)
            .options(selectinload(Expense.category))
            .where(*filters)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def get_expense(
        self, *, tenant_id: uuid.UUID, expense_id: uuid.UUID
    ) -> Expense | None:
        result = await self._session.execute(
            select(Expense)
            .options(selectinload(Expense.category))
            .where(Expense.tenant_id == tenant_id, Expense.id == expense_id)
        )
        return result.scalar_one_or_none()

    async def summarize_expenses(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> tuple[int, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Expense.amount_minor), 0),
                func.count(),
            ).where(
                Expense.tenant_id == tenant_id,
                Expense.currency == currency,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
        )
        total_minor, count = result.one()
        return int(total_minor), int(count)

    async def add(self, entity: Expense | ExpenseCategory) -> None:
        self._session.add(entity)

    async def flush(self) -> None:
        await self._session.flush()
