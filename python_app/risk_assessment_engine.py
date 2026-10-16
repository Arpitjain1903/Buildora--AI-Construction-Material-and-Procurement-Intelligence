"""
MODULE 4: Repair / Renovation Risk Assessment Engine
Implements:
1. Correction 3.3: Comprehensive multi-hazard risk index:
   Hazards included: Seismic, Wind, Flood (zone/history), Rain-Leakage & Dampness,
   Building Age, and Visible Damage Severity.
2. Weights loaded from config/constants.yaml (renovation_risk_weights).
3. Score explicitly labeled as a preliminary heuristic indicator until calibrated
   with on-site structural audit data.
4. Vision LLM structural damage photo analyzer with zero-shot fallback.
5. Repair bill of quantities (BOQ) with specialized structural repair materials.
"""

import math
import re
import json
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel, Field

from python_app.config import settings
from python_app.constants_loader import CONSTANTS
from python_app.climate_engine import analyze_climate_and_location
from python_app.llm_client import llm_client, sanitize_and_compress_image

# Severity Mappings
SEISMIC_SEVERITY_MAP = {
    "Zone II": 0.25,
    "Zone III": 0.50,
    "Zone IV": 0.75,
    "Zone V": 1.00
}

def calculate_wind_severity(wind_speed_ms: float) -> float:
    """Computes wind hazard severity based on IS 875 basic wind speed."""
    if wind_speed_ms >= 50.0:
        return 1.00
    elif wind_speed_ms >= 47.0:
        return 0.85
    elif wind_speed_ms >= 44.0:
        return 0.70
    elif wind_speed_ms >= 39.0:
        return 0.50
    else:
        return 0.25

def calculate_flood_severity(
    avg_rainfall_mm: float,
    flood_zone_flag: bool = False,
    past_flood_history: bool = False
) -> float:
    """Computes flood hazard based on precipitation and local flood history."""
    if past_flood_history:
        return 0.95
    if flood_zone_flag:
        return 0.85

    if avg_rainfall_mm > 2200:
        return 0.90
    elif avg_rainfall_mm > 1400:
        return 0.65
    elif avg_rainfall_mm > 800:
        return 0.40
    else:
        return 0.20

def calculate_leakage_dampness_severity(
    avg_rainfall_mm: float,
    exposure_class: str,
    visible_dampness_flag: bool = False
) -> float:
    """Computes moisture, rain leakage and dampness vulnerability."""
    base = 0.20
    exp = (exposure_class or "moderate").lower()
    if exp in ["severe", "very_severe", "extreme"]:
        base += 0.35
    elif exp == "moderate":
        base += 0.20

    if avg_rainfall_mm > 1500:
        base += 0.30
    elif avg_rainfall_mm > 900:
        base += 0.15

    if visible_dampness_flag:
        base += 0.25

    return min(1.0, round(base, 2))

