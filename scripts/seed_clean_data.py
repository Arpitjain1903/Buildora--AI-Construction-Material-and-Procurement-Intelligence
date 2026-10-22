"""
Clean Database Seed Script for Buildora.
Cleans up test/dummy projects and seeds 3 realistic construction projects with clean stage enums:
1. Sharma Residence (Delhi, Foundation)
2. Sunrise Heights Apartments (Noida, Planning)
3. Metro Commercial Plaza (Gurugram, Structure)
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from python_app.database import SessionLocal
from python_app.models import (
    Project, BoqItem, SupplierQuote, Stock, OpenOrder, Receipt, Approval,
    User, Organization, UserRole, ProjectMember
)
from python_app.db_migration import init_and_migrate_db

def seed_clean_projects():
    init_and_migrate_db()
    db = SessionLocal()
    try:
        # 1. Clean up test/dummy projects
        test_projects = db.query(Project).filter(
            (Project.name.like("%resudiance%")) |
            (Project.name.like("%test%")) |
            (Project.id == "proj_1792514632")
        ).all()
        for tp in test_projects:
            print(f"Removing dummy project: {tp.id} - {tp.name}")
            db.delete(tp)
        db.commit()

        # 2. Ensure Organization
        org = db.query(Organization).filter(Organization.id == "org_demo").first()
        if not org:
            org = Organization(id="org_demo", name="Demo Contractor Co.")
            db.add(org)
            db.commit()

        # 3. Realistic Projects with clean stage enum: Planning, Foundation, Structure, Finishing, Completed
        real_projects = [
            {
                "id": "proj_sharma_001",
                "name": "Sharma Residence",
                "city": "Delhi",
                "type": "Low-rise residential",
                "area_sqft": 2000.0,
                "floors": 2,
                "stage": "Foundation",
                "target_date": "2027-01-31",
                "currency": "INR"
            },
            {
                "id": "proj_sunrise_002",
                "name": "Sunrise Heights Apartments",
                "city": "Noida",
                "type": "Multi-story residential",
                "area_sqft": 12500.0,
                "floors": 5,
                "stage": "Planning",
                "target_date": "2027-08-15",
                "currency": "INR"
            },
            {
                "id": "proj_metro_003",
                "name": "Metro Commercial Plaza",
                "city": "Gurugram",
                "type": "Commercial complex",
                "area_sqft": 8000.0,
                "floors": 3,
                "stage": "Structure",
                "target_date": "2027-05-30",
                "currency": "INR"
            }
        ]

        for p_data in real_projects:
            p = db.query(Project).filter(Project.id == p_data["id"]).first()
            if not p:
                p = Project(
                    id=p_data["id"],
                    organization_id="org_demo",
                    name=p_data["name"],
                    city=p_data["city"],
                    type=p_data["type"],
                    area_sqft=p_data["area_sqft"],
                    floors=p_data["floors"],
                    stage=p_data["stage"],
                    target_date=p_data["target_date"],
                    currency=p_data["currency"]
                )
                db.add(p)
            else:
                p.name = p_data["name"]
                p.city = p_data["city"]
                p.type = p_data["type"]
                p.area_sqft = p_data["area_sqft"]
                p.floors = p_data["floors"]
                p.stage = p_data["stage"]
                p.target_date = p_data["target_date"]
            db.commit()

        # Update any leftover old project stage names to clean enums
        for p in db.query(Project).all():
            if "foundation" in (p.stage or "").lower():
                p.stage = "Foundation"
            elif "planning" in (p.stage or "").lower():
                p.stage = "Planning"
            elif "structure" in (p.stage or "").lower():
                p.stage = "Structure"
            elif "finishing" in (p.stage or "").lower():
                p.stage = "Finishing"
        db.commit()

        print("Projects seeded with clean stages successfully:")
        for p in db.query(Project).all():
            print(f"- {p.id}: {p.name} ({p.city}) • Stage: {p.stage}")

    finally:
        db.close()

if __name__ == "__main__":
    seed_clean_projects()
