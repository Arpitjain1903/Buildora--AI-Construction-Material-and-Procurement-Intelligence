"""
Seed Script: Seeds Demo Users with Secure Bcrypt Hashed Passwords.
Usage:
    python scripts/seed_users.py
"""

import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from python_app.database import engine, SessionLocal
from python_app.models import User, Organization, UserRole
from python_app.auth import hash_password
from python_app.db_migration import init_and_migrate_db

def seed_demo_users():
    init_and_migrate_db()
    db = SessionLocal()
    try:
        # Organization
        org = db.query(Organization).filter(Organization.id == "org_demo").first()
        if not org:
            org = Organization(id="org_demo", name="Demo Contractor Co.")
            db.add(org)
            db.commit()

        # Seed site@demo.local and owner@demo.local
        users_to_seed = [
            {
                "id": "user_site_001",
                "name": "Site Engineer",
                "email": "site@demo.local",
                "phone": "+91 98765 43210",
                "role": "site_user",
                "roles": ["site_user"],
                "password": "site1234", # min 8 chars
                "must_change_password": False
            },
            {
                "id": "user_owner_001",
                "name": "Contractor Owner",
                "email": "owner@demo.local",
                "phone": "+91 98765 12345",
                "role": "contractor_owner",
                "roles": ["contractor_owner"],
                "password": "owner1234", # min 8 chars
                "must_change_password": False
            }
        ]

        # Clean any unnecessary demo users
        db.query(UserRole).filter(UserRole.user_id == "user_new_001").delete()
        db.query(User).filter(User.email == "newuser@demo.local").delete()
        db.commit()

        print("\n" + "=" * 65)
        print("SEEDING DEMO USERS (BCRYPT HASHED)")
        print("=" * 65)

        for u in users_to_seed:
            user = db.query(User).filter(User.email == u["email"]).first()
            if not user:
                user = User(
                    id=u["id"],
                    organization_id="org_demo",
                    name=u["name"],
                    email=u["email"],
                    role=u["role"],
                    roles=u["roles"],
                    password_hash=hash_password(u["password"]),
                    must_change_password=u["must_change_password"],
                    phone=u.get("phone")
                )
                db.add(user)
                db.flush()
            else:
                user.name = u["name"]
                user.role = u["role"]
                user.roles = u["roles"]
                user.phone = u.get("phone")
                user.password_hash = hash_password(u["password"])
                user.must_change_password = u["must_change_password"]
                db.flush()

            # Ensure UserRole table entry
            db.query(UserRole).filter(UserRole.user_id == user.id).delete()
            for r in u["roles"]:
                db.add(UserRole(user_id=user.id, role=r))

            print(f"Email: {user.email:<18} | Role: {user.role:<16} | Password: {u['password']}")

        db.commit()
        print("=" * 65)
        print("Demo users seeded successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_users()