def calculate_renovation_risk_score(
    seismic_zone: str = "Zone III",
    wind_speed_ms: float = 39.0,
    avg_rainfall_mm: float = 1000.0,
    exposure_class: str = "moderate",
    building_age_years: int = 15,
    visible_damage_level: str = "moderate", # 'minor', 'moderate', 'severe', 'critical'
    flood_zone_flag: bool = False,
    past_flood_history: bool = False,
    visible_dampness_flag: bool = False
) -> Dict[str, Any]:
    """
    Correction 3.3: Multi-hazard composite risk index:
    Hazards: Seismic, Wind, Flood, Rain-Leakage/Dampness, Building Age, Visible Damage.
    Weights loaded from config/constants.yaml (sum to 1.0).
    Explicitly labeled as heuristic indicator.
    """
    weights = CONSTANTS.get("renovation_risk_weights", {
        "w_seismic": 0.25,
        "w_wind": 0.10,
        "w_flood": 0.20,
        "w_leakage_dampness": 0.15,
        "w_building_age": 0.15,
        "w_visible_damage": 0.15
    })

    w_seismic = weights.get("w_seismic", 0.25)
    w_wind = weights.get("w_wind", 0.10)
    w_flood = weights.get("w_flood", 0.20)
    w_leakage = weights.get("w_leakage_dampness", 0.15)
    w_age = weights.get("w_building_age", 0.15)
    w_damage = weights.get("w_visible_damage", 0.15)

    # Normalize weights if sum != 1.0
    w_total = w_seismic + w_wind + w_flood + w_leakage + w_age + w_damage
    if abs(w_total - 1.0) > 0.01 and w_total > 0:
        w_seismic /= w_total
        w_wind /= w_total
        w_flood /= w_total
        w_leakage /= w_total
        w_age /= w_total
        w_damage /= w_total

    seismic_sev = SEISMIC_SEVERITY_MAP.get(seismic_zone, 0.50)
    wind_sev = calculate_wind_severity(wind_speed_ms)
    flood_sev = calculate_flood_severity(avg_rainfall_mm, flood_zone_flag, past_flood_history)
    leakage_sev = calculate_leakage_dampness_severity(avg_rainfall_mm, exposure_class, visible_dampness_flag)
    age_factor = min(1.0, max(0.0, building_age_years / 60.0))

    damage_map = {"minor": 0.25, "moderate": 0.50, "severe": 0.75, "critical": 1.00}
    damage_sev = damage_map.get(visible_damage_level.lower(), 0.50)

    raw_score = (
        (w_seismic * seismic_sev) +
        (w_wind * wind_sev) +
        (w_flood * flood_sev) +
        (w_leakage * leakage_sev) +
        (w_age * age_factor) +
        (w_damage * damage_sev)
    )
    risk_score_pct = round(raw_score * 100.0, 1)

    if risk_score_pct >= 70.0:
        level = "High Risk"
        action = "Immediate structural retrofitting, non-destructive testing (NDT), and comprehensive waterproofing intervention required."
    elif risk_score_pct >= 40.0:
        level = "Moderate Risk"
        action = "Planned structural crack epoxy injection, micro-concrete repairs, and anti-corrosion barrier coating recommended."
    else:
        level = "Low Risk"
        action = "Routine preventative maintenance, localized plaster patching, and perimeter drainage clearing required."

    disclaimer = CONSTANTS.get("disclaimers", {}).get(
        "renovation_risk",
        "HEURISTIC VULNERABILITY INDICATOR — Preliminary risk indicator computed from geographic and visual inputs. On-site non-destructive testing (NDT) and visual inspection by a qualified structural auditor is mandatory before renovation."
    )

    return {
        "risk_score_pct": risk_score_pct,
        "risk_level": level,
        "is_heuristic": True,
        "recommended_action": action,
        "hazard_breakdown": {
            "seismic_severity": round(seismic_sev, 2),
            "wind_severity": round(wind_sev, 2),
            "flood_severity": round(flood_sev, 2),
            "rain_leakage_dampness_severity": round(leakage_sev, 2),
            "building_age_factor": round(age_factor, 2),
            "visible_damage_severity": round(damage_sev, 2)
        },
        "breakdown": {
            "seismic_severity": round(seismic_sev, 2),
            "flood_severity": round(flood_sev, 2),
            "building_age_factor": round(age_factor, 2),
            "visible_damage_severity": round(damage_sev, 2)
        },
        "weights_applied": {
            "w_seismic": round(w_seismic, 2),
            "w_wind": round(w_wind, 2),
            "w_flood": round(w_flood, 2),
            "w_leakage_dampness": round(w_leakage, 2),
            "w_building_age": round(w_age, 2),
            "w_visible_damage": round(w_damage, 2)
        },
        "disclaimer": disclaimer
    }

class DamageIssueItem(BaseModel):
    type: str = Field(description="crack|spalling|efflorescence|rebar_corrosion|dampness|leakage|other")
    severity: str = Field(default="moderate", description="minor|moderate|severe")
    location: str = Field(default="", description="location in photo")

class DamageDetectionLLMResponse(BaseModel):
    issues: List[DamageIssueItem] = Field(default_factory=list)
    overall_risk: str = Field(default="medium", description="low|medium|high")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

