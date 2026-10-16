"""
SQLAlchemy Models for Construction Material Intelligence Platform.
Schema covers:
- users, organizations, project_members, sessions
- projects, boq_items, materials, suppliers, supplier_quotes
- marketplace_listings, climate_zones, risk_assessments, design_suggestions
- stock, open_orders, receipts, approvals, audit_log
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from python_app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

def utc_iso():
    return datetime.now(timezone.utc).isoformat()

def utc_date_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    users = relationship("User", back_populates="organization")
    projects = relationship("Project", back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(String(64), nullable=False, default="site_user") # 'contractor_owner', 'site_user'
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    organization = relationship("Organization", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(128), unique=True, index=True, nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    city = Column(String(128), nullable=False, default="Delhi")
    type = Column(String(128), default="Low-rise residential")
    area_sqft = Column(Float, default=2000.0)
    floors = Column(Integer, default=2)
    stage = Column(String(128), default="Planning and structure")
    target_date = Column(String(32), default="2027-01-31")
    currency = Column(String(16), default="INR")
    created_at = Column(DateTime, default=utc_now)

    organization = relationship("Organization", back_populates="projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    boq_items = relationship("BoqItem", back_populates="project", cascade="all, delete-orphan")
    quotes = relationship("SupplierQuote", back_populates="project", cascade="all, delete-orphan")
    stock_items = relationship("Stock", back_populates="project", cascade="all, delete-orphan")
    open_orders = relationship("OpenOrder", back_populates="project", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="project", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="project", cascade="all, delete-orphan")
    audit_events = relationship("AuditLog", back_populates="project", cascade="all, delete-orphan")

class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    role = Column(String(64), default="site_user")

    project = relationship("Project", back_populates="members")

class Material(Base):
    __tablename__ = "materials"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    category = Column(String(128), nullable=False)
    specification = Column(String(255))
    unit = Column(String(32), nullable=False)
    standard_rate = Column(Float, default=0.0)
    description = Column(Text)

class BoqItem(Base):
    __tablename__ = "boq_items"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    material_id = Column(String(64), nullable=False)
    material_name = Column(String(255), nullable=False)
    specification = Column(String(255))
    unit = Column(String(32), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    rate = Column(Float, default=0.0)
    days_until_required = Column(Integer, default=14)

    project = relationship("Project", back_populates="boq_items")

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    city = Column(String(128))
    contact_email = Column(String(255))
    contact_phone = Column(String(64))
    rating = Column(Float, default=4.5)
    tier = Column(String(64), default="Tier A")

class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    material_id = Column(String(64), nullable=False)
    supplier_id = Column(String(64), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    tax_rate = Column(Float, default=18.0)
    freight = Column(Float, default=0.0)
    handling = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    lead_time_days = Column(Integer, default=3)
    quote_date = Column(String(32), default=utc_date_str)

    project = relationship("Project", back_populates="quotes")

class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(String(64), primary_key=True)
    seller_name = Column(String(255), nullable=False)
    material_name = Column(String(255), nullable=False)
    specification = Column(String(255))
    category = Column(String(128), default="General") # 'Cement', 'Steel', 'Masonry', 'Aggregates', 'Timber', 'Fixtures'
    condition = Column(String(64), default="good") # 'brand_new', 'good', 'fair', 'poor'
    usable_fraction = Column(Float, default=0.88)
    usable_life_years = Column(Integer, default=15)
    quantity_available = Column(Float, default=100.0)
    price = Column(Float, nullable=False)
    tax_rate = Column(Float, default=5.0)
    freight = Column(Float, default=500.0)
    seller_location = Column(String(128), default="Delhi Yard")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    verified_grade = Column(String(64), default="AI Verified")
    test_certificate_available = Column(Boolean, default=False)
    requires_engineer_approval = Column(Boolean, default=False)
    photo_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utc_now)

class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    material_id = Column(String(64), nullable=False)
    quantity = Column(Float, default=0.0)

    project = relationship("Project", back_populates="stock_items")

class OpenOrder(Base):
    __tablename__ = "open_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    material_id = Column(String(64), nullable=False)
    quantity = Column(Float, default=0.0)
    expected_date = Column(String(32))

    project = relationship("Project", back_populates="open_orders")

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    material_id = Column(String(64), nullable=True)
    material_name = Column(String(255), nullable=True)
    supplier_id = Column(String(64), nullable=True)
    quantity = Column(Float, default=0.0)
    actual_unit_cost = Column(Float, default=0.0)
    invoice_number = Column(String(128), nullable=True)
    photo_url = Column(String(512), nullable=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(String(64), default=utc_iso)

    project = relationship("Project", back_populates="receipts")

class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    quote_id = Column(String(64), nullable=False)
    approved_by = Column(String(64), nullable=False)
    status = Column(String(32), default="approved")
    comments = Column(Text, nullable=True)
    created_at = Column(String(64), default=utc_iso)

    project = relationship("Project", back_populates="approvals")

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True)
    actor_user_id = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False)
    entity_id = Column(String(128), nullable=True)
    timestamp = Column(String(64), default=utc_iso)
    details = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="audit_events")

class ClimateZone(Base):
    __tablename__ = "climate_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(128), unique=True, nullable=False)
    seismic_zone = Column(String(32), nullable=False)
    wind_zone_speed = Column(Float, nullable=False)
    avg_rainfall_mm = Column(Float, nullable=False)
    exposure_class = Column(String(64), nullable=False)
    default_temp_c = Column(Float, default=30.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

class RiskAssessmentRecord(Base):
    __tablename__ = "risk_assessments"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), nullable=True)
    location = Column(String(128), nullable=False)
    building_age_years = Column(Integer, default=15)
    visible_damage_level = Column(String(64), default="moderate")
    risk_score_pct = Column(Float, nullable=False)
    risk_level = Column(String(64), nullable=False)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)

class DesignSuggestionRecord(Base):
    __tablename__ = "design_suggestions"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), nullable=True)
    orientation = Column(String(64), default="North-East")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    ventilation_strategy = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
