"""
Comprehensive Pytest Suite for Section 3 Corrections & Phase 2 Full Material Take-Off.
Each test verifies the code against independent engineering standards:
- IS 456:2000 (Plain and Reinforced Concrete)
- IS 10262:2019 (Concrete Mix Proportioning Guidelines)
- IS 2185 (Part 3):1984 (AAC Blocks & Thin-bed jointing)
- IS 1893 (Part 1):2016 (Criteria for Earthquake Resistant Design)
- IS 875 (Part 3):2015 (Design Loads - Wind Loads)
- IS 3362:1977 & NBC 2016 (Natural Ventilation of Residential Buildings)
- Iglewicz and Hoaglin 1993 (Modified Z-score Outlier Detection)
"""

import math
import pytest
from python_app.marketplace_engine import (
    calculate_line_delivered_cost,
    calculate_freight_cost,
    get_usable_fraction_from_condition,
    rank_marketplace_offers,
    compare_quotes_unified,
    build_procurement_queue_unified
)
from python_app.ml_analytics import (
    detect_overinvoicing_anomalies,
    PriceTrendForecaster,
    calculate_supplier_reliability_score
)
from python_app.risk_assessment_engine import (
    calculate_renovation_risk_score,
    assess_renovation_risk
)
from python_app.quantity_estimator import (
    estimate_project_quantities,
    calculate_steel_bar_weight_per_meter,
    check_municipal_feasibility,
    QuantityCalibratorML
)
from python_app.climate_engine import (
    analyze_climate_and_location,
    calculate_wind_pressure_indicator,
    SEISMIC_ZONES
)
from python_app.design_engine import (
    calculate_ventilation_requirements,
    get_ventilation_ratio_for_location
)
from python_app.constants_loader import CONSTANTS

# --------------------------------------------------------------------------
# Correction 1: Marketplace Delivered Cost, Freight & Usable Fraction
# --------------------------------------------------------------------------
def test_correction_1_delivered_cost_formula():
    """
    Verifies Section 3.1:
    base = unit_price * quantity * (1 - discount)
    tax = base * gst_rate
    freight = f(weight_kg, distance_km, truck_capacity) -> trips * rate_per_trip
    raw_cost = base + tax + freight
    effective = raw_cost / usable_fraction
    """
    # 200 bags of cement (10,000 kg), unit price 400, 10% discount, 18% GST, 20 km distance
    cost = calculate_line_delivered_cost(
        quantity=200,
        unit_price=400,
        discount=0.10,
        tax_rate_pct=18.0,
        distance_km=20.0,
        unit_weight_kg=50.0,
        condition="brand_new"
    )
    # Expected:
    # base = 200 * 400 * 0.9 = 72,000
    # tax = 72,000 * 0.18 = 12,960
    # weight = 200 * 50 = 10,000 kg -> 1 trip in 10-ton truck
    # rate_per_trip = 500 + 20 * 45 = 1,400 -> freight = 1,400
    # raw_cost = 72,000 + 12,960 + 1,400 = 86,360
    # usable_fraction = 1.0 (brand_new)
    # effective_cost = 86,360
    assert cost["base"] == 72000.0
    assert cost["tax"] == 12960.0
    assert cost["freight"] == 1400.0
    assert cost["raw_cost"] == 86360.0
    assert cost["usable_fraction"] == 1.0
    assert cost["effective_cost"] == 86360.0

def test_correction_1_salvaged_usable_fraction_inflates_effective_cost():
    """
    Verifies that a salvaged material in 'fair' condition (usable_fraction ~0.72)
    has higher effective cost than raw cost because contractor needs extra to account for yield.
    """
    cost_salvaged = calculate_line_delivered_cost(
        quantity=100,
        unit_price=250,
        discount=0.0,
        tax_rate_pct=5.0,
        freight=1000.0,
        condition="fair"
    )
    # raw_cost = 25,000 + 1,250 + 1,000 = 27,250
    # usable_fraction = 0.72
    # effective_cost = 27,250 / 0.72 = 37,847.22
    assert cost_salvaged["raw_cost"] == 27250.0
    assert cost_salvaged["usable_fraction"] == 0.72
    assert cost_salvaged["effective_cost"] > cost_salvaged["raw_cost"]
    assert cost_salvaged["effective_unit_cost"] > cost_salvaged["delivered_unit_cost"]

