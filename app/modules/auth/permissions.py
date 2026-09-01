"""Permission keys and role grants (ADR-003)."""

STAFF_READ = "staff.read"
STAFF_WRITE = "staff.write"
STAFF_STATUS = "staff.status"

ALL_PERMISSION_KEYS = frozenset({STAFF_READ, STAFF_WRITE, STAFF_STATUS})

# Default grants seeded in migration 0003.
ROLE_PERMISSION_MAP: dict[str, frozenset[str]] = {
    "owner": frozenset({STAFF_READ, STAFF_WRITE, STAFF_STATUS}),
    "manager": frozenset({STAFF_READ, STAFF_WRITE, STAFF_STATUS}),
    "cashier": frozenset(),
    "kitchen": frozenset(),
    "finance": frozenset(),
}
