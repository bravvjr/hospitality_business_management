"""Expense business logic (Phase 1 finance MVP)."""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.repository import ExpenseRepository
from app.modules.expenses.schemas import (
    ExpenseCategoryCreateRequest,
    ExpenseCategoryUpdateRequest,
    ExpenseCreateRequest,
    ExpenseSummaryRead,
    ExpenseUpdateRequest,
)


class ExpenseError(Exception):
    """Business rule violation for expense operations."""


class ExpenseNotFoundError(ExpenseError):
    """Requested expense entity was not found in the current tenant."""


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ExpenseRepository(session)

    async def list_categories(
        self, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[ExpenseCategory], int]:
        return await self._repo.list_categories(tenant_id=tenant_id, limit=limit, offset=offset)

    async def create_category(
        self, *, tenant_id: uuid.UUID, payload: ExpenseCategoryCreateRequest
    ) -> ExpenseCategory:
        name = payload.name.strip()
        if not name:
            raise ExpenseError("Category name is required")
        existing = await self._repo.get_category_by_name(tenant_id=tenant_id, name=name)
        if existing is not None:
            raise ExpenseError("Category name already exists")

        category = ExpenseCategory(tenant_id=tenant_id, name=name)
        await self._repo.add(category)
        await self._session.commit()
        await self._session.refresh(category)
        return category

    async def update_category(
        self,
        *,
        tenant_id: uuid.UUID,
        category_id: uuid.UUID,
        payload: ExpenseCategoryUpdateRequest,
    ) -> ExpenseCategory:
        category = await self._repo.get_category(tenant_id=tenant_id, category_id=category_id)
        if category is None:
            raise ExpenseNotFoundError("Category not found")

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ExpenseError("Category name is required")
            existing = await self._repo.get_category_by_name(tenant_id=tenant_id, name=name)
            if existing is not None and existing.id != category.id:
                raise ExpenseError("Category name already exists")
            category.name = name

        if payload.status is not None:
            category.status = payload.status

        await self._session.commit()
        await self._session.refresh(category)
        return category

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
        return await self._repo.list_expenses(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            category_id=category_id,
            from_date=from_date,
            to_date=to_date,
        )

    async def get_expense(self, *, tenant_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
        expense = await self._repo.get_expense(tenant_id=tenant_id, expense_id=expense_id)
        if expense is None:
            raise ExpenseNotFoundError("Expense not found")
        return expense

    async def create_expense(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        payload: ExpenseCreateRequest,
    ) -> Expense:
        category = await self._repo.get_category(
            tenant_id=tenant_id, category_id=payload.category_id
        )
        if category is None:
            raise ExpenseNotFoundError("Category not found")
        if category.status != "active":
            raise ExpenseError("Category is not active")

        expense = Expense(
            tenant_id=tenant_id,
            category_id=payload.category_id,
            amount_minor=payload.amount_minor,
            currency=payload.currency.upper(),
            description=payload.description.strip(),
            expense_date=payload.expense_date,
            recorded_by_user_id=actor_user_id,
            note=payload.note,
        )
        await self._repo.add(expense)
        await self._session.commit()
        return await self.get_expense(tenant_id=tenant_id, expense_id=expense.id)

    async def update_expense(
        self,
        *,
        tenant_id: uuid.UUID,
        expense_id: uuid.UUID,
        payload: ExpenseUpdateRequest,
    ) -> Expense:
        expense = await self.get_expense(tenant_id=tenant_id, expense_id=expense_id)

        if payload.category_id is not None:
            category = await self._repo.get_category(
                tenant_id=tenant_id, category_id=payload.category_id
            )
            if category is None:
                raise ExpenseNotFoundError("Category not found")
            if category.status != "active":
                raise ExpenseError("Category is not active")
            expense.category_id = payload.category_id

        if payload.amount_minor is not None:
            expense.amount_minor = payload.amount_minor
        if payload.currency is not None:
            expense.currency = payload.currency.upper()
        if payload.description is not None:
            expense.description = payload.description.strip()
        if payload.expense_date is not None:
            expense.expense_date = payload.expense_date
        if payload.note is not None:
            expense.note = payload.note

        await self._session.commit()
        return await self.get_expense(tenant_id=tenant_id, expense_id=expense.id)

    async def summarize(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
    ) -> ExpenseSummaryRead:
        if from_date > to_date:
            raise ExpenseError("from_date must be on or before to_date")

        resolved_currency = currency
        if resolved_currency is None:
            from app.modules.tenant.repository import TenantRepository

            tenant = await TenantRepository(self._session).get(tenant_id)
            if tenant is None:
                raise ExpenseError("Tenant is unavailable")
            resolved_currency = tenant.base_currency

        total_minor, count = await self._repo.summarize_expenses(
            tenant_id=tenant_id,
            currency=resolved_currency.upper(),
            from_date=from_date,
            to_date=to_date,
        )
        return ExpenseSummaryRead(
            currency=resolved_currency.upper(),
            total_minor=total_minor,
            expense_count=count,
            from_date=from_date,
            to_date=to_date,
        )
