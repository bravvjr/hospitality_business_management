"""Tenant module entitlements (ADR-012 subproducts)."""

INVENTORY = "inventory"
POS = "pos"
FINANCE = "finance"

DEFAULT_MODULE_KEYS = frozenset({INVENTORY, POS})