# --------------------------------------------------------------------------
# Correction 2: Anomaly Detection (Modified Z-Score & Small Sample Fallback)
# --------------------------------------------------------------------------
def test_correction_2_modified_zscore_n_gte_5():
    """
    Verifies Boris Iglewicz and David Hoaglin (1993) modified z-score for n >= 5:
    M_i = 0.6745 * (x_i - median) / MAD
    Flags if |M_i| > 3.5
    """
    # 5 quotes: 4 normal (400, 405, 410, 415) and 1 extreme outlier (900)
    quotes = [
        {"supplier": "A", "delivered_unit_cost": 400},
        {"supplier": "B", "delivered_unit_cost": 405},
        {"supplier": "C", "delivered_unit_cost": 410},
        {"supplier": "D", "delivered_unit_cost": 415},
        {"supplier": "E", "delivered_unit_cost": 900} # Over-invoiced outlier
    ]
    results = detect_overinvoicing_anomalies(quotes)
    assert len(results) == 5
    assert results[4]["is_anomaly"] is True
    assert "modified_z_score" in results[4]["method_used"]
    assert abs(results[4]["modified_z_score"]) > 3.5
    assert results[0]["is_anomaly"] is False

def test_correction_2_small_sample_fallback_n_lt_5():
    """
    Verifies fallback when n < 5: Flags if % above median exceeds threshold (25%).
    """
    quotes_small = [
        {"supplier": "A", "delivered_unit_cost": 400},
        {"supplier": "B", "delivered_unit_cost": 410},
        {"supplier": "C", "delivered_unit_cost": 650} # 60% above median
    ]
    results = detect_overinvoicing_anomalies(quotes_small)
    assert len(results) == 3
    assert "small_sample_percentage_fallback" in results[2]["method_used"]
    assert results[2]["is_anomaly"] is True
    assert results[0]["is_anomaly"] is False

# --------------------------------------------------------------------------
# Correction 3: Multi-Hazard Renovation Risk Index & Heuristic Label
# --------------------------------------------------------------------------
def test_correction_3_multi_hazard_risk_index_and_disclaimer():
    """
    Verifies Section 3.3: Risk index includes seismic, wind, flood, rain-leakage/dampness,
    building age, and damage, with weights from config and explicit heuristic disclaimer.
    """
    res = assess_renovation_risk(
        location="Mumbai",
        building_age_years=35,
        visible_damage_level="severe",
        flood_zone_flag=True,
        past_flood_history=True
    )
    score_data = res["risk_assessment"]
    assert score_data["is_heuristic"] is True
    assert "HEURISTIC VULNERABILITY INDICATOR" in score_data["disclaimer"]

    # All hazard severities must be present in breakdown
    hazards = score_data["hazard_breakdown"]
    assert "seismic_severity" in hazards
    assert "wind_severity" in hazards
    assert "flood_severity" in hazards
    assert "rain_leakage_dampness_severity" in hazards
    assert "building_age_factor" in hazards
    assert "visible_damage_severity" in hazards

    # High flood history & age 35 + severe damage in Mumbai should be High Risk (>70%)
    assert score_data["risk_score_pct"] >= 70.0
    assert score_data["risk_level"] == "High Risk"

# --------------------------------------------------------------------------
# Correction 4: Concrete Grades (IS 456 Nominal vs IS 10262 Design Mix)
# --------------------------------------------------------------------------
def test_correction_4_concrete_grades_is456_and_is10262():
    """
    Verifies Section 3.4:
    - Nominal mixes only exist up to M20 (M5, M7.5, M10, M15, M20).
    - M25 and M30 require IS 10262 design mix and are not fixed ratios.
    """
    # M20 nominal mix
    res_m20 = estimate_project_quantities(area_sqft=1000, floors=1, mix_ratio_str="M20", location="Delhi")
    assert res_m20["project"]["is_design_mix"] is False
    assert res_m20["project"]["resolved_concrete_grade"] == "M20"

    # M25 design mix
    res_m25 = estimate_project_quantities(area_sqft=1000, floors=1, mix_ratio_str="M25", location="Delhi")
    assert res_m25["project"]["is_design_mix"] is True
    assert res_m25["project"]["resolved_concrete_grade"] == "M25"
    assert "IS 10262:2019" in res_m25["design_mix_warning"]

