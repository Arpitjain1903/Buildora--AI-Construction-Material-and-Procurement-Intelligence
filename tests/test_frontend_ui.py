"""
Unit and Integration Tests for Frontend UI (Task J),
Wizard Flow, Multi-Photo Upload, and Leaflet Map Integration.
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from python_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_frontend_index_html_served_at_root(client):
    """Verify that public/index.html is served statically at the root URL."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "<title>Buildora" in html or "<title>Buildora AI" in html or "<title>ConstructIntel" in html or "<title>Datum" in html
    assert "Leaflet" in html or "leaflet.css" in html
    assert "OpenStreetMap" in html


def test_frontend_ui_elements_present():
    """Verify that all required Task J UI elements are present in index.html."""
    html_path = Path(__file__).resolve().parent.parent / "public" / "index.html"
    assert html_path.exists(), "public/index.html must exist"
    content = html_path.read_text(encoding="utf-8")

    # 1. Project Wizard & AI parser elements
    assert "wizFreeText" in content, "Free text project intake element missing"
    assert "btnParseText" in content, "Parse text action button missing"
    assert "wizConfirmationArea" in content, "Confirmation modal/banner area missing"
    assert "STATUTORY ENGINEERING DISCLAIMER" in content, "Statutory disclaimer banner missing"

    # 2. Leaflet Map container & scripts
    assert "id=\"hazardMap\"" in content or "id='hazardMap'" in content, "Hazard map container missing"
    assert "leaflet.js" in content, "Leaflet JS script missing"
    assert "leaflet.css" in content, "Leaflet CSS missing"
    assert "tileLayer" in content, "OpenStreetMap tile layer setup missing"

    # 3. Multi-Photo upload & canvas resize
    assert "fileToResizedBase64" in content, "Client-side canvas image downscaler missing"
    assert "mktPhotoInput" in content, "Marketplace photo input missing"
    assert "renPhotoInput" in content, "Renovation damage photo input missing"
    assert "multiple" in content, "Multiple file attribute missing"

    # 4. Category safety enforcement
    assert "cementWarningBanner" in content or "Used cement cannot be accepted" in content, "Cement safety warning missing"

    # 5. Mandatory structural engineer warning
    assert "engineer-alert" in content or "qualified structural engineer" in content, "Structural engineer alert missing"

    # 6. Source and verified badges
    assert "sourceBadge" in content, "AI vs Fallback source badge logic missing"
    assert "verifiedBadge" in content, "Verified citation badge logic missing"


def test_wizard_api_flow(client):
    """Test the backend API that backs the Project Wizard intake."""
    # 1. Normal project text
    res = client.post("/api/materials/parse-text", json={
        "user_text": "Build a 2000 sqft 2 floor house in Mumbai with a budget of 40 lakhs"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["parsed"]["area_sqft"] == 2000.0
    assert data["parsed"]["floors"] == 2
    assert "Mumbai" in data["parsed"]["location"]
    assert "source" in data
    assert "disclaimer" in data

    # 2. Project text requiring confirmation (out of range or ambiguous)
    res_ambiguous = client.post("/api/materials/parse-text", json={
        "user_text": "Construct a small kiosk of 50 sqft"
    })
    assert res_ambiguous.status_code == 200
    amb_data = res_ambiguous.json()
    assert amb_data["needs_confirmation"] is True
    assert "area_sqft" in amb_data["confirmation_message"].lower() or "bounds" in amb_data["confirmation_message"].lower() or "confirm" in amb_data["confirmation_message"].lower()


def test_photo_upload_grading_api_flow(client):
    """Test backend photo grading supporting 1-5 photos and category rules."""
    dummy_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    
    # 1. Multiple photos for steel
    res = client.post("/api/marketplace/grade-photo", json={
        "images": [dummy_b64, dummy_b64],
        "category": "steel",
        "material_type": "TMT Rebar Fe500"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["condition"] in ["good", "fair", "poor"]
    assert data["usable_fraction"] >= 0.20
    assert "source" in data
    assert "disclaimer" in data

    # 2. Used cement category rule enforcement
    res_cement = client.post("/api/marketplace/grade-photo", json={
        "images": [dummy_b64],
        "category": "cement",
        "material_type": "Used OPC 53"
    })
    assert res_cement.status_code == 200
    cement_data = res_cement.json()
    assert cement_data["usable_fraction"] == 0.0
    assert "prohibited" in cement_data["reason"].lower() or "never permitted" in cement_data["reason"].lower()


def test_renovation_photo_damage_api_flow(client):
    """Test renovation damage detection with structural engineer alert."""
    dummy_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    
    res = client.post("/api/renovation/assess", json={
        "location": "Delhi",
        "building_age_years": 30,
        "visible_damage_level": "severe",
        "damage_photos": [dummy_b64]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["risk_assessment"]["requires_structural_engineer_inspection"] is True
    assert data["engineer_inspection_required"] is True
    assert "engineer" in (data.get("prominent_warning") or "").lower()
    assert "source" in data
    assert "disclaimer" in data


def test_hazard_lookup_api_flow_with_overrides(client):
    """Test hazard lookup API with Leaflet coordinate query and manual overrides."""
    # 1. Standard coordinate lookup
    res = client.post("/api/climate/hazard-lookup", json={
        "lat": 19.0760,
        "long": 72.8777
    })
    assert res.status_code == 200
    data = res.json()
    assert "Mumbai" in data["nearest_reference_city"]
    assert data["seismic_zone"] == "Zone III"
    assert data["seismic_verified"] is True

    # 2. Manual override
    res_ovr = client.post("/api/climate/hazard-lookup", json={
        "lat": 19.0760,
        "long": 72.8777,
        "seismic_zone_override": "Zone V",
        "wind_zone_speed_override": 55.0,
        "exposure_class_override": "Extreme"
    })
    assert res_ovr.status_code == 200
    ovr_data = res_ovr.json()
    assert ovr_data["seismic_zone"] == "Zone V"
    assert ovr_data["seismic_verified"] is False
    assert "User Manual Override" in ovr_data["seismic_source"]
    assert ovr_data["wind_zone_speed"] == 55.0
    assert ovr_data["exposure_class"] == "Extreme"


def test_playwright_browser_wizard_flow():
    """Playwright E2E browser test verifying wizard render and interaction in headless Chromium."""
    from playwright.sync_api import sync_playwright

    html_file = Path(__file__).resolve().parent.parent / "public" / "index.html"
    file_url = f"file:///{html_file.as_posix()}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(file_url)

        # Check title and brand
        assert "Buildora" in page.title() or "Buildora AI" in page.title() or "ConstructIntel" in page.title() or "Datum" in page.title()

        # Hide login modal to allow clicks
        page.evaluate("() => hideLogin()")

        # Check tabs exist
        assert page.locator("#tab-wizard").is_visible()
        assert page.locator("#tab-takeoff").is_visible()
        assert page.locator("#tab-marketplace").is_visible()
        assert page.locator("#tab-climate").is_visible()
        assert page.locator("#tab-renovation").is_visible()

        # Switch to climate tab and check map container
        page.click("#tab-climate")
        page.wait_for_timeout(500)
        assert page.locator("#hazardMap").is_visible()

        # Switch to marketplace tab and check photo upload dropzone
        page.click("#tab-marketplace")
        assert page.locator(".photo-dropzone").is_visible()

        # Select cement category and verify the safety warning appears
        page.select_option("#gradeCategory", "cement")
        assert page.locator("#cementWarningBanner").is_visible()

        browser.close()

