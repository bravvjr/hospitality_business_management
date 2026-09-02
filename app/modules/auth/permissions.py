"""Permission keys (ADR-003). Role grants are seeded in migrations 0003 / 0005 / 0007."""

STAFF_READ = "staff.read"
STAFF_WRITE = "staff.write"
STAFF_STATUS = "staff.status"

# Sub-tenant (branch) management.
TENANT_READ = "tenant.read"
TENANT_WRITE = "tenant.write"

# Inventory module (re-exported for convenience; canonical keys live in inventory.permissions).
INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"

# POS module.
POS_READ = "pos.read"
POS_WRITE = "pos.write"