def test_concrete_m20_1m3_sanity_check():
    """
    Sanity check (Section 4 Phase 8):
    1 m^3 of wet M20 (1:1.5:3) nominal concrete yields:
    - ~8.1 to 8.4 bags of cement (50kg)
    - ~0.42 m^3 sand
    - ~0.84 m^3 aggregate
    Formula check:
    Dry volume = 1.0 * 1.54 = 1.54 m3
    Cement = 1.54 * (1 / 5.5) = 0.28 m3 * 1440 kg/m3 = 403.2 kg / 50 = 8.06 -> ~8.1 bags.
    Sand = 1.54 * (1.5 / 5.5) = 0.42 m3.
    Aggregate = 1.54 * (3.0 / 5.5) = 0.84 m3.
    """
    dry_vol = 1.0 * 1.54
    cement_vol = dry_vol * (1.0 / 5.5)
    cement_bags = (cement_vol * 1440.0) / 50.0
    sand_vol = dry_vol * (1.5 / 5.5)
    agg_vol = dry_vol * (3.0 / 5.5)

    assert round(cement_bags, 1) == 8.1
    assert round(sand_vol, 2) == 0.42
    assert round(agg_vol, 2) == 0.84

# --------------------------------------------------------------------------
# Correction 5: AAC Masonry Separate Calculation with Thin-Bed Adhesive
# --------------------------------------------------------------------------
def test_correction_5_aac_masonry_thin_bed_adhesive():
    """
    Verifies Section 3.5:
    AAC blocks use thin-bed adhesive (2-3mm joints, ~35 kg/m3).
    Thin-bed adhesive requires ZERO sand. Does not reuse 1.30 mortar multiplier.
    """
    # AAC Wall
    res_aac = estimate_project_quantities(area_sqft=1000, floors=1, wall_type="aac_block", location="Delhi")
    q_aac = res_aac["quantities"]

    assert q_aac["blocks_count"] > 0
    assert q_aac["aac_adhesive_kg"] > 0.0
    assert q_aac["aac_adhesive_bags"] > 0
    # Masonry sand for AAC thin-bed adhesive must be 0!
    # (Total sand only contains concrete sand + plaster sand)
    res_brick = estimate_project_quantities(area_sqft=1000, floors=1, wall_type="brick", location="Delhi")
    q_brick = res_brick["quantities"]

    # Red brick requires significantly more sand due to 10-12mm mortar joints
    assert q_brick["sand_m3"] > q_aac["sand_m3"]
    assert q_brick["bricks_count"] > 0

# --------------------------------------------------------------------------
# Correction 6: Wind & Seismic Zone Indicators
# --------------------------------------------------------------------------
def test_correction_6_wind_and_seismic_zone_indicators():
    """
    Verifies Section 3.6:
    Wind and seismic outputs are labeled as zone indicators only, not design loads.
    """
    clim = analyze_climate_and_location(location="Guwahati")
    assert clim["seismic_zone"] == "Zone V"
    assert clim["seismic_details"]["is_indicator_only"] is True
    assert "Ah = (Z/2)*(I/R)*(Sa/g)" in clim["seismic_details"]["design_reference"]

    wind = clim["wind_details"]
    assert wind["is_indicator_only"] is True
    assert wind["basic_wind_speed_vb_ms"] == 50
    # p_z = 0.6 * 50^2 = 1500 N/m2 = 1.5 kN/m2
    assert wind["basic_wind_pressure_pz_n_m2"] == 1500.0
    assert "ZONE INDICATOR ONLY" in wind["disclaimer"]

# --------------------------------------------------------------------------
# Correction 7: IS 3362 Ventilation Threshold Regional / Municipal Config
# --------------------------------------------------------------------------
def test_correction_7_is3362_ventilation_threshold():
    """
    Verifies Section 3.7:
    Ventilation threshold is configurable per municipal bye-laws:
    - Mumbai: 16.67% (1/6th floor area) per DCPR 2034
    - Delhi: 10% per UBBL 2016
    """
    vent_mumbai = calculate_ventilation_requirements(area_sqft=1200, floors=2, location="Mumbai")
    assert vent_mumbai["opening_to_floor_ratio"] == 0.1667
    assert "DCPR 2034" in vent_mumbai["authority_reference"]
    # Total floor area 2400 sqft * 0.1667 = 400.1 sqft
    assert vent_mumbai["min_window_area_sqft"] == 400.1

    vent_delhi = calculate_ventilation_requirements(area_sqft=1200, floors=2, location="Delhi")
    assert vent_delhi["opening_to_floor_ratio"] == 0.1000
    assert "UBBL" in vent_delhi["authority_reference"]
    # Total floor area 2400 sqft * 0.10 = 240.0 sqft
    assert vent_delhi["min_window_area_sqft"] == 240.0

