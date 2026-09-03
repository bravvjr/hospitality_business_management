"""expense categories + expenses ledger (Phase 1 finance MVP)

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-03
"""
import os
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")

PERMISSION_SEEDS = (
    ("expenses.read", "View expense categories and expense history"),
    ("expenses.write", "Record and manage expenses"),
)

ROLE_PERMISSION_MAP = {
    "owner": ("expenses.read", "expenses.write"),
    "manager": ("expenses.read", "expenses.write"),
    "finance": ("expenses.read", "expenses.write"),
    "cashier": ("expenses.read",),
    "kitchen": (),
}

TENANT_TABLES = ("expense_categories", "expenses")
MODULE_KEY = "finance"


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
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_expense_categories_tenant_name"),
    )
    op.create_index("ix_expense_categories_tenant_id", "expense_categories", ["tenant_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_tenant_id", "expenses", ["tenant_id"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])

    for table in TENANT_TABLES:
        _enable_rls(table)

    permission_ids = {key: uuid.uuid4() for key, _ in PERMISSION_SEEDS}
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": permission_ids[key], "key": key, "name": name}
            for key, name in PERMISSION_SEEDS
        ],
    )

    connection = op.get_bind()
    role_ids = {
        row.key: row.id
        for row in connection.execute(sa.text("SELECT id, key FROM roles")).fetchall()
    }
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    rows = []
    for role_key, permission_keys in ROLE_PERMISSION_MAP.items():
        role_id = role_ids.get(role_key)
        if role_id is None:
            continue
        for permission_key in permission_keys:
            rows.append(
                {
                    "role_id": role_id,
                    "permission_id": permission_ids[permission_key],
                }
            )
    if rows:
        op.bulk_insert(role_permissions_table, rows)

    # Backfill finance entitlement for existing tenants.
    entitlements = sa.table(
        "tenant_entitlements",
        sa.column("tenant_id", sa.Uuid()),
        sa.column("module_key", sa.String()),
        sa.column("enabled", sa.Boolean()),
    )
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants"))]
    entitlement_rows = [
        {"tenant_id": tenant_id, "module_key": MODULE_KEY, "enabled": True}
        for tenant_id in tenant_ids
    ]
    if entitlement_rows:
        op.bulk_insert(entitlements, entitlement_rows)

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_DB_ROLE}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON expense_categories TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON expenses TO {APP_DB_ROLE};
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE key IN ('expenses.read', 'expenses.write'))"
        )
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE key IN ('expenses.read', 'expenses.write')")
    )
    connection.execute(
        sa.text("DELETE FROM tenant_entitlements WHERE module_key = 'finance'")
    )

    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_tenant_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_expense_categories_tenant_id", table_name="expense_categories")
    op.drop_table("expense_categories")
