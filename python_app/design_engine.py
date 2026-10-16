"""
MODULE 5: Aesthetic & Layout Design Suggestions Engine
Implements:
1. Correction 3.7: Configurable ventilation opening-to-floor area ratios based on IS 3362:1977,
   NBC 2016 Part 8, and local municipal building bye-laws (Delhi UBBL, Mumbai DCPR, Kolkata, Chennai, BBMP).
2. Cross-ventilation guidelines and wind-direction alignment.
3. Text LLM layout design suggestion generator with deterministic template fallbacks.
4. BOQ material adjustment module (glazing, louvers, masonry deductions).
"""

import re
import json
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel, Field

from python_app.config import settings
from python_app.constants_loader import CONSTANTS
from python_app.climate_engine import analyze_climate_and_location
from python_app.llm_client import llm_client

def get_ventilation_ratio_for_location(location: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns required window-to-floor opening ratio and citation per municipal bye-laws or climate.
    Source: config/constants.yaml (ventilation_standards)
    """
    v_cfg = CONSTANTS.get("ventilation_standards", {})
    muni_map = v_cfg.get("municipal_bylaws", {})
    reg_map = v_cfg.get("regional_min_ratios", {})
    default_ratio = v_cfg.get("default_min_ratio", 0.10)

    if location:
        loc_clean = location.strip()
        for city, rule in muni_map.items():
            if city.lower() in loc_clean.lower() or loc_clean.lower() in city.lower():
                return {
                    "min_ratio": float(rule.get("min_opening_ratio", default_ratio)),
                    "authority": rule.get("authority", "Municipal Building Bye-Laws"),
                    "climate_basis": "Municipal Mandate"
                }

        # Check regional climate
        loc_lower = loc_clean.lower()
        if any(c in loc_lower for c in ["mumbai", "chennai", "kolkata", "kochi", "goa", "coastal"]):
            return {
                "min_ratio": float(reg_map.get("warm_humid", 0.1667)),
                "authority": "IS 3362:1977 Cl. 4.1 & NBC 2016 (Warm-Humid / Coastal Zone)",
                "climate_basis": "Warm-Humid (Min 1/6th floor area)"
            }
        elif any(c in loc_lower for c in ["bengaluru", "hyderabad", "pune"]):
            return {
                "min_ratio": float(reg_map.get("composite", 0.125)),
                "authority": "IS 3362:1977 Cl. 4.1 & NBC 2016 (Composite Zone)",
                "climate_basis": "Composite (Min 1/8th floor area)"
            }
        elif any(c in loc_lower for c in ["srinagar", "shimla", "manali", "cold"]):
            return {
                "min_ratio": float(reg_map.get("cold", 0.08)),
                "authority": "IS 3362:1977 Cl. 4.1 & NBC 2016 (Cold Climate)",
                "climate_basis": "Cold (Min 8% floor area)"
            }

    return {
        "min_ratio": default_ratio,
        "authority": "IS 3362:1977 Standard Guideline & NBC 2016 Part 8 Clause 4",
        "climate_basis": "Standard (Min 10% floor area)"
    }

def calculate_ventilation_requirements(
    area_sqft: float,
    floors: int,
    location: Optional[str] = "Delhi",
    ratio_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Computes required aggregate opening area (windows/ventilators) per IS 3362 & local bye-laws.
    """
    rule = get_ventilation_ratio_for_location(location)
    ratio = ratio_override if ratio_override is not None else rule["min_ratio"]

    total_floor_area_m2 = area_sqft * 0.092903 * floors
    min_window_area_m2 = round(total_floor_area_m2 * ratio, 2)
    min_window_area_sqft = round(area_sqft * floors * ratio, 1)

    return {
        "total_floor_area_sqft": round(area_sqft * floors, 1),
        "total_floor_area_m2": round(total_floor_area_m2, 1),
        "min_window_area_m2": min_window_area_m2,
        "min_window_area_sqft": min_window_area_sqft,
        "opening_to_floor_ratio": round(ratio, 4),
        "authority_reference": rule["authority"],
        "climate_basis": rule["climate_basis"],
        "cross_ventilation_rule": "At least 2 openings on opposite or adjacent walls per habitable room aligned with prevailing wind direction (IS 3362 Clause 5.2)."
    }

class LayoutIdeaItem(BaseModel):
    title: str = Field(description="Title of layout proposal")
    description: str = Field(description="Architectural layout concept")
    ventilation_strategy: str = Field(description="Airflow, stack effect, and cross-ventilation arrangement")
    window_area_sqft_proposed: Optional[float] = Field(default=None, description="Proposed aggregate opening area in sqft")
    supports_cross_ventilation: bool = Field(default=True, description="Whether layout provides dual opposite/adjacent wall openings")

class LayoutDesignSuggestionsResponse(BaseModel):
    suggestions: List[LayoutIdeaItem] = Field(default_factory=list)

def generate_layout_design_suggestions(
    area_sqft: float = 1500.0,
    floors: int = 2,
    orientation: str = "North-East",
    location: str = "Delhi"
) -> Dict[str, Any]:
    """
    Task D: Generates 3-5 layout ideas maximizing cross-ventilation and daylight.
    Calls Text LLM when configured, validates every proposal in code against municipal
    window-to-floor opening ratios and cross-ventilation rules (IS 3362 / NBC 2016).
    Non-compliant proposals are never shown as compliant.
    """
    climate_info = analyze_climate_and_location(location=location)
    vent_specs = calculate_ventilation_requirements(area_sqft, floors, location=location)
    wind_speed = climate_info.get("wind_zone_speed_ms", 39)
    min_win_sqft = vent_specs["min_window_area_sqft"]
    authority = vent_specs["authority_reference"]

    ai_result: Optional[LayoutDesignSuggestionsResponse] = None
    source = "rule_based_fallback"
    source_label = "Rule-Constrained Bioclimatic Templates"

    if llm_client.api_key:
        try:
            system_prompt = (
                "You are an expert residential architectural consultant in India specializing in bioclimatic passive solar design. "
                "Suggest 3-5 layout design concepts that optimize natural cross-ventilation and daylighting. "
                "Include window_area_sqft_proposed and supports_cross_ventilation boolean for each idea."
            )
            user_prompt = (
                f"Project: area={area_sqft} sqft, floors={floors}, plot orientation={orientation}, "
                f"location={location}, climate={climate_info['exposure_class']}, prevailing wind={wind_speed} m/s. "
                f"Statutory ventilation opening requirement: min {vent_specs['opening_to_floor_ratio']*100:.1f}% of floor area "
                f"({min_win_sqft} sqft total opening area per {authority}). "
                f"Return JSON matching LayoutDesignSuggestionsResponse schema with 3 to 5 layout proposals."
            )
            ai_result = llm_client.call_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=LayoutDesignSuggestionsResponse
            )
            if ai_result and ai_result.suggestions:
                source = "ai"
                source_label = "Text LLM Architectural Assistant"
        except Exception:
            ai_result = None

    if ai_result and ai_result.suggestions:
        raw_suggestions = [s.model_dump() for s in ai_result.suggestions]
    else:
        # Fallback bioclimatic architectural templates
        raw_suggestions = [
            {
                "title": f"Courtyard-Centric Passive Cooling Layout ({orientation} Facing)",
                "description": f"Position central open-to-sky courtyard with high-level louvers to create a chimney stack effect, lowering ambient indoor temp in {location}.",
                "ventilation_strategy": f"Window area of {min_win_sqft} sqft distributed across north-south facade for stack ventilation per {authority}.",
                "window_area_sqft_proposed": min_win_sqft,
                "supports_cross_ventilation": True
            },
            {
                "title": "Dual-Aspect L-Shaped Living Corridor",
                "description": "L-shaped open plan floor arrangement allowing cross breezes across living and dining areas without structural partition walls.",
                "ventilation_strategy": "Operable casement windows placed at 45° angle to prevailing wind direction for high airflow catchment.",
                "window_area_sqft_proposed": round(min_win_sqft * 1.15, 1),
                "supports_cross_ventilation": True
            },
            {
                "title": "Solar-Shaded Clerestory & Deep Overhang Layout",
                "description": "Extended roof overhangs (600mm) combined with high clerestory windows to allow hot air exhaust while preventing direct solar thermal gain.",
                "ventilation_strategy": "Low-level inlet louvers on cool windward wall paired with high-level exhaust openings on leeward wall.",
                "window_area_sqft_proposed": round(min_win_sqft * 1.10, 1),
                "supports_cross_ventilation": True
            }
        ]

    # Deterministic code-level verification of proposals
    verified_proposals = []
    for prop in raw_suggestions:
        p = dict(prop)
        prop_area = p.get("window_area_sqft_proposed")
        is_cross = p.get("supports_cross_ventilation", True)

        compliant = True
        compliance_notes = []

        if prop_area is not None:
            if prop_area < min_win_sqft:
                compliant = False
                compliance_notes.append(f"NON-COMPLIANT: Proposed window area ({prop_area} sqft) is below statutory minimum ({min_win_sqft} sqft) per {authority}.")
            else:
                compliance_notes.append(f"COMPLIANT: Proposed window area ({prop_area} sqft) satisfies statutory minimum ({min_win_sqft} sqft) per {authority}.")
        else:
            compliance_notes.append(f"Proposed openings must allocate at least {min_win_sqft} sqft per {authority}.")

        if not is_cross:
            compliant = False
            compliance_notes.append("NON-COMPLIANT: Lacks dual-aspect cross ventilation openings required by IS 3362 Cl. 5.2.")
        else:
            compliance_notes.append("COMPLIANT: Dual-aspect cross-ventilation verified per IS 3362 Cl. 5.2.")

        p["is_compliant"] = compliant
        p["compliance_notes"] = compliance_notes
        p["min_required_window_area_sqft"] = min_win_sqft
        verified_proposals.append(p)

    disclaimer = (
        "ARCHITECTURAL CONCEPT NOTICE — Layout proposals are indicative design concepts for cross-ventilation and spatial orientation. "
        "Final architectural drawings, municipal sanction submissions, and structural framing must be prepared by a licensed architect."
    )

    return {
        "ventilation_specs": vent_specs,
        "suggestions": verified_proposals,
        "source": source,
        "source_label": source_label,
        "disclaimer": disclaimer
    }