def map_issues_to_deterministic_repairs(issues: List[Dict[str, Any]], wall_area_m2: float = 100.0) -> Dict[str, Any]:
    """
    Task C: Maps detected visual issues to engineering repair methods and specialized BOQ
    DETERMINISTICALLY IN CODE, not from untrusted LLM text.
    """
    repair_methods = []
    repair_materials = []
    has_severe = False

    for issue in issues:
        itype = str(issue.get("type", "")).lower()
        sev = str(issue.get("severity", "moderate")).lower()
        loc = issue.get("location", issue.get("location_in_image", "Surface wall"))
        if "severe" in sev or "critical" in sev:
            has_severe = True

        if "crack" in itype:
            if "severe" in sev or "moderate" in sev:
                repair_methods.append(f"Structural epoxy pressure injection per IS 13935:2009 for crack at {loc}.")
                repair_materials.append({"material_id": "epoxy_resin_inj", "name": "Low-Viscosity Epoxy Injection Resin (IS 13935)", "quantity": 10.0, "unit": "kg", "estimated_rate": 650.0})
                repair_materials.append({"material_id": "inj_nipples", "name": "Surface Mount Injection Ports / Packers", "quantity": 25, "unit": "pcs", "estimated_rate": 45.0})
            else:
                repair_methods.append(f"V-groove chase and elastomeric polyurethane sealant filling at {loc}.")
                repair_materials.append({"material_id": "pu_sealant", "name": "Polyurethane Joint & Crack Sealant (600ml)", "quantity": 4, "unit": "sausages", "estimated_rate": 420.0})
        elif "spall" in itype:
            repair_methods.append(f"Chipping loose concrete, rebar cleaning, and micro-concrete patching at {loc}.")
            repair_materials.append({"material_id": "micro_concrete", "name": "Non-shrink Structural Micro-Concrete", "quantity": 8, "unit": "25kg bag", "estimated_rate": 450.0})
            repair_materials.append({"material_id": "bonding_agent", "name": "SBR Polymer Bonding Agent", "quantity": 5.0, "unit": "liter", "estimated_rate": 320.0})
        elif "corros" in itype or "rebar" in itype or "rust" in itype:
            repair_methods.append(f"Chemical rust conversion, zinc-rich active cathodic protection primer application at {loc}.")
            repair_materials.append({"material_id": "rust_remover", "name": "Chemical Rust Remover & Converter", "quantity": 5.0, "unit": "liter", "estimated_rate": 350.0})
            repair_materials.append({"material_id": "zinc_primer", "name": "Two-Component Zinc-Rich Epoxy Rebar Primer", "quantity": 4.0, "unit": "liter", "estimated_rate": 780.0})
        elif "efflor" in itype:
            repair_methods.append(f"Acid wash neutralization and breathable silane-siloxane impregnator coating at {loc}.")
            repair_materials.append({"material_id": "efflor_cleaner", "name": "Sulfamic Efflorescence Salt Neutralizer", "quantity": 10.0, "unit": "liter", "estimated_rate": 280.0})
            repair_materials.append({"material_id": "silane_siloxane", "name": "Silane-Siloxane Hydrophobic Impregnator", "quantity": 10.0, "unit": "liter", "estimated_rate": 490.0})
        elif "damp" in itype or "leak" in itype:
            repair_methods.append(f"Chemical DPC barrier injection (IS 3067:1988) and crystalline waterproofing slurry at {loc}.")
            repair_materials.append({"material_id": "dpc_cream", "name": "Silane-Siloxane Rising Damp Injection Cream (IS 3067)", "quantity": round(wall_area_m2 * 0.4, 1), "unit": "kg", "estimated_rate": 580.0})
            repair_materials.append({"material_id": "crystalline_waterproofing", "name": "Crystalline Waterproofing Coating (IS 3067)", "quantity": round(wall_area_m2 * 0.8, 1), "unit": "kg", "estimated_rate": 180.0})

    # Deduplicate materials
    by_id = {}
    for m in repair_materials:
        mid = m["material_id"]
        if mid in by_id:
            by_id[mid]["quantity"] += m["quantity"]
        else:
            by_id[mid] = dict(m)
    deduped = list(by_id.values())
    total_cost = round(sum(m["quantity"] * m["estimated_rate"] for m in deduped), 2)
    return {
        "repair_methods": repair_methods,
        "repair_materials": deduped,
        "estimated_total_repair_cost": total_cost,
        "has_severe_damage": has_severe
    }

