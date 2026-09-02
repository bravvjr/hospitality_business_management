"""enable row-level security on tenant-scoped tables (ADR-002)

Applies defense-in-depth tenant isolation: FORCE RLS + a single indexed-equality
policy keyed on the per-transaction `app.tenant_id` GUC. An unset GUC allows all
rows so the pre-tenant-context auth bootstrap (login/register/switch) keeps working;
once a request sets the tenant context (see app.core.db.apply_tenant_context), the
policy restricts every row to the active tenant.

Runs as the OWNER role. Grants runtime DML to the non-owner app role when present.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02
"""
import os
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tenant-scoped tables get RLS keyed on this column.
TENANT_TABLES = ("memberships",)

# Non-owner runtime role that the application connects as (ADR-002).
APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # NULLIF(..., '') treats an unset OR reset (post-commit) GUC as "no
        # tenant context" so the pre-context auth bootstrap keeps working; a set
        # GUC restricts every row to that tenant.
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

    # Grant runtime DML to the app role if it exists (idempotent, guarded).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_DB_ROLE}') THEN
                GRANT USAGE ON SCHEMA public TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public TO {APP_DB_ROLE};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_DB_ROLE};
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
