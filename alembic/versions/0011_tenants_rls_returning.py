"""fix tenants RLS USING for INSERT RETURNING before closure trigger

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-03
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
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


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenants
        USING (
            NULLIF(current_setting('app.tenant_id', true), '') IS NULL
            OR id IN (
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
