"""Role keys and assignment rules (ADR-003)."""

OWNER = "owner"
MANAGER = "manager"
CASHIER = "cashier"
KITCHEN = "kitchen"
FINANCE = "finance"

ALL_ROLE_KEYS = frozenset({OWNER, MANAGER, CASHIER, KITCHEN, FINANCE})

# Roles a manager may assign (owners can assign any role).
MANAGER_ASSIGNABLE_ROLES = frozenset({CASHIER, KITCHEN, FINANCE})


def assert_assignable_role(*, actor_role: str, role_key: str) -> None:
    if role_key not in ALL_ROLE_KEYS:
        raise ValueError(f"Unknown role: {role_key}")
    if actor_role == OWNER:
        return
    if actor_role == MANAGER:
        if role_key in MANAGER_ASSIGNABLE_ROLES:
            return
        raise ValueError("Managers may only assign cashier, kitchen, or finance roles")
    raise ValueError("Insufficient role to assign staff")