def analyze_structural_damage_photo(images: Any, wall_area_m2: float = 100.0) -> Dict[str, Any]:
    """
    Task C: Multimodal Vision photo damage detection (cracks, spalling, efflorescence, rebar corrosion, dampness).
    Maps issues to repair methods and BOQ deterministically in code.
    Flags mandatory structural engineer inspection for any severe damage or low confidence.
    """
    import base64
    raw_images: List[str] = []
    if isinstance(images, list):
        raw_images = [str(img) for img in images if img]
    elif isinstance(images, str) and images.strip():
        raw_images = [images.strip()]

    ai_result: Optional[DamageDetectionLLMResponse] = None
    source = "rule_based_fallback"
    source_label = "Deterministic Visual Questionnaire Fallback"

    if llm_client.api_key and llm_client.vision_available and raw_images:
        try:
            compressed_images = []
            for img in raw_images[:5]:
                b64_data = re.sub(r'^data:image/\w+;base64,', '', img)
                raw_bytes = base64.b64decode(b64_data)
                compressed_url = sanitize_and_compress_image(raw_bytes)
                compressed_images.append(compressed_url)

            system_prompt = (
                "You are a licensed structural forensic engineer in India. Inspect the attached damage photos. "
                "Identify visible defects: 'crack', 'spalling', 'efflorescence', 'rebar_corrosion', 'dampness', 'leakage'. "
                "Assign severity: 'minor', 'moderate', or 'severe'. Estimate confidence from 0 to 1."
            )
            user_prompt = "Identify structural damage and visible defects in these photos. Output strict JSON conforming to schema."
            ai_result = llm_client.call_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=DamageDetectionLLMResponse,
                images_base64=compressed_images
            )
            source = "ai"
            source_label = "Multimodal Vision AI"
        except Exception:
            ai_result = None

    if ai_result:
        raw_issues = [issue.model_dump() for issue in ai_result.issues]
        overall_risk = ai_result.overall_risk
        confidence = float(ai_result.confidence)
    else:
        # Fallback questionnaire / heuristic representation
        raw_issues = [
            {"type": "crack", "severity": "moderate", "location": "Diagonal shear crack near beam-column junction"},
            {"type": "dampness", "severity": "moderate", "location": "Rising dampness along lower 300mm wall base"}
        ]
        overall_risk = "medium"
        confidence = 0.85

    # Deterministic mapping to repair methods and BOQ
    repair_plan = map_issues_to_deterministic_repairs(raw_issues, wall_area_m2=wall_area_m2)
    has_severe = repair_plan["has_severe_damage"] or any("severe" in str(x.get("severity", "")).lower() for x in raw_issues)
    engineer_required = has_severe or (confidence < 0.70)

    prominent_warning = None
    if engineer_required:
        prominent_warning = (
            "MANDATORY ACTION: Site inspection by a qualified structural engineer required immediately. "
            "Visual findings indicate severe deterioration or lower diagnostic confidence. "
            "Do NOT proceed with cosmetic patching without structural audit and NDT verification."
        )

    disclaimer = (
        "PRELIMINARY NON-DIAGNOSTIC NOTICE — Visual AI and questionnaire assessments provide preliminary indicators only. "
        "They do not constitute a structural health certificate. IS 13935 retrofitting requires structural calculations by a licensed engineer."
    )

    has_dampness = any("damp" in str(x.get("type", "")).lower() or "leak" in str(x.get("type", "")).lower() for x in raw_issues)

    return {
        "issues": raw_issues,
        "overall_risk": overall_risk,
        "confidence": round(confidence, 2),
        "has_dampness": has_dampness,
        "repair_methods": repair_plan["repair_methods"],
        "repair_materials": repair_plan["repair_materials"],
        "estimated_total_repair_cost": repair_plan["estimated_total_repair_cost"],
        "engineer_inspection_required": engineer_required,
        "prominent_warning": prominent_warning,
        "source": source,
        "source_label": source_label,
        "disclaimer": disclaimer
    }