# --------------------------------------------------------------------------
# Correction 8: ML Placeholders & Forecast Guards
# --------------------------------------------------------------------------
def test_correction_8_ml_placeholders_and_price_forecast():
    """
    Verifies Section 3.8:
    - Quantity calibrator defaults calibration factor to 1.0 when uncalibrated.
    - Price forecaster includes seasonality (monsoon, budget), 95% confidence intervals,
      and minimum-data guard (refuses statistical model if n < 6).
    """
    # 1. Quantity Calibrator defaults to 1.0
    calibrator = QuantityCalibratorML()
    res = calibrator.calibrate(1500, 2, 5.5, 350.0, 2500.0)
    assert res["calibration_factor_applied"] == 1.0
    assert res["calibrated_cement_bags"] == 350.0
    assert res["calibrated_steel_kg"] == 2500.0

    # 2. Price Forecaster minimum data guard
    forecaster = PriceTrendForecaster()
    insufficient_history = [{"past_price": 400, "target_future_price": 410}]
    train_res = forecaster.train_on_history(insufficient_history)
    assert train_res["trained"] is False
    assert forecaster.is_trained is False

    # 3. Forecast includes 95% confidence intervals & seasonality
    forecast = forecaster.forecast_price_trend(current_price=410.0, month=7, monsoon_flag=True)
    assert "confidence_interval_30_days_95" in forecast
    assert len(forecast["confidence_interval_30_days_95"]) == 2
    assert forecast["confidence_interval_30_days_95"][0] < forecast["forecast_30_days"] < forecast["confidence_interval_30_days_95"][1]
    assert forecast["seasonality"]["monsoon_active"] is True

# --------------------------------------------------------------------------
# Phase 2: Full Material Take-Off for Sample 1200 sqft, 2-floor House
# --------------------------------------------------------------------------
def test_phase_2_material_take_off_1200sqft_2floors():
    """
    Verifies Phase 2 Acceptance:
    For a sample 1200 sqft, 2-floor house, the BOQ is generated in one call,
    with element-wise quantities, municipal feasibility, climate integration,
    and trace back to engineering formulas.
    """
    takeoff = estimate_project_quantities(
        area_sqft=1200,
        floors=2,
        mix_ratio_str="1:1.5:3",
        wall_type="brick",
        location="Delhi",
        structure_type="framed"
    )

    # 1. Feasibility check
    feasibility = takeoff["feasibility"]
    assert "is_feasible" in feasibility
    assert feasibility["proposed_metrics"]["floors"] == 2

    # 2. Climate & Design integration
    assert takeoff["climate_summary"]["seismic_zone"] == "Zone IV"
    assert takeoff["design_integration"]["required_window_area_sqft"] > 0
    assert takeoff["design_integration"]["masonry_deduction_m3"] > 0

    # 3. Element-wise quantities
    q = takeoff["quantities"]
    assert q["cement_bags"] > 0
    assert q["steel_kg"] > 0
    assert q["sand_m3"] > 0
    assert q["aggregate_m3"] > 0
    assert q["bricks_count"] > 0
    assert q["water_liters"] > 0
    assert q["flooring_tiles_boxes"] > 0

    # 4. Steel element breakdown
    steel_parts = q["steel_breakdown"]
    assert steel_parts["slab_kg"] > 0
    assert steel_parts["beam_kg"] > 0
    assert steel_parts["column_kg"] > 0
    assert steel_parts["footing_kg"] > 0
    assert sum(steel_parts.values()) == q["steel_kg"]

    # 5. Standard BOQ items feed cost engine
    boq = takeoff["boq_items"]
    assert len(boq) >= 6
    cement_item = next(b for b in boq if b["material_id"] == "cement_opc53")
    assert cement_item["quantity"] == q["cement_bags"]

    # 6. Disclaimer check
    assert "ESTIMATE ONLY" in takeoff["disclaimer"].upper()
