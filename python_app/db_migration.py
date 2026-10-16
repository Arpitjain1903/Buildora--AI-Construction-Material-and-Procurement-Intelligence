"""
Database Migration and Seed Utility.
Migrates data from legacy data/store.json to the database (SQLite/PostgreSQL)
and seeds standard users, marketplace listings, and climate zones.
"""

import json
from pathlib import Path
from datetime import datetime

from python_app.database import engine, SessionLocal, Base
from python_app.models import (
    Organization, User, Project, ProjectMember, BoqItem, Material,
    Supplier, SupplierQuote, Stock, OpenOrder, Receipt, Approval,
    AuditLog, MarketplaceListing, ClimateZone
)
from python_app.auth import hash_password
from python_app.climate_engine import REGIONAL_CLIMATE_DATABASE

ROOT_DIR = Path(__file__).resolve().parent.parent
STORE_JSON = ROOT_DIR / "data" / "store.json"

def init_and_migrate_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Seed Organization
        org = db.query(Organization).filter(Organization.id == "org_demo").first()
        if not org:
            org = Organization(id="org_demo", name="Demo Contractor Co.")
            db.add(org)
            db.commit()

        # 2. Seed Users
        owner = db.query(User).filter(User.email == "owner@demo.local").first()
        if not owner:
            owner = User(
                id="user_owner_001",
                organization_id="org_demo",
                name="Contractor Owner",
                email="owner@demo.local",
                role="contractor_owner",
                password_hash=hash_password("owner123", "demo-owner-salt")
            )
            db.add(owner)

        site_user = db.query(User).filter(User.email == "site@demo.local").first()
        if not site_user:
            site_user = User(
                id="user_site_001",
                organization_id="org_demo",
                name="Site Engineer",
                email="site@demo.local",
                role="site_user",
                password_hash=hash_password("site123", "demo-site-salt")
            )
            db.add(site_user)
        db.commit()

        # 3. Seed Climate Zones
        for reg in REGIONAL_CLIMATE_DATABASE:
            cz = db.query(ClimateZone).filter(ClimateZone.city == reg["city"]).first()
            if not cz:
                db.add(ClimateZone(
                    city=reg["city"],
                    seismic_zone=reg["seismic_zone"],
                    wind_zone_speed=float(reg["wind_zone_speed"]),
                    avg_rainfall_mm=float(reg["avg_rainfall_mm"]),
                    exposure_class=reg["exposure_class"],
                    default_temp_c=float(reg.get("default_temp_c", 30)),
                    latitude=float(reg.get("latitude", 28.0)),
                    longitude=float(reg.get("longitude", 77.0))
                ))
        db.commit()

        # 4. Migrate data from store.json if available
        if STORE_JSON.exists():
            try:
                with open(STORE_JSON, "r", encoding="utf-8") as f:
                    store_data = json.load(f)

                # Projects
                for p in store_data.get("projects", []):
                    if not db.query(Project).filter(Project.id == p["id"]).first():
                        db.add(Project(
                            id=p["id"],
                            organization_id="org_demo",
                            name=p["name"],
                            city=p.get("city", "Delhi"),
                            type=p.get("type", "Low-rise residential"),
                            area_sqft=float(p.get("areaSqFt", 2000)),
                            floors=int(p.get("floors", 2)),
                            stage=p.get("stage", "Foundation and structure"),
                            target_date=p.get("targetDate", "2027-01-31"),
                            currency=p.get("currency", "INR")
                        ))
                db.commit()

                # Project Memberships
                for uid in ["user_owner_001", "user_site_001"]:
                    for p in store_data.get("projects", []):
                        if not db.query(ProjectMember).filter(ProjectMember.project_id == p["id"], ProjectMember.user_id == uid).first():
                            db.add(ProjectMember(project_id=p["id"], user_id=uid, role="owner" if "owner" in uid else "site"))
                db.commit()

                # BOQ Items
                for b in store_data.get("boqLines", []):
                    if not db.query(BoqItem).filter(BoqItem.id == b["id"]).first():
                        db.add(BoqItem(
                            id=b["id"],
                            project_id=b["projectId"],
                            material_id=b["materialId"],
                            material_name=b["materialName"],
                            specification=b.get("specification", ""),
                            unit=b["unit"],
                            quantity=float(b["quantity"]),
                            rate=float(b.get("rate", 0)),
                            days_until_required=int(b.get("daysUntilRequired", 14))
                        ))
                db.commit()

                # Quotes
                for q in store_data.get("quotes", []):
                    if not db.query(SupplierQuote).filter(SupplierQuote.id == q["id"]).first():
                        db.add(SupplierQuote(
                            id=q["id"],
                            project_id=q["projectId"],
                            material_id=q["materialId"],
                            supplier_id=q["supplierId"],
                            supplier_name=q["supplierName"],
                            quantity=float(q["quantity"]),
                            unit_price=float(q["unitPrice"]),
                            tax_rate=float(q.get("taxRate", 18.0)),
                            freight=float(q.get("freight", 0.0)),
                            handling=float(q.get("handling", 0.0)),
                            discount=float(q.get("discount", 0.0)),
                            lead_time_days=int(q.get("leadTimeDays", 3)),
                            quote_date=q.get("quoteDate", "2026-09-18")
                        ))
                db.commit()

                # Stock
                for s in store_data.get("stock", []):
                    existing = db.query(Stock).filter(Stock.project_id == s["projectId"], Stock.material_id == s["materialId"]).first()
                    if not existing:
                        db.add(Stock(
                            project_id=s["projectId"],
                            material_id=s["materialId"],
                            quantity=float(s["quantity"])
                        ))
                db.commit()

                # Open Orders
                for o in store_data.get("openOrders", []):
                    existing = db.query(OpenOrder).filter(OpenOrder.project_id == o["projectId"], OpenOrder.material_id == o["materialId"]).first()
                    if not existing:
                        db.add(OpenOrder(
                            project_id=o["projectId"],
                            material_id=o["materialId"],
                            quantity=float(o["quantity"]),
                            expected_date=o.get("expectedDate")
                        ))
                db.commit()
            except Exception as e:
                print(f"Store migration warning: {e}")

        # 5. Seed sample marketplace listings
        sample_listings = [
            {
                "id": "mkt_cem_001",
                "seller_name": "Surplus Building Depot",
                "material_name": "Cement OPC 53 Grade",
                "specification": "50kg bag, fresh sealed surplus",
                "category": "Cement",
                "condition": "good",
                "usable_fraction": 0.90,
                "usable_life_years": 1,
                "quantity_available": 350.0,
                "price": 290.0,
                "tax_rate": 5.0,
                "freight": 400.0,
                "seller_location": "Narela Mandi, Delhi",
                "verified_grade": "AI Verified Grade A"
            },
            {
                "id": "mkt_steel_001",
                "seller_name": "Metro Reclaim Yard",
                "material_name": "TMT Steel Rebar 12mm Fe500",
                "specification": "Surplus uncut factory lengths with test mill cert",
                "category": "Steel",
                "condition": "good",
                "usable_fraction": 0.95,
                "usable_life_years": 40,
                "quantity_available": 4500.0,
                "price": 48.0,
                "tax_rate": 5.0,
                "freight": 2000.0,
                "seller_location": "Mayapuri, Delhi",
                "verified_grade": "Certified with Mill Test Certificate"
            },
            {
                "id": "mkt_aac_001",
                "seller_name": "Precast & Masonry Surplus",
                "material_name": "AAC Blocks 600x200x150",
                "specification": "Unused site surplus pallets",
                "category": "Masonry",
                "condition": "good",
                "usable_fraction": 0.92,
                "usable_life_years": 50,
                "quantity_available": 1200.0,
                "price": 42.0,
                "tax_rate": 5.0,
                "freight": 3500.0,
                "seller_location": "Bhiwadi Yard",
                "verified_grade": "AI Inspected"
            }
        ]

        for item in sample_listings:
            if not db.query(MarketplaceListing).filter(MarketplaceListing.id == item["id"]).first():
                db.add(MarketplaceListing(**item))
        db.commit()

    finally:
        db.close()

if __name__ == "__main__":
    init_and_migrate_db()
    print("Database initialization and migration completed successfully.")