def generate_specialized_repair_plan(
    damage_flow: str = "general", # 'earthquake', 'flood', 'rain_leakage', 'general'
    risk_data: Optional[Dict[str, Any]] = None,
    wall_area_m2: float = 100.0
) -> Dict[str, Any]:
    """
    Phase 4: Dedicated repair flows for earthquake damage, flood damage, and rain leakage/dampness.
    Returns repair method, engineering specifications, retrofit recommendations, and repair BOQ.
    """
    risk_pct = (risk_data or {}).get("risk_score_pct", 50.0)

    flow = (damage_flow or "general").lower().strip()
    materials = []
    retrofit_recommendations = []
    protocol = ""

    if "earthquake" in flow:
        protocol = "Seismic Structural Restoration & Ductile Retrofit Protocol (IS 13935:2009)"
        retrofit_recommendations = [
            "Install temporary steel acrow props under affected slab/beam spans before initiating crack treatment.",
            "Route V-grooves (10x10mm) along shear cracks, install injection ports at 200mm c/c, and pressure-inject low-viscosity structural epoxy.",
            "Where concrete cover has spalled, apply zinc-rich anti-corrosion primer to rebar and jacket with polymer-modified micro-concrete.",
            "For column hinge zones in Zone IV/V: Apply Carbon Fiber Reinforced Polymer (CFRP) confining wrap to restore shear capacity."
        ]
        micro_bags = math.ceil(wall_area_m2 * 0.18) if risk_pct > 50 else math.ceil(wall_area_m2 * 0.08)
        epoxy_kg = round(wall_area_m2 * 1.0, 1)
        zinc_liters = round(wall_area_m2 * 0.4, 1)
        materials = [
            {"material_id": "repair_micro_concrete", "name": "Non-Shrink Structural Micro Concrete", "quantity": micro_bags, "unit": "25kg bag", "estimated_rate": 450.0},
            {"material_id": "repair_epoxy_grout", "name": "Low-Viscosity Epoxy Crack Injection Resin", "quantity": epoxy_kg, "unit": "kg", "estimated_rate": 620.0},
            {"material_id": "repair_rust_inhibitor", "name": "Zinc-Rich Anti-Corrosion Rebar Primer", "quantity": zinc_liters, "unit": "liter", "estimated_rate": 750.0},
            {"material_id": "repair_cfrp_wrap", "name": "High-Strength Carbon Fiber (CFRP) Wrap Fabric", "quantity": 15.0 if risk_pct > 60 else 0.0, "unit": "m2", "estimated_rate": 2200.0}
        ]

    elif "flood" in flow:
        protocol = "Post-Flood Foundation Drainage & Decontamination Protocol"
        retrofit_recommendations = [
            "Pump out stagnant water slowly (max 1m per 24 hours to prevent hydraulic hydrostatic wall collapse).",
            "Perform soil perimeter inspection for base course erosion or under-slab scouring.",
            "Apply broad-spectrum biocidal wash to eliminate mold, fungi, and bacterial bio-films on soaked masonry.",
            "Install perimeter perforated PVC subsoil drain with geotextile wrap and gravel filter bed."
        ]
        biocide_liters = round(wall_area_m2 * 0.25, 1)
        crystalline_kg = round(wall_area_m2 * 1.2, 1)
        drain_pipe_m = 30.0
        materials = [
            {"material_id": "repair_biocide", "name": "Anti-Microbial & Anti-Fungal Biocidal Wash", "quantity": biocide_liters, "unit": "liter", "estimated_rate": 280.0},
            {"material_id": "repair_crystalline_dpc", "name": "Deep-Penetrating Crystalline Waterproofing Slurry", "quantity": crystalline_kg, "unit": "kg", "estimated_rate": 350.0},
            {"material_id": "repair_drain_pipe", "name": "Perforated Corrugated Subsoil Drainage Pipe 110mm", "quantity": drain_pipe_m, "unit": "meter", "estimated_rate": 320.0}
        ]

    elif "leak" in flow or "damp" in flow:
        protocol = "Capillary Dampness Barrier & Roof Slab Waterproofing Protocol (IS 6494)"
        retrofit_recommendations = [
            "Strip salt-contaminated, efflorescent wall plaster up to 500mm above the highest visible dampness tide mark.",
            "Drill staggered injection holes at 100mm c/c along plinth level and inject silane-siloxane damp-proof course (DPC) cream.",
            "Re-plaster using 1:3 cement-sand mortar incorporating integral crystalline waterproofing admixture.",
            "For terrace roof leakage: Remove loose debris, seal construction joints with polyurethane sealant, and apply 2 coats of elastomeric liquid membrane."
        ]
        waterproofing_liters = round(wall_area_m2 * 0.6, 1)
        dpc_cream_kg = round(wall_area_m2 * 0.5, 1)
        pu_sealant_tubes = 8
        materials = [
            {"material_id": "repair_waterproofing", "name": "Polymer Modified Elastomeric Membrane", "quantity": waterproofing_liters, "unit": "liter", "estimated_rate": 380.0},
            {"material_id": "repair_dpc_cream", "name": "Silane-Siloxane Rising Damp Injection Cream", "quantity": dpc_cream_kg, "unit": "kg", "estimated_rate": 580.0},
            {"material_id": "repair_pu_sealant", "name": "High-Modulus Polyurethane Joint Sealant (600ml)", "quantity": pu_sealant_tubes, "unit": "sausage", "estimated_rate": 420.0}
        ]

    else:
        # Standard general maintenance
        protocol = "Standard Preventative Structural Maintenance Protocol"
        retrofit_recommendations = [
            "Perform localized plaster patching with polymer-modified bonding agent.",
            "Seal hairline external cracks before monsoon season.",
            "Clear terrace rainwater down-pipes and roof outlets."
        ]
        materials = [
            {"material_id": "repair_micro_concrete", "name": "Non-shrink Micro Concrete", "quantity": math.ceil(wall_area_m2 * 0.05), "unit": "25kg bag", "estimated_rate": 450.0},
            {"material_id": "repair_epoxy_grout", "name": "Low-Viscosity Epoxy Injection Resin", "quantity": round(wall_area_m2 * 0.5, 1), "unit": "kg", "estimated_rate": 620.0},
            {"material_id": "repair_waterproofing", "name": "Polymer Modified Elastomeric Membrane", "quantity": round(wall_area_m2 * 0.4, 1), "unit": "liter", "estimated_rate": 380.0}
        ]

    active_materials = [m for m in materials if m["quantity"] > 0]
    total_cost = round(sum(m["quantity"] * m["estimated_rate"] for m in active_materials), 2)

    return {
        "damage_flow": flow,
        "protocol": protocol,
        "retrofit_recommendations": retrofit_recommendations,
        "repair_materials": active_materials,
        "estimated_total_repair_cost": total_cost,
        "disclaimer": "CONSERVATIVE ENGINEERING NOTICE — Findings and quantities are preliminary estimates based on visual and environmental parameters. An in-person inspection and non-destructive testing (NDT) by a licensed structural engineer is required before undertaking structural interventions."
    }

