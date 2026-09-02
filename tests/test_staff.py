"""Integration tests for tenant staff management."""
import uuid

import pytest


async def _register_owner(client, *, email: str | None = None, password: str = "secure-pass-123"):
    email = email or f"owner-{uuid.uuid4()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": "Test Cafe",
            "base_currency": "KES",
        },
    )
    assert response.status_code == 201
    return response, email, password


@pytest.mark.integration
async def test_owner_adds_and_lists_staff(client):
    owner_resp, _, _ = await _register_owner(client)

    add_resp = await client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"cashier-{uuid.uuid4()}@example.com",
            "password": "cashier-pass-123",
            "role_key": "cashier",
        },
        cookies=owner_resp.cookies,
    )
    assert add_resp.status_code == 201
    body = add_resp.json()
    assert body["membership"]["role"]["key"] == "cashier"

    list_resp = await client.get("/api/v1/auth/staff", cookies=owner_resp.cookies)
    assert list_resp.status_code == 200
    page = list_resp.json()
    emails = {member["user"]["email"] for member in page["items"]}
    assert body["user"]["email"] in emails
    assert page["total"] == 2  # owner + cashier
    assert len(page["items"]) == 2


@pytest.mark.integration
async def test_cashier_cannot_manage_staff(client):
    owner_resp, _, _ = await _register_owner(client)
    cashier_email = f"cashier-{uuid.uuid4()}@example.com"

    await client.post(
        "/api/v1/auth/staff",
        json={"email": cashier_email, "password": "cashier-pass-123", "role_key": "cashier"},
        cookies=owner_resp.cookies,
    )

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": cashier_email, "password": "cashier-pass-123"},
    )
    assert login_resp.status_code == 200

    denied = await client.get("/api/v1/auth/staff", cookies=login_resp.cookies)
    assert denied.status_code == 403


@pytest.mark.integration
async def test_manager_cannot_assign_manager_role(client):
    owner_resp, _, _ = await _register_owner(client)
    manager_email = f"manager-{uuid.uuid4()}@example.com"

    await client.post(
        "/api/v1/auth/staff",
        json={"email": manager_email, "password": "manager-pass-123", "role_key": "manager"},
        cookies=owner_resp.cookies,
    )

    manager_login = await client.post(
        "/api/v1/auth/login",
        json={"email": manager_email, "password": "manager-pass-123"},
    )

    denied = await client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"other-{uuid.uuid4()}@example.com",
            "password": "other-pass-123",
            "role_key": "manager",
        },
        cookies=manager_login.cookies,
    )
    assert denied.status_code == 400


@pytest.mark.integration
async def test_add_existing_user_to_tenant(client):
    owner_resp, owner_email, owner_password = await _register_owner(client)
    shared_email = f"shared-{uuid.uuid4()}@example.com"

    other_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": shared_email,
            "password": "shared-pass-123",
            "tenant_name": "Other Cafe",
        },
    )
    assert other_owner.status_code == 201

    add_resp = await client.post(
        "/api/v1/auth/staff",
        json={"email": shared_email, "role_key": "kitchen"},
        cookies=owner_resp.cookies,
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["membership"]["role"]["key"] == "kitchen"

    tenant_id = owner_resp.json()["tenant"]["id"]
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": shared_email,
            "password": "shared-pass-123",
            "tenant_id": tenant_id,
        },
    )
    assert login_resp.status_code == 200


@pytest.mark.integration
async def test_update_and_remove_staff(client):
    owner_resp, _, _ = await _register_owner(client)
    staff_email = f"finance-{uuid.uuid4()}@example.com"

    created = await client.post(
        "/api/v1/auth/staff",
        json={"email": staff_email, "password": "finance-pass-123", "role_key": "finance"},
        cookies=owner_resp.cookies,
    )
    membership_id = created.json()["membership"]["id"]

    updated = await client.patch(
        f"/api/v1/auth/staff/{membership_id}",
        json={"role_key": "cashier"},
        cookies=owner_resp.cookies,
    )
    assert updated.status_code == 200
    assert updated.json()["membership"]["role"]["key"] == "cashier"

    removed = await client.delete(
        f"/api/v1/auth/staff/{membership_id}",
        cookies=owner_resp.cookies,
    )
    assert removed.status_code == 200

    staff = await client.get("/api/v1/auth/staff", cookies=owner_resp.cookies)
    assert all(m["membership"]["id"] != membership_id for m in staff.json()["items"])


@pytest.mark.integration
async def test_deactivate_and_reactivate_staff(client):
    owner_resp, _, _ = await _register_owner(client)
    staff_email = f"kitchen-{uuid.uuid4()}@example.com"

    created = await client.post(
        "/api/v1/auth/staff",
        json={"email": staff_email, "password": "kitchen-pass-123", "role_key": "kitchen"},
        cookies=owner_resp.cookies,
    )
    membership_id = created.json()["membership"]["id"]

    deactivated = await client.patch(
        f"/api/v1/auth/staff/{membership_id}/status",
        json={"status": "inactive"},
        cookies=owner_resp.cookies,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["user"]["status"] == "inactive"

    login_denied = await client.post(
        "/api/v1/auth/login",
        json={"email": staff_email, "password": "kitchen-pass-123"},
    )
    assert login_denied.status_code == 401

    reactivated = await client.patch(
        f"/api/v1/auth/staff/{membership_id}/status",
        json={"status": "active"},
        cookies=owner_resp.cookies,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["user"]["status"] == "active"

    login_ok = await client.post(
        "/api/v1/auth/login",
        json={"email": staff_email, "password": "kitchen-pass-123"},
    )
    assert login_ok.status_code == 200


@pytest.mark.integration
async def test_cannot_deactivate_own_account(client):
    owner_resp, _, _ = await _register_owner(client)
    owner_membership_id = owner_resp.json()["membership"]["id"]

    denied = await client.patch(
        f"/api/v1/auth/staff/{owner_membership_id}/status",
        json={"status": "inactive"},
        cookies=owner_resp.cookies,
    )
    assert denied.status_code == 400

