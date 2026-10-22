"""
Comprehensive Test Suite for Buildora AI Authentication System.
Verifies:
- Bcrypt password hashing
- Login API (/auth/login and /api/auth/login) with JWT tokens
- Generic error messages for security ("Invalid email or password")
- Session invalidation on logout (/auth/logout)
- Current user & role (/auth/me)
- Forgot password flow (/auth/forgot-password) with timing/enumeration safe generic responses
- Reset password flow (/auth/reset-password) with token verification, min 8 char rule, session purge
- Change password flow (/auth/change-password) for authenticated users
- First-time login must_change_password flag
- Role authorization and 403 Forbidden on unauthorized role switch
- In-memory rate limiting (5 attempts/minute)
"""

import hashlib
import time
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from python_app.main import app
from python_app.database import SessionLocal
from python_app.models import User, Session, UserRole
from python_app.auth import hash_password, verify_password, _rate_limit_store
from python_app.db_migration import init_and_migrate_db

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_and_migrate_db()
    db = SessionLocal()
    try:
        # Reset rate limiter
        _rate_limit_store.clear()

        # Ensure clean state for site@demo.local
        site = db.query(User).filter(User.email == "site@demo.local").first()
        if site:
            site.password_hash = hash_password("site1234")
            site.role = "site_user"
            site.roles = ["site_user"]
            site.must_change_password = False
            db.query(UserRole).filter(UserRole.user_id == site.id).delete()
            db.add(UserRole(user_id=site.id, role="site_user"))

        # Ensure clean state for owner@demo.local
        owner = db.query(User).filter(User.email == "owner@demo.local").first()
        if owner:
            owner.password_hash = hash_password("owner1234")
            owner.role = "contractor_owner"
            owner.roles = ["contractor_owner"]
            owner.must_change_password = False
            db.query(UserRole).filter(UserRole.user_id == owner.id).delete()
            db.add(UserRole(user_id=owner.id, role="contractor_owner"))

        db.commit()
    finally:
        db.close()

@pytest.fixture
def client():
    # Clear rate limiter before tests to avoid cross-test throttling
    _rate_limit_store.clear()
    return TestClient(app)


def test_bcrypt_hashing_and_verification():
    raw_pwd = "SuperSecretPassword123"
    hashed = hash_password(raw_pwd)
    assert hashed.startswith("$2"), "Hash must be a standard bcrypt hash"
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_login_success_and_jwt_token(client):
    # Both /auth/login and /api/auth/login supported
    res = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "token" in data
    assert len(data["token"]) > 20
    assert data["user"]["email"] == "site@demo.local"
    assert data["user"]["role"] == "site_user"
    assert data["mustChangePassword"] is False

    # Also verify /api/auth/login
    res_api = client.post("/api/auth/login", json={"email": "owner@demo.local", "password": "owner1234"})
    assert res_api.status_code == 200
    assert res_api.json()["user"]["role"] == "contractor_owner"