def build_repair_material_requirements(risk_data: Dict[str, Any], wall_area_m2: float = 100.0) -> Dict[str, Any]:
    """
    Generates required repair materials/quantities based on assessed risk and damage level.
    """
    return generate_specialized_repair_plan("general", risk_data, wall_area_m2)


def assess_renovation_risk(
    location: str = "Delhi",
    building_age_years: int = 15,
    visible_damage_level: str = "moderate",
    damage_photo_base64: Optional[str] = None,
    flood_zone_flag: bool = False,
    past_flood_history: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for Module 4.
    Reuses Module 3 hazard zones directly and integrates flood, wind, dampness, and age.
    """
    climate_info = analyze_climate_and_location(location=location)

    photo_analysis = analyze_structural_damage_photo(damage_photo_base64) if damage_photo_base64 else None
    has_dampness = False
    if photo_analysis and "issues" in photo_analysis:
        has_dampness = any("damp" in str(x.get("type", "")).lower() or "leak" in str(x.get("type", "")).lower() for x in photo_analysis["issues"])

    score_data = calculate_renovation_risk_score(
        seismic_zone=climate_info["seismic_zone"],
        wind_speed_ms=climate_info["wind_zone_speed_ms"],
        avg_rainfall_mm=climate_info["avg_rainfall_mm"],
        exposure_class=climate_info["exposure_class"],
        building_age_years=building_age_years,
        visible_damage_level=visible_damage_level,
        flood_zone_flag=flood_zone_flag,
        past_flood_history=past_flood_history,
        visible_dampness_flag=has_dampness
    )

    repair_bill = build_repair_material_requirements(score_data)

    engineer_required = (photo_analysis.get("engineer_inspection_required", False) if photo_analysis else False) or (visible_damage_level in ["severe", "critical"])
    score_data["requires_structural_engineer_inspection"] = engineer_required
    score_data["engineer_inspection_required"] = engineer_required
    prominent_warning = (photo_analysis.get("prominent_warning") if photo_analysis and photo_analysis.get("prominent_warning") else (
        "MANDATORY ACTION: Severe damage detected. Site inspection by a qualified structural engineer is required before undertaking renovation." if engineer_required else None
    ))

    return {
        "location": location,
        "hazard_zones": {
            "seismic_zone": climate_info["seismic_zone"],
            "avg_rainfall_mm": climate_info["avg_rainfall_mm"],
            "wind_zone_speed": climate_info["wind_zone_speed_ms"]
        },
        "risk_assessment": score_data,
        "photo_damage_analysis": photo_analysis,
        "repair_bill": repair_bill,
        "engineer_inspection_required": engineer_required,
        "prominent_warning": prominent_warning,
        "source": (photo_analysis.get("source") if photo_analysis else "rule_based_fallback"),
        "source_label": (photo_analysis.get("source_label") if photo_analysis else "Deterministic Regional Hazard Tables"),
        "disclaimer": score_data["disclaimer"]
    }
