"""
Authentication, Authorization & Audit Logging for Python Platform.
Ports Node auth.js:
- Scrypt hashing & timing-safe verification matching Node crypto.scryptSync
- 8-hour bearer token sessions
- Roles: contractor_owner, site_user
- Project access checks
- Append-only audit trail logging
"""

import hmac
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session as DBSession

from python_app.database import get_db
from python_app.models import User, Session, ProjectMember, Project, AuditLog

SESSION_HOURS = 8

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Computes scrypt hash matching Node crypto.scryptSync(password, salt, 64)
    Format: salt:hash_hex
    """
    if salt is None:
        salt = secrets.token_hex(16)
    salt_bytes = salt.encode("utf-8")
    pwd_bytes = str(password).encode("utf-8")
    # Standard Node scrypt parameters: N=16384, r=8, p=1, dklen=64
    derived = hashlib.scrypt(pwd_bytes, salt=salt_bytes, n=16384, r=8, p=1, maxmem=0, dklen=64)
    return f"{salt}:{derived.hex()}"

def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """
    Timing-safe verification of password against stored salt:hash string.
    """
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, expected_hex = stored_hash.split(":", 1)
    salt_bytes = salt.encode("utf-8")
    pwd_bytes = str(password).encode("utf-8")
    derived = hashlib.scrypt(pwd_bytes, salt=salt_bytes, n=16384, r=8, p=1, maxmem=0, dklen=64)
    return hmac.compare_digest(derived.hex(), expected_hex)

def public_user(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "organizationId": user.organization_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "createdAt": user.created_at.isoformat() if user.created_at else None
    }

def authenticate(email: str, password: str, db: DBSession) -> Optional[Dict[str, Any]]:
    user = db.query(User).filter(User.email.ilike(email.strip())).first()
    if not user or not verify_password(password, user.password_hash):
        return None

    # Clean expired sessions
    now = datetime.now(timezone.utc)
    db.query(Session).filter(Session.expires_at < now).delete()

    token = secrets.token_hex(32)
    expires_at = now + timedelta(hours=SESSION_HOURS)
    session = Session(token=token, user_id=user.id, expires_at=expires_at)
    db.add(session)
    db.commit()

    return {
        "token": token,
        "expiresAt": expires_at.isoformat(),
        "user": public_user(user)
    }

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
) -> User:
    """FastAPI Dependency for token authentication."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token."
        )

    token = authorization.replace("Bearer ", "").strip()
    session = db.query(Session).filter(
        Session.token == token,
        Session.expires_at > datetime.now(timezone.utc)
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token."
        )

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found."
        )
    return user

def require_role(allowed_roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized. Required: {allowed_roles}"
            )
        return user
    return role_checker

def has_project_access(user: User, project_id: str, db: DBSession) -> bool:
    if not user:
        return False
    # contractor_owner has access to all projects in their organization
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    if user.role == "contractor_owner" and user.organization_id == project.organization_id:
        return True
    # site_user must be explicitly assigned to project
    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id
    ).first()
    return membership is not None

def log_audit(
    db: DBSession,
    actor_user_id: str,
    action: str,
    project_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """Logs an immutable audit event."""
    audit_entry = AuditLog(
        project_id=project_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_id=entity_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        details=details or {}
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