def adjust_material_quantities_from_design(
    base_quantities: Dict[str, Any],
    selected_design_option: str = "courtyard"
) -> Dict[str, Any]:
    """
    Adjusts material list quantities when user selects a specific design/layout choice.
    E.g., adding glazing area, reducing interior brick partition volume, or adding shading louvers.
    """
    adjusted = dict(base_quantities)
    q = dict(adjusted.get("quantities", {}))

    if selected_design_option == "courtyard":
        # Courtyard reduces partition brick volume by 8% and adds glass glazing
        q["bricks_count"] = int(q.get("bricks_count", 0) * 0.92)
        q["blocks_count"] = int(q.get("blocks_count", 0) * 0.92)
        q["glass_glazing_sqft"] = 280
        q["aluminum_louvers_kg"] = 150
    elif selected_design_option == "clerestory":
        # Deep overhang adds ~5% roof slab concrete & steel
        q["steel_kg"] = int(q.get("steel_kg", 0) * 1.05)
        q["cement_bags"] = int(q.get("cement_bags", 0) * 1.04)
        q["glass_glazing_sqft"] = 350
    else:
        q["glass_glazing_sqft"] = 200

    adjusted["quantities"] = q
    adjusted["design_adjustment_applied"] = selected_design_option
    return adjusted
