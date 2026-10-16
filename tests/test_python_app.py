"""
Comprehensive Pytest Suite for Python Construction Material Intelligence Platform
"""

import pytest
from fastapi.testclient import TestClient

from python_app.climate_engine import analyze_climate_and_location, lookup_regional_climate, determine_curing_schedule
from python_app.quantity_estimator import calculate_steel_bar_weight_per_meter, estimate_project_quantities, parse_project_description_text, QuantityCalibratorML
from python_app.marketplace_engine import calculate_cosine_similarity, match_material_name, rank_marketplace_offers, grade_material_photo
from python_app.design_engine import calculate_ventilation_requirements, generate_layout_design_suggestions, adjust_material_quantities_from_design
from python_app.risk_assessment_engine import calculate_renovation_risk_score, assess_renovation_risk
from python_app.ml_analytics import PriceTrendForecaster, calculate_supplier_reliability_score, detect_overinvoicing_anomalies
from python_app.main import app

client = TestClient(app)

# --- Module 3 Tests ---
def test_climate_regional_lookup():
    reg = lookup_regional_climate("Delhi")
    assert reg["seismic_zone"] == "Zone IV"
    assert reg["wind_zone_speed"] == 47

def test_climate_analysis_exposure_rules():
    res = analyze_climate_and_location(location="Mumbai", temp_override=38.0)
    assert res["exposure_class"] == "Severe"
    assert res["min_cement_kg_m3"] == 320
    assert res["max_wc_ratio"] == 0.45
    assert res["curing_schedule"]["min_days"] == 10 # Hot climate (>35C)

# --- Module 1 Tests ---
def test_steel_bar_weight_formula():
    assert calculate_steel_bar_weight_per_meter(12) == 0.889
    assert calculate_steel_bar_weight_per_meter(16) == 1.58
    assert calculate_steel_bar_weight_per_meter(8) == 0.395

def test_quantity_estimation_formulas():
    res = estimate_project_quantities(area_sqft=2000, floors=2, mix_ratio_str="1:1.5:3", location="Delhi")
    q = res["quantities"]
    assert q["cement_bags"] > 0
    assert q["steel_kg"] > 0
    assert q["sand_m3"] > 0
    assert q["aggregate_m3"] > 0
    assert res["disclaimer"] == "Estimate only — final reinforcement design requires a licensed structural engineer (IS 456 limit state method)."

def test_free_text_parser():
    parsed = parse_project_description_text("Construct a 2500 sqft 3 floor building in Bengaluru with budget of 45 lakhs")
    assert parsed["area_sqft"] == 2500
    assert parsed["floors"] == 3
    assert parsed["location"] == "Bengaluru"
    assert parsed["budget"] == 4500000.0

def test_quantity_ml_calibrator():
    calibrator = QuantityCalibratorML()
    history = [
        {"area_sqft": 1000, "floors": 1, "mix_ratio_num": 5.5, "actual_cement": 250, "actual_steel": 1800},
        {"area_sqft": 2000, "floors": 2, "mix_ratio_num": 5.5, "actual_cement": 480, "actual_steel": 3600}
    ]
    calibrator.train_on_history(history)
    calibrated = calibrator.calibrate(1500, 2, 5.5, 380, 2700)
    assert "calibrated_cement_bags" in calibrated
    assert "calibrated_steel_kg" in calibrated

# --- Module 2 Tests ---
def test_cosine_similarity():
    sim1 = calculate_cosine_similarity("Ultratech OPC 53 Cement", "Cement 53 OPC Ultratech")
    assert sim1 >= 0.85

    sim2 = calculate_cosine_similarity("Ultratech OPC 53 Cement", "TMT Steel Rebar 12mm")
    assert sim2 < 0.40

def test_marketplace_material_matching_and_ranking():
    listings = [
        {"material_name": "Cement OPC 53", "specification": "50kg bag"},
        {"material_name": "TMT Steel Bar", "specification": "12mm"}
    ]
    matched = match_material_name("Ultratech OPC 53 Cement", listings, 0.85)
    assert matched[0]["auto_matched"] is True

    ranked = rank_marketplace_offers(
        query_quantity=50,
        new_quotes=[{"id": "q1", "unitPrice": 410, "taxRate": 18, "freight": 1000}],
        reused_listings=[{"id": "r1", "price": 280, "tax_rate": 5, "freight": 300, "quantity_available": 50}]
    )
    assert ranked[0]["id"] == "r1" # Reused material cheaper
    assert ranked[0]["savings_vs_new"] > 0

# --- Module 5 Tests ---
def test_ventilation_and_design_suggestions():
    vent = calculate_ventilation_requirements(area_sqft=2000, floors=2)
    assert vent["min_window_area_sqft"] == 400.0 # 10% of 4000 sqft

    suggestions = generate_layout_design_suggestions(area_sqft=2000, floors=2)
    assert len(suggestions["suggestions"]) >= 3

# --- Module 4 Tests ---
def test_renovation_risk_assessment():
    res = assess_renovation_risk(location="Delhi", building_age_years=25, visible_damage_level="severe")
    assert res["risk_assessment"]["risk_score_pct"] > 50.0
    assert len(res["repair_bill"]["repair_materials"]) > 0

# --- Section 6 ML Analytics Tests ---
def test_ml_analytics():
    forecaster = PriceTrendForecaster()
    forecast = forecaster.forecast_price_trend(current_price=410.0, monsoon_flag=True)
    assert forecast["forecast_90_days"] >= 410.0

    reliability = calculate_supplier_reliability_score(on_time_delivery_pct=95.0, defect_rate_pct=1.0)
    assert reliability["reliability_score"] >= 85.0
    assert "Tier A" in reliability["tier"]

    anomalies = detect_overinvoicing_anomalies([
        {"supplier": "A", "delivered_unit_cost": 410},
        {"supplier": "B", "delivered_unit_cost": 415},
        {"supplier": "C", "delivered_unit_cost": 950} # Anomaly over-invoiced
    ], z_threshold=1.5)
    assert anomalies[2]["is_anomaly"] is True

# --- FastAPI Route Integration Tests ---
def test_fastapi_endpoints():
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["ok"] is True

    res_pipeline = client.post("/api/pipeline/run", json={
        "area_sqft": 2000,
        "floors": 2,
        "location": "Delhi"
    })
    assert res_pipeline.status_code == 200
    data = res_pipeline.json()
    assert data["status"] == "success"
    assert "module_3_climate" in data
    assert "module_1_quantities" in data
    assert "module_5_design" in data
    assert "module_2_marketplace" in data
    assert "module_4_renovation_risk" in data
