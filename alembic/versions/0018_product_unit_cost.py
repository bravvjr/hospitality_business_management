"""product unit cost columns for ingredient costing (Phase 2)

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-12
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("unit_cost_minor", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("cost_currency", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "cost_currency")
    op.drop_column("products", "unit_cost_minor")