def test_login_invalid_credentials_generic_error(client):
    # Wrong password
    res = client.post("/auth/login", json={"email": "site@demo.local", "password": "wrongpassword123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"

    # Non-existent email
    res2 = client.post("/auth/login", json={"email": "nonexistent@demo.local", "password": "somepassword123"})
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Invalid email or password"


def test_register_new_user_and_future_login(client):
    reg_email = f"newuser_{int(time.time())}@buildora.ai"
    reg_payload = {
        "name": "Rohan Mehra",
        "phone": "+91 9876543210",
        "email": reg_email,
        "password": "SecurePassword123"
    }

    # 1. Register new user
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "token" in data
    assert data["user"]["email"] == reg_email
    assert data["user"]["name"] == "Rohan Mehra"
    assert data["user"]["phone"] == "+91 9876543210"

    # 2. Duplicate registration rejected
    res_dup = client.post("/api/auth/register", json=reg_payload)
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"].lower()

    # 3. Future login with registered credentials
    res_login = client.post("/api/auth/login", json={
        "email": reg_email,
        "password": "SecurePassword123"
    })
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert login_data["user"]["email"] == reg_email
    assert login_data["user"]["name"] == "Rohan Mehra"
    assert login_data["user"]["phone"] == "+91 9876543210"

    # 4. Access /auth/me with new token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_data['token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == reg_email


def test_auth_me_endpoint(client):
    login_res = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"}).json()
    token = login_res["token"]

    # Without header
    assert client.get("/auth/me").status_code == 401

    # With valid Bearer token
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    user = res.json()["user"]
    assert user["email"] == "site@demo.local"
    assert user["role"] == "site_user"
    assert "site_user" in user["roles"]


def test_logout_session_invalidation(client):
    login_res = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"}).json()
    token = login_res["token"]

    # Access /auth/me before logout
    res_before = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_before.status_code == 200

    # Logout
    logout_res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Token should be invalidated
    res_after = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_after.status_code == 401


def test_forgot_password_generic_response(client):
    # Registered email
    res1 = client.post("/auth/forgot-password", json={"email": "site@demo.local"})
    assert res1.status_code == 200
    assert "instructions" in res1.json()["message"].lower()

    # Verify reset token was saved in DB
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "site@demo.local").first()
        assert user.reset_token_hash is not None
        assert user.reset_token_expiry is not None
    finally:
        db.close()

    # Unregistered email returns identical message (no email enumeration)
    res2 = client.post("/auth/forgot-password", json={"email": "unknown@nowhere.local"})
    assert res2.status_code == 200
    assert res1.json()["message"] == res2.json()["message"]


def test_reset_password_flow(client):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "site@demo.local").first()
        # Create a mock reset token
        raw_token = "test-reset-token-abcdef123456789"
        user.reset_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=20)
        db.commit()
    finally:
        db.close()

    # 1. Reject too short password (< 8 chars)
    res_short = client.post("/auth/reset-password", json={"token": raw_token, "new_password": "short"})
    assert res_short.status_code == 400
    assert "8 characters" in res_short.json()["detail"]

    # 2. Reject invalid token
    res_bad_tok = client.post("/auth/reset-password", json={"token": "invalid-token", "new_password": "BrandNewPassword123"})
    assert res_bad_tok.status_code == 400

    # 3. Successful reset
    res_ok = client.post("/auth/reset-password", json={"token": raw_token, "new_password": "BrandNewPassword123"})
    assert res_ok.status_code == 200

    # Old password no longer works
    assert client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"}).status_code == 401

    # New password works
    assert client.post("/auth/login", json={"email": "site@demo.local", "password": "BrandNewPassword123"}).status_code == 200

    # Token was deleted/invalidated (cannot be reused)
    res_reuse = client.post("/auth/reset-password", json={"token": raw_token, "new_password": "AnotherPassword123"})
    assert res_reuse.status_code == 400

    # Restore site1234 for subsequent tests
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "site@demo.local").first()
        user.password_hash = hash_password("site1234")
        db.commit()
    finally:
        db.close()


def test_change_password_endpoint(client):
    login = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"}).json()
    token = login["token"]

    # Wrong old password
    res_wrong = client.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "old_password": "wrongOldPassword",
        "new_password": "UpdatedPassword123"
    })
    assert res_wrong.status_code == 400
    assert "Incorrect current password" in res_wrong.json()["detail"]

    # Too short new password
    res_short = client.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "old_password": "site1234",
        "new_password": "short"
    })
    assert res_short.status_code == 400

    # Valid change
    res_ok = client.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "old_password": "site1234",
        "new_password": "UpdatedPassword123"
    })
    assert res_ok.status_code == 200

    # Re-login with new password
    assert client.post("/auth/login", json={"email": "site@demo.local", "password": "UpdatedPassword123"}).status_code == 200

    # Reset back to site1234
    client.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "old_password": "UpdatedPassword123",
        "new_password": "site1234"
    })


def test_switch_role_authorization_and_403(client):
    # site@demo.local only has 'site_user' role
    site_token = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"}).json()["token"]

    # Attempt to switch to contractor_owner must return 403 Forbidden!
    res_forbidden = client.post("/auth/switch-role", headers={"Authorization": f"Bearer {site_token}"}, json={
        "target_role": "contractor_owner"
    })
    assert res_forbidden.status_code == 403
    assert "not have permission" in res_forbidden.json()["detail"]


def test_first_time_login_must_change_password(client):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "site@demo.local").first()
        user.must_change_password = True
        db.commit()
    finally:
        db.close()

    res = client.post("/auth/login", json={"email": "site@demo.local", "password": "site1234"})
    assert res.status_code == 200
    assert res.json()["mustChangePassword"] is True

    # After password change, must_change_password is cleared
    token = res.json()["token"]
    client.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "old_password": "site1234",
        "new_password": "NewPermanentPass123"
    })

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "site@demo.local").first()
        assert user.must_change_password is False
        # Reset back
        user.password_hash = hash_password("site1234")
        db.commit()
    finally:
        db.close()


def test_rate_limiting_login_endpoint(client):
    _rate_limit_store.clear()
    # Execute 5 attempts
    for _ in range(5):
        client.post("/auth/login", json={"email": "test@demo.local", "password": "badpassword123"})
    # 6th attempt must be rejected with 429
    res_429 = client.post("/auth/login", json={"email": "test@demo.local", "password": "badpassword123"})
    assert res_429.status_code == 429
    assert "Too many requests" in res_429.json()["detail"]
    _rate_limit_store.clear()
