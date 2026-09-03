"""phase 1 hardening: tighten RBAC permissions (ADR-003)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-03

Tenants-table RLS (subtree policy) is deferred: hierarchical tenant rows need a
closure table or SECURITY DEFINER insert helper to avoid policy recursion and
INSERT WITH CHECK edge cases. Tenant routes now use get_tenant_session; subtree
access is enforced in TenantService (ADR-012).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id
          AND rp.permission_id = p.id
          AND r.key IN ('kitchen', 'cashier')
          AND p.key = 'inventory.write'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.key IN ('kitchen', 'cashier')
          AND p.key = 'inventory.write'
        ON CONFLICT DO NOTHING
        """
    )
