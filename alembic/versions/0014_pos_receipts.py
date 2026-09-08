"""POS sale receipts (migration 0014)

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-08
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.add_column("orders", sa.Column("receipt_number", sa.BigInteger(), nullable=True))
    op.create_index(
        "uq_orders_tenant_receipt_number",
        "orders",
        ["tenant_id", "receipt_number"],
        unique=True,
        postgresql_where=sa.text("receipt_number IS NOT NULL"),
    )

    op.create_table(
        "pos_receipt_sequences",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("next_receipt_number", sa.BigInteger(), nullable=False, server_default="1"),
    )
    _enable_rls("pos_receipt_sequences")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON pos_receipt_sequences TO {APP_DB_ROLE}")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON pos_receipt_sequences")
    op.drop_table("pos_receipt_sequences")
    op.drop_index("uq_orders_tenant_receipt_number", table_name="orders")
    op.drop_column("orders", "receipt_number")
