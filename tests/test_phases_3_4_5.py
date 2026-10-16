"""
Pytest Suite for Phase 3 (Geospatial Location Intelligence),
Phase 4 (Repair & Renovation Planner Specialized Flows),
and Phase 5 (Marketplace Supply-Side Category Safety Rules & Distance).
"""

import pytest
from python_app.climate_engine import lookup_climate_by_coordinates
from python_app.risk_assessment_engine import generate_specialized_repair_plan
from python_app.marketplace_engine import (
    calculate_haversine_distance,
    validate_marketplace_listing_rules
)

def test_phase3_coordinate_lookup_and_cache():
    """Verifies GPS lat/long lookup for seismic zone, wind, rainfall, and caching."""
    # Near Mumbai coordinates (19.07, 72.87)
    res = lookup_climate_by_coordinates(19.076, 72.877)
    assert res["nearest_reference_city"] == "Mumbai"
    assert res["seismic_zone"] == "Zone III"
    assert res["wind_zone_speed"] == 44
    assert res["avg_rainfall_mm"] == 2400
    assert res["flood_prone"] is True
    assert res["is_cached"] is True

    # Repeated query retrieves from cache
    res_cached = lookup_climate_by_coordinates(19.076, 72.877)
    assert res_cached["nearest_reference_city"] == "Mumbai"

def test_phase4_specialized_repair_earthquake():
    """Verifies earthquake damage repair flow (IS 13935:2009, epoxy, micro-concrete, CFRP)."""
    plan = generate_specialized_repair_plan("earthquake", risk_data={"risk_score_pct": 75.0}, wall_area_m2=150.0)
    assert "IS 13935:2009" in plan["protocol"]
    assert len(plan["retrofit_recommendations"]) >= 3
    assert len(plan["repair_materials"]) >= 3

    mat_ids = [m["material_id"] for m in plan["repair_materials"]]
    assert "repair_micro_concrete" in mat_ids
    assert "repair_epoxy_grout" in mat_ids
    assert "repair_cfrp_wrap" in mat_ids
    assert "CONSERVATIVE ENGINEERING NOTICE" in plan["disclaimer"]

def test_phase4_specialized_repair_flood():
    """Verifies flood damage flow (subsoil drainage, biocide, crystalline DPC)."""
    plan = generate_specialized_repair_plan("flood", wall_area_m2=100.0)
    assert "Flood Foundation Drainage" in plan["protocol"]
    mat_ids = [m["material_id"] for m in plan["repair_materials"]]
    assert "repair_biocide" in mat_ids
    assert "repair_crystalline_dpc" in mat_ids
    assert "repair_drain_pipe" in mat_ids

def test_phase4_specialized_repair_rain_leakage():
    """Verifies rain leakage and dampness flow (silane-siloxane DPC, elastomeric membrane)."""
    plan = generate_specialized_repair_plan("rain_leakage", wall_area_m2=100.0)
    assert "Capillary Dampness" in plan["protocol"]
    mat_ids = [m["material_id"] for m in plan["repair_materials"]]
    assert "repair_dpc_cream" in mat_ids
    assert "repair_pu_sealant" in mat_ids
    assert "repair_waterproofing" in mat_ids

def test_phase5_marketplace_category_rule_used_cement_blocked():
    """Verifies that used or opened cement cannot be listed under safety policy (IS 456 / IS 269)."""
    with pytest.raises(ValueError, match="Safety Policy Violation"):
        validate_marketplace_listing_rules({
            "category": "Cement",
            "material_name": "Ultratech OPC 53 Cement",
            "condition": "fair" # used / opened cement is forbidden
        })

    # Brand new cement surplus is allowed
    ok_listing = validate_marketplace_listing_rules({
        "category": "Cement",
        "material_name": "Ultratech OPC 53 Cement",
        "condition": "brand_new"
    })
    assert ok_listing["requires_engineer_approval"] is False

def test_phase5_marketplace_category_rule_salvaged_steel():
    """Verifies that salvaged steel requires mill test certificate and engineer approval."""
    # Without test certificate -> rejected
    with pytest.raises(ValueError, match="Quality Policy"):
        validate_marketplace_listing_rules({
            "category": "Steel",
            "material_name": "TMT Rebar 16mm",
            "condition": "good",
            "test_certificate_available": False
        })

    # With test certificate -> allowed, but flagged for engineer approval
    valid_steel = validate_marketplace_listing_rules({
        "category": "Steel",
        "material_name": "TMT Rebar 16mm",
        "condition": "good",
        "test_certificate_available": True
    })
    assert valid_steel["requires_engineer_approval"] is True

def test_phase5_haversine_distance():
    """Verifies Haversine GPS distance calculation."""
    # Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777) is ~1148 km
    dist = calculate_haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1140.0 <= dist <= 1160.0
