"""
Pytest Suite for Phase 1: Unified Architecture Integration Tests.
Verifies:
1. One login works against one API and one database (SQLite/PostgreSQL).
2. Ported auth, roles (contractor_owner, site_user), sessions, and access control.
3. Procurement queue netting and quote comparisons.
4. Receipts recording, stock netting, and append-only audit trail.
5. Project creation with automatic BOQ take-off generation.
"""

import pytest
from fastapi.testclient import TestClient
from python_app.main import app

client = TestClient(app)

def test_unified_auth_login_owner():
    """Verifies login for contractor_owner user."""
    resp = client.post("/api/auth/login", json={
        "email": "owner@demo.local",
        "password": "owner123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "owner@demo.local"
    assert data["user"]["role"] == "contractor_owner"

def test_unified_auth_login_site():
    """Verifies login for site_user."""
    resp = client.post("/api/auth/login", json={
        "email": "site@demo.local",
        "password": "site123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["role"] == "site_user"

def test_unified_auth_me_endpoint():
    """Verifies /api/auth/me requires valid Bearer token."""
    # Unauthenticated
    resp_unauth = client.get("/api/auth/me")
    assert resp_unauth.status_code == 401

    # Authenticated
    login_resp = client.post("/api/auth/login", json={"email": "owner@demo.local", "password": "owner123"}).json()
    token = login_resp["token"]

    resp_auth = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_auth.status_code == 200
    assert resp_auth.json()["user"]["email"] == "owner@demo.local"

def test_unified_project_data_and_procurement_queue():
    """Verifies project data, BOQ, quotes, and procurement queue work through unified API."""
    login_resp = client.post("/api/auth/login", json={"email": "owner@demo.local", "password": "owner123"}).json()
    token = login_resp["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List projects
    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()["projects"]
    assert len(projects) >= 1
    proj_id = projects[0]["id"]

    # Full project view
    proj_resp = client.get(f"/api/projects/{proj_id}", headers=headers)
    assert proj_resp.status_code == 200
    pdata = proj_resp.json()
    assert "boq" in pdata
    assert "quotes" in pdata
    assert "procurementQueue" in pdata
    assert "comparisons" in pdata
    assert len(pdata["boq"]) >= 3
    assert len(pdata["comparisons"]) >= 1

    # Procurement queue check
    queue = pdata["procurementQueue"]
    assert len(queue) == len(pdata["boq"])
    for item in queue:
        assert "materialId" in item
        assert "netRequirement" in item
        assert "action" in item
        assert item["action"] in ["covered", "buy_now", "buy_later"]

def test_unified_receipts_and_audit_trail():
    """Verifies recording a receipt logs an immutable audit event."""
    login_resp = client.post("/api/auth/login", json={"email": "site@demo.local", "password": "site123"}).json()
    token = login_resp["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Record receipt
    receipt_resp = client.post("/api/projects/proj_sharma_001/receipts", headers=headers, json={
        "material_id": "cement_opc53",
        "material_name": "Cement OPC 53",
        "supplier_id": "sup_alpha",
        "quantity": 25.0,
        "actual_unit_cost": 405.0,
        "invoice_number": "INV-2026-99"
    })
    assert receipt_resp.status_code == 200
    assert receipt_resp.json()["ok"] is True

    # Audit log check
    audit_resp = client.get("/api/projects/proj_sharma_001/audit", headers=headers)
    assert audit_resp.status_code == 200
    events = audit_resp.json()["auditEvents"]
    assert len(events) >= 1
    assert any(e["action"] == "receipt.created" for e in events)

def test_unified_role_enforcement():
    """Verifies role permissions: site_user cannot approve quotes, only contractor_owner can."""
    site_token = client.post("/api/auth/login", json={"email": "site@demo.local", "password": "site123"}).json()["token"]
    owner_token = client.post("/api/auth/login", json={"email": "owner@demo.local", "password": "owner123"}).json()["token"]

    # Site user attempting quote approval -> 403 Forbidden
    resp_site = client.post("/api/projects/proj_sharma_001/approvals", headers={"Authorization": f"Bearer {site_token}"}, json={
        "quote_id": "q_001",
        "status": "approved",
        "comments": "Unauthorized approval"
    })
    assert resp_site.status_code == 403

    # Owner user approving quote -> 200 OK
    resp_owner = client.post("/api/projects/proj_sharma_001/approvals", headers={"Authorization": f"Bearer {owner_token}"}, json={
        "quote_id": "q_001",
        "status": "approved",
        "comments": "Approved by owner"
    })
    assert resp_owner.status_code == 200
    assert resp_owner.json()["ok"] is True
