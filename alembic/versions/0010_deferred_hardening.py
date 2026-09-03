"""deferred hardening: tenant closure + RLS, entitlements, refresh_sessions RLS

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-03
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")

MODULE_KEYS = ("inventory", "pos")


def upgrade() -> None:
    # --- tenant closure (enables non-recursive tenants RLS) ---
    op.create_table(
        "tenant_closure",
        sa.Column("ancestor_id", sa.Uuid(), nullable=False),
        sa.Column("descendant_id", sa.Uuid(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["ancestor_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["descendant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ancestor_id", "descendant_id"),
    )
    op.create_index("ix_tenant_closure_descendant_id", "tenant_closure", ["descendant_id"])

    op.execute(
        """
        INSERT INTO tenant_closure (ancestor_id, descendant_id, depth)
        WITH RECURSIVE tree AS (
            SELECT id AS root_id, id AS node_id, 0 AS depth
            FROM tenants
            WHERE parent_tenant_id IS NULL
            UNION ALL
            SELECT tree.root_id, t.id, tree.depth + 1
            FROM tenants t
            JOIN tree ON t.parent_tenant_id = tree.node_id
        )
        SELECT root_id, node_id, depth FROM tree
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION maintain_tenant_closure()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            INSERT INTO tenant_closure (ancestor_id, descendant_id, depth)
            VALUES (NEW.id, NEW.id, 0);

            IF NEW.parent_tenant_id IS NOT NULL THEN
                INSERT INTO tenant_closure (ancestor_id, descendant_id, depth)
                SELECT ancestor_id, NEW.id, depth + 1
                FROM tenant_closure
                WHERE descendant_id = NEW.parent_tenant_id;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER tenant_closure_after_insert
        AFTER INSERT ON tenants
        FOR EACH ROW
        EXECUTE FUNCTION maintain_tenant_closure();
        """
    )

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenants
        USING (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR id IN (
                SELECT descendant_id FROM tenant_closure
                WHERE ancestor_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            OR parent_tenant_id IN (
                SELECT descendant_id FROM tenant_closure
                WHERE ancestor_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
        )
        WITH CHECK (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR parent_tenant_id IN (
                SELECT descendant_id FROM tenant_closure
                WHERE ancestor_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
        )
        """
    )

    op.execute("ALTER TABLE tenant_closure ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_closure NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_closure_isolation ON tenant_closure
        USING (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR ancestor_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )

    # --- module entitlements (ADR-012 subproducts) ---
    op.create_table(
        "tenant_entitlements",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("module_key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "module_key"),
    )

    entitlements = sa.table(
        "tenant_entitlements",
        sa.column("tenant_id", sa.Uuid()),
        sa.column("module_key", sa.String()),
        sa.column("enabled", sa.Boolean()),
    )
    connection = op.get_bind()
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants"))]
    rows = [
        {"tenant_id": tenant_id, "module_key": key, "enabled": True}
        for tenant_id in tenant_ids
        for key in MODULE_KEYS
    ]
    if rows:
        op.bulk_insert(entitlements, rows)

    op.execute("ALTER TABLE tenant_entitlements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_entitlements FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenant_entitlements
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

    # --- refresh_sessions RLS ---
    op.execute("ALTER TABLE refresh_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON refresh_sessions
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

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_DB_ROLE}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_closure TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_entitlements TO {APP_DB_ROLE};
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON refresh_sessions")
    op.execute("ALTER TABLE refresh_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_sessions DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_entitlements")
    op.execute("ALTER TABLE tenant_entitlements NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_entitlements DISABLE ROW LEVEL SECURITY")
    op.drop_table("tenant_entitlements")

    op.execute("DROP POLICY IF EXISTS tenant_closure_isolation ON tenant_closure")
    op.execute("ALTER TABLE tenant_closure NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_closure DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")

    op.execute("DROP TRIGGER IF EXISTS tenant_closure_after_insert ON tenants")
    op.execute("DROP FUNCTION IF EXISTS maintain_tenant_closure()")
    op.drop_index("ix_tenant_closure_descendant_id", table_name="tenant_closure")
    op.drop_table("tenant_closure")
