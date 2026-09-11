"""recipes + recipe_items tables and recipes permissions (Phase 2a)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-11
"""
import os
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")

PERMISSION_SEEDS = (
    ("recipes.read", "View recipe bills of materials"),
    ("recipes.write", "Create and manage recipe bills of materials"),
)

ROLE_PERMISSION_MAP = {
    "owner": ("recipes.read", "recipes.write"),
    "manager": ("recipes.read", "recipes.write"),
    "kitchen": ("recipes.read", "recipes.write"),
    "finance": ("recipes.read",),
    "cashier": ("recipes.read",),
}

TENANT_TABLES = ("recipes", "recipe_items")


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
        "recipes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "yields_quantity",
            sa.Numeric(precision=24, scale=6),
            server_default="1",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_recipes_tenant_product"),
    )
    op.create_index("ix_recipes_tenant_id", "recipes", ["tenant_id"])
    op.create_index("ix_recipes_product_id", "recipes", ["product_id"])

    op.create_table(
        "recipe_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["ingredient_product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id",
            "ingredient_product_id",
            name="uq_recipe_items_recipe_ingredient",
        ),
    )
    op.create_index("ix_recipe_items_tenant_id", "recipe_items", ["tenant_id"])
    op.create_index("ix_recipe_items_recipe_id", "recipe_items", ["recipe_id"])
    op.create_index(
        "ix_recipe_items_ingredient_product_id",
        "recipe_items",
        ["ingredient_product_id"],
    )

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

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON recipes TO {APP_DB_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON recipe_items TO {APP_DB_ROLE}")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE key IN ('recipes.read', 'recipes.write'))"
        )
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE key IN ('recipes.read', 'recipes.write')")
    )

    op.drop_index("ix_recipe_items_ingredient_product_id", table_name="recipe_items")
    op.drop_index("ix_recipe_items_recipe_id", table_name="recipe_items")
    op.drop_index("ix_recipe_items_tenant_id", table_name="recipe_items")
    op.drop_table("recipe_items")

    op.drop_index("ix_recipes_product_id", table_name="recipes")
    op.drop_index("ix_recipes_tenant_id", table_name="recipes")
    op.drop_table("recipes")
