"""report query indexes (Phase 2b)

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_orders_tenant_completed_at",
        "orders",
        ["tenant_id", "completed_at"],
        postgresql_where=sa.text("status = 'completed'"),
    )
    op.create_index(
        "ix_expenses_tenant_expense_date",
        "expenses",
        ["tenant_id", "expense_date"],
    )
    op.create_index(
        "ix_stock_movements_tenant_created_at",
        "stock_movements",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_tenant_created_at", table_name="stock_movements")
    op.drop_index("ix_expenses_tenant_expense_date", table_name="expenses")
    op.drop_index("ix_orders_tenant_completed_at", table_name="orders")
