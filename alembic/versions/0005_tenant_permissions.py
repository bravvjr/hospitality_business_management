"""sub-tenant (branch) management permissions + grants (ADR-012)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_SEEDS = (
    ("tenant.read", "View sub-tenants (branches)"),
    ("tenant.write", "Create and manage sub-tenants (branches)"),
)

# Owners manage the tenant tree; managers may view it.
ROLE_PERMISSION_MAP = {
    "owner": ("tenant.read", "tenant.write"),
    "manager": ("tenant.read",),
}


def upgrade() -> None:
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
    )
    permission_ids = {key: uuid.uuid4() for key, _ in PERMISSION_SEEDS}
    op.bulk_insert(
        permissions_table,
        [{"id": permission_ids[key], "key": key, "name": name} for key, name in PERMISSION_SEEDS],
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
            rows.append({"role_id": role_id, "permission_id": permission_ids[permission_key]})
    if rows:
        op.bulk_insert(role_permissions_table, rows)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE key IN ('tenant.read', 'tenant.write'))"
        )
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE key IN ('tenant.read', 'tenant.write')")
    )
