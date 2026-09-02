"""inventory tables, RLS, unit seeds, and inventory permissions (ADR-005)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-02
"""
import os
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_DB_ROLE = os.environ.get("APP_DB_ROLE", "hbm_app")

UNIT_SEEDS = (
    ("kg", "Kilogram", "kg"),
    ("g", "Gram", "g"),
    ("l", "Litre", "L"),
    ("ml", "Millilitre", "mL"),
    ("piece", "Piece", "pc"),
    ("sack", "Sack", "sack"),
    ("crate", "Crate", "crate"),
    ("dozen", "Dozen", "dz"),
)

PERMISSION_SEEDS = (
    ("inventory.read", "View inventory products, stock levels, and history"),
    ("inventory.write", "Manage products and record stock movements"),
)

ROLE_PERMISSION_MAP = {
    "owner": ("inventory.read", "inventory.write"),
    "manager": ("inventory.read", "inventory.write"),
    "cashier": ("inventory.read", "inventory.write"),
    "kitchen": ("inventory.read", "inventory.write"),
    "finance": ("inventory.read",),
}

TENANT_TABLES = ("products", "product_units", "stock_movements", "stock_levels")


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
        "units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    units_table = sa.table(
        "units",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("symbol", sa.String()),
    )
    op.bulk_insert(
        units_table,
        [
            {"id": uuid.uuid4(), "key": key, "name": name, "symbol": symbol}
            for key, name, symbol in UNIT_SEEDS
        ],
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("base_unit_id", sa.Uuid(), nullable=False),
        sa.Column("reorder_level_base", sa.Numeric(precision=24, scale=6), nullable=True),
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
        sa.ForeignKeyConstraint(["base_unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])

    op.create_table(
        "product_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("to_base_factor", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("is_stock", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_purchase", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_recipe", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_sales", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "unit_id", name="uq_product_units_product_unit"),
    )
    op.create_index("ix_product_units_tenant_id", "product_units", ["tenant_id"])
    op.create_index("ix_product_units_product_id", "product_units", ["product_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta_base", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("entered_quantity", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("entered_unit_id", sa.Uuid(), nullable=False),
        sa.Column("to_base_factor_snapshot", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_document_type", sa.String(length=50), nullable=True),
        sa.Column("source_document_id", sa.String(length=100), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["entered_unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_stock_movements_tenant_idempotency",
        ),
    )
    op.create_index("ix_stock_movements_tenant_id", "stock_movements", ["tenant_id"])
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])

    op.create_table(
        "stock_levels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity_base",
            sa.Numeric(precision=24, scale=6),
            server_default="0",
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "product_id", name="uq_stock_levels_tenant_product"
        ),
    )
    op.create_index("ix_stock_levels_tenant_id", "stock_levels", ["tenant_id"])

    for table in TENANT_TABLES:
        _enable_rls(table)

    # Permissions
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

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_DB_ROLE}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON units TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON products TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON product_units TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON stock_movements TO {APP_DB_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON stock_levels TO {APP_DB_ROLE};
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE key IN "
            "('inventory.read', 'inventory.write'))"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE key IN ('inventory.read', 'inventory.write')"
        )
    )

    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_stock_levels_tenant_id", table_name="stock_levels")
    op.drop_table("stock_levels")
    op.drop_index("ix_stock_movements_product_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_tenant_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index("ix_product_units_product_id", table_name="product_units")
    op.drop_index("ix_product_units_tenant_id", table_name="product_units")
    op.drop_table("product_units")
    op.drop_index("ix_products_tenant_id", table_name="products")
    op.drop_table("products")
    op.drop_table("units")
