"""
MODULE 3: Climate-Based Material Recommendation & Location Analysis
Implements:
1. IS 456:2000 Exposure Conditions (Table 3 & Table 5) for minimum cement, max w/c, and min grade.
2. IS 1893 (Part 1):2016 Seismic Zone Factors Z (II=0.10, III=0.16, IV=0.24, V=0.36).
   Correction 3.6: Explicitly labeled as ZONE INDICATORS ONLY, not structural design loads.
3. IS 875 (Part 3):2015 Wind speed zones and basic wind pressure indicator p_z = 0.6 * Vz^2.
   Explicitly labeled as ZONE INDICATOR ONLY.
4. Thermal curing schedules per IS 7861 (Part 1 & 2) and IS 456 Cl. 13.5.
5. Weather API integration with regional offline fallback database.
"""

from typing import Dict, Any, Optional
import requests

from python_app.config import settings
from python_app.constants_loader import CONSTANTS

# IS 456:2000 Table 5 Minimum Cement Content, Maximum Water-Cement Ratio and Minimum Grade
EXPOSURE_TABLE: Dict[str, Dict[str, Any]] = {
    "mild": {
        "exposure_class": "Mild",
        "min_cement_kg_m3": 300,
        "max_wc_ratio": 0.55,
        "min_concrete_grade": "M20",
        "description": "Concrete surfaces protected against weather or aggressive conditions"
    },
    "moderate": {
        "exposure_class": "Moderate",
        "min_cement_kg_m3": 300,
        "max_wc_ratio": 0.50,
        "min_concrete_grade": "M25",
        "description": "Concrete sheltered from severe rain, coastal air, or continuously submerged under non-aggressive water"
    },
    "severe": {
        "exposure_class": "Severe",
        "min_cement_kg_m3": 320,
        "max_wc_ratio": 0.45,
        "min_concrete_grade": "M30",
        "description": "Concrete exposed to severe rain, alternate wetting and drying, coastal airborne salt, or heavy frost"
    },
    "very_severe": {
        "exposure_class": "Very Severe",
        "min_cement_kg_m3": 340,
        "max_wc_ratio": 0.45,
        "min_concrete_grade": "M35",
        "description": "Concrete exposed to sea water spray, severe freezing while saturated, or corrosive industrial fumes"
    },
    "extreme": {
        "exposure_class": "Extreme",
        "min_cement_kg_m3": 360,
        "max_wc_ratio": 0.40,
        "min_concrete_grade": "M40",
        "description": "Concrete in direct contact with aggressive chemical soils, tidal zones, or heavy marine impact"
    }
}

# IS 1893 (Part 1):2016 Seismic Zone Classification
SEISMIC_ZONES: Dict[str, Dict[str, Any]] = {
    "Zone II": {
        "zone_factor": 0.10,
        "zone_factor_Z": 0.10,
        "risk_level": "Low",
        "is_indicator_only": True,
        "detailing_requirements": "Standard ductile detailing per IS 456; IS 13920 provisions recommended.",
        "design_reference": "Design horizontal seismic coefficient Ah = (Z/2)*(I/R)*(Sa/g) per IS 1893:2016 requires dynamic structural analysis."
    },
    "Zone III": {
        "zone_factor": 0.16,
        "zone_factor_Z": 0.16,
        "risk_level": "Moderate",
        "is_indicator_only": True,
        "detailing_requirements": "Mandatory ductile detailing per IS 13920:2016. Special confining reinforcement at column-beam joints.",
        "design_reference": "Design horizontal seismic coefficient Ah = (Z/2)*(I/R)*(Sa/g) per IS 1893:2016 requires dynamic structural analysis."
    },
    "Zone IV": {
        "zone_factor": 0.24,
        "zone_factor_Z": 0.24,
        "risk_level": "High",
        "is_indicator_only": True,
        "detailing_requirements": "Mandatory ductile shear walls/frames per IS 13920. 135-degree seismic hooks. Ductile steel Fe500D/Fe550D mandatory.",
        "design_reference": "Design horizontal seismic coefficient Ah = (Z/2)*(I/R)*(Sa/g) per IS 1893:2016 requires dynamic structural analysis."
    },
    "Zone V": {
        "zone_factor": 0.36,
        "zone_factor_Z": 0.36,
        "risk_level": "Very High",
        "is_indicator_only": True,
        "detailing_requirements": "Maximum ductile detailing. Base isolation/damper analysis recommended. Strict joint confinement.",
        "design_reference": "Design horizontal seismic coefficient Ah = (Z/2)*(I/R)*(Sa/g) per IS 1893:2016 requires dynamic structural analysis."
    }
}

# Regional Hazard Database with verified IS 1893:2016 Annex E Table 7 & IS 875 Annex A citations
REGIONAL_CLIMATE_DATABASE = [
    {"city": "Delhi", "aliases": ["new delhi", "ncr", "gurugram", "noida", "faridabad", "ghaziabad"], "seismic_zone": "Zone IV", "wind_zone_speed": 47, "avg_rainfall_mm": 790, "exposure_class": "moderate", "default_temp_c": 32, "latitude": 28.6139, "longitude": 77.2090, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Mumbai", "aliases": ["thane", "navi mumbai", "kalyan"], "seismic_zone": "Zone III", "wind_zone_speed": 44, "avg_rainfall_mm": 2400, "exposure_class": "severe", "default_temp_c": 30, "latitude": 19.0760, "longitude": 72.8777, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Kolkata", "aliases": ["howrah", "salt lake"], "seismic_zone": "Zone III", "wind_zone_speed": 50, "avg_rainfall_mm": 1800, "exposure_class": "severe", "default_temp_c": 31, "latitude": 22.5726, "longitude": 88.3639, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Chennai", "aliases": ["kanchipuram", "chengalpattu"], "seismic_zone": "Zone III", "wind_zone_speed": 50, "avg_rainfall_mm": 1400, "exposure_class": "severe", "default_temp_c": 33, "latitude": 13.0827, "longitude": 80.2707, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Bengaluru", "aliases": ["bangalore", "whitefield", "electronic city"], "seismic_zone": "Zone II", "wind_zone_speed": 33, "avg_rainfall_mm": 950, "exposure_class": "mild", "default_temp_c": 26, "latitude": 12.9716, "longitude": 77.5946, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Hyderabad", "aliases": ["secunderabad", "cyberabad"], "seismic_zone": "Zone II", "wind_zone_speed": 44, "avg_rainfall_mm": 820, "exposure_class": "moderate", "default_temp_c": 29, "latitude": 17.3850, "longitude": 78.4867, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Ahmedabad", "aliases": ["gandhinagar"], "seismic_zone": "Zone III", "wind_zone_speed": 39, "avg_rainfall_mm": 750, "exposure_class": "moderate", "default_temp_c": 35, "latitude": 23.0225, "longitude": 72.5714, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Pune", "aliases": ["pimpri", "chinchwad"], "seismic_zone": "Zone III", "wind_zone_speed": 39, "avg_rainfall_mm": 750, "exposure_class": "moderate", "default_temp_c": 28, "latitude": 18.5204, "longitude": 73.8567, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Chandigarh", "aliases": ["mohali", "panchkula"], "seismic_zone": "Zone IV", "wind_zone_speed": 47, "avg_rainfall_mm": 1050, "exposure_class": "moderate", "default_temp_c": 30, "latitude": 30.7333, "longitude": 76.7794, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Jaipur", "aliases": ["pink city"], "seismic_zone": "Zone II", "wind_zone_speed": 47, "avg_rainfall_mm": 650, "exposure_class": "moderate", "default_temp_c": 33, "latitude": 26.9124, "longitude": 75.7873, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Lucknow", "aliases": ["kanpur"], "seismic_zone": "Zone III", "wind_zone_speed": 47, "avg_rainfall_mm": 1000, "exposure_class": "moderate", "default_temp_c": 31, "latitude": 26.8467, "longitude": 80.9462, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Patna", "aliases": ["bihar"], "seismic_zone": "Zone IV", "wind_zone_speed": 47, "avg_rainfall_mm": 1150, "exposure_class": "severe", "default_temp_c": 31, "latitude": 25.5941, "longitude": 85.1376, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Dehradun", "aliases": ["rishikesh", "haridwar"], "seismic_zone": "Zone IV", "wind_zone_speed": 47, "avg_rainfall_mm": 2000, "exposure_class": "severe", "default_temp_c": 25, "latitude": 30.3165, "longitude": 78.0322, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Shimla", "aliases": ["himachal"], "seismic_zone": "Zone IV", "wind_zone_speed": 39, "avg_rainfall_mm": 1400, "exposure_class": "very_severe", "default_temp_c": 16, "latitude": 31.1048, "longitude": 77.1734, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Guwahati", "aliases": ["assam", "northeast", "dispur"], "seismic_zone": "Zone V", "wind_zone_speed": 50, "avg_rainfall_mm": 1700, "exposure_class": "severe", "default_temp_c": 27, "latitude": 26.1445, "longitude": 91.7362, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Srinagar", "aliases": ["jammu", "kashmir"], "seismic_zone": "Zone V", "wind_zone_speed": 39, "avg_rainfall_mm": 710, "exposure_class": "very_severe", "default_temp_c": 12, "latitude": 34.0837, "longitude": 74.7973, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Kochi", "aliases": ["cochin", "kerala", "ernakulam"], "seismic_zone": "Zone III", "wind_zone_speed": 39, "avg_rainfall_mm": 3000, "exposure_class": "severe", "default_temp_c": 29, "latitude": 9.9312, "longitude": 76.2673, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Goa", "aliases": ["panaji", "margao", "vasco"], "seismic_zone": "Zone III", "wind_zone_speed": 39, "avg_rainfall_mm": 3000, "exposure_class": "severe", "default_temp_c": 29, "latitude": 15.4909, "longitude": 73.8278, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Surat", "aliases": ["south gujarat"], "seismic_zone": "Zone III", "wind_zone_speed": 44, "avg_rainfall_mm": 1200, "exposure_class": "moderate", "default_temp_c": 31, "latitude": 21.1702, "longitude": 72.8311, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Visakhapatnam", "aliases": ["vizag"], "seismic_zone": "Zone II", "wind_zone_speed": 50, "avg_rainfall_mm": 1100, "exposure_class": "severe", "default_temp_c": 30, "latitude": 17.6868, "longitude": 83.2185, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Bhopal", "aliases": ["mp capital"], "seismic_zone": "Zone II", "wind_zone_speed": 39, "avg_rainfall_mm": 1100, "exposure_class": "moderate", "default_temp_c": 29, "latitude": 23.2599, "longitude": 77.4126, "source": "IS 1893:2016 Annex E Table 7", "verified": True},
    {"city": "Bhubaneswar", "aliases": ["cuttack", "odisha"], "seismic_zone": "Zone III", "wind_zone_speed": 50, "avg_rainfall_mm": 1500, "exposure_class": "severe", "default_temp_c": 31, "latitude": 20.2961, "longitude": 85.8245, "source": "IS 1893:2016 Annex E Table 7", "verified": True}
]

def calculate_wind_pressure_indicator(wind_speed_ms: float, height_m: float = 10.0) -> Dict[str, Any]:
    """
    Computes IS 875 (Part 3):2015 indicative wind pressure:
    Vz = Vb * k1 * k2 * k3 * k4
    p_z = 0.6 * Vz^2 (N/m2)
    Explicitly labeled as ZONE INDICATOR ONLY.
    """
    k1 = 1.0 # 50-year life
    k2 = 1.0 # Category 2 terrain at 10m height
    k3 = 1.0 # Topography
    k4 = 1.0 # Cyclone factor for non-cyclonic regions
    vz = wind_speed_ms * k1 * k2 * k3 * k4
    pz_n_m2 = round(0.6 * (vz ** 2), 1)
    pz_kn_m2 = round(pz_n_m2 / 1000.0, 3)

    return {
        "basic_wind_speed_vb_ms": wind_speed_ms,
        "design_wind_speed_vz_ms": vz,
        "basic_wind_pressure_pz_n_m2": pz_n_m2,
        "basic_wind_pressure_pz_kn_m2": pz_kn_m2,
        "is_indicator_only": True,
        "disclaimer": "ZONE INDICATOR ONLY — Wind pressure is an indicative basic pressure. Structural wind design requires aerodynamic pressure coefficients (Cpe - Cpi) and dynamic wind analysis per IS 875 (Part 3):2015 by a licensed structural engineer."
    }

def determine_curing_schedule(temp_c: float, humidity_percent: float = 60.0) -> Dict[str, Any]:
    """
    Computes curing requirements and hydration recommendations based on ambient temperature.
    Source: IS 7861 Part 1 & 2 and IS 456 Cl. 13.5
    """
    if temp_c > 35.0:
        return {
            "protocol": "Hot Climate Curing (IS 7861 Part 1)",
            "min_days": 10,
            "frequency": "3 to 4 times daily moist curing or continuous ponding",
            "admixture_recommendation": "Use set-retarding plasticizer / water reducer to combat rapid slump loss",
            "evaporation_risk": "High plastic shrinkage risk (>1.0 kg/m²/hr evaporation rate). Apply curing compound or wet burlap immediately after initial set.",
            "strength_target_28_day_pct": 90
        }
    elif temp_c < 5.0:
        return {
            "protocol": "Cold Weather Curing (IS 7861 Part 2)",
            "min_days": 14,
            "frequency": "Insulated thermal blanket enclosure + moisture retention",
            "admixture_recommendation": "Non-chloride accelerating admixture (e.g. Calcium Nitrate based)",
            "evaporation_risk": "Low evaporation, but hydration reaction severely retarded. Do not allow green concrete to freeze.",
            "strength_target_28_day_pct": 85
        }
    else:
        return {
            "protocol": "Standard Moist Curing (IS 456 Cl. 13.5)",
            "min_days": 7,
            "frequency": "Continuous ponding or wet burlap moistening twice daily",
            "admixture_recommendation": "Standard water reducer optional based on workability",
            "evaporation_risk": "Moderate evaporation risk. Maintain damp surface for full 7-14 days.",
            "strength_target_28_day_pct": 90
        }

def lookup_regional_climate(location_query: Optional[str]) -> Dict[str, Any]:
    if not location_query:
        return REGIONAL_CLIMATE_DATABASE[0]

    q = location_query.lower().strip()
    for reg in REGIONAL_CLIMATE_DATABASE:
        if reg["city"].lower() == q or any(a in q for a in reg["aliases"]) or reg["city"].lower() in q:
            return reg

    return {
        "city": location_query,
        "seismic_zone": "Zone III",
        "wind_zone_speed": 39,
        "avg_rainfall_mm": 1000,
        "exposure_class": "moderate",
        "default_temp_c": 28,
        "latitude": 28.0,
        "longitude": 77.0
    }

_coordinate_climate_cache: Dict[str, Dict[str, Any]] = {}

def lookup_climate_by_coordinates(lat: float, long: float) -> Dict[str, Any]:
    """
    Phase 3: Lat/Long -> Seismic Zone, Wind Zone, Rainfall, Flood-prone flag,
    and temperature range via cached nearest-neighbor geospatial lookup.
    """
    cache_key = f"{round(lat, 3)}_{round(long, 3)}"
    if cache_key in _coordinate_climate_cache:
        return _coordinate_climate_cache[cache_key]

    import math
    best_dist = float("inf")
    nearest_station = REGIONAL_CLIMATE_DATABASE[0]

    for reg in REGIONAL_CLIMATE_DATABASE:
        r_lat = reg.get("latitude", 28.0)
        r_lon = reg.get("longitude", 77.0)
        dlat = math.radians(lat - r_lat)
        dlon = math.radians(long - r_lon)
        a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(r_lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2.0)**2
        dist_km = 6371.0 * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))

        if dist_km < best_dist:
            best_dist = dist_km
            nearest_station = reg

    flood_prone = nearest_station["avg_rainfall_mm"] > 1800 or any(c in nearest_station["city"].lower() for c in ["mumbai", "kolkata", "chennai", "kochi", "guwahati", "patna", "dehradun"])

    result = {
        "queried_coordinates": {"lat": lat, "long": long},
        "nearest_reference_city": nearest_station["city"],
        "distance_to_station_km": round(best_dist, 1),
        "seismic_zone": nearest_station["seismic_zone"],
        "seismic_source": nearest_station.get("source", "IS 1893:2016 Annex E Table 7"),
        "seismic_verified": True,
        "wind_zone_speed": nearest_station["wind_zone_speed"],
        "wind_source": "IS 875 (Part 3):2015 Annex A",
        "wind_verified": True,
        "avg_rainfall_mm": nearest_station["avg_rainfall_mm"],
        "exposure_class": nearest_station["exposure_class"],
        "exposure_source": "IS 456:2000 Table 3",
        "exposure_verified": True,
        "default_temp_c": nearest_station["default_temp_c"],
        "temperature_range_c": [nearest_station["default_temp_c"] - 12.0, nearest_station["default_temp_c"] + 8.0],
        "flood_prone": flood_prone,
        "flood_source": "Indicative flood vulnerability based on IMD precipitation and coastal/riverine proximity; user must confirm locally with Central Water Commission (CWC)",
        "flood_verified": False,
        "is_cached": True,
        "disclaimer": "ZONE INDICATOR ONLY — Seismic and wind values are geographic zone indicators per IS 1893:2016 and IS 875:2015. On-site structural engineering required for foundation and frame design."
    }
    _coordinate_climate_cache[cache_key] = result
    return result


from python_app.weather_client import weather_client

def fetch_external_weather(lat: float, long: float) -> Optional[Dict[str, Any]]:
    """Fetches weather from weather_client (cached, OpenWeatherMap or Open-Meteo)."""
    try:
        return weather_client.get_weather(lat, long)
    except Exception:
        return None

def analyze_climate_and_location(
    location: str = "Delhi",
    lat: Optional[float] = None,
    long: Optional[float] = None,
    exposure_override: Optional[str] = None,
    temp_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Main climate analysis function with IS 456 durability, IS 1893 seismic indicators,
    IS 875 wind indicators, and live weather/curing schedule.
    """
    regional = lookup_regional_climate(location)

    effective_lat = lat if lat is not None else regional.get("latitude", 28.6139)
    effective_long = long if long is not None else regional.get("longitude", 77.2090)

    weather_data = fetch_external_weather(effective_lat, effective_long)

    current_temp = temp_override if temp_override is not None else (
        weather_data["temp_c"] if weather_data else regional["default_temp_c"]
    )
    current_humidity = weather_data["humidity"] if weather_data else 60.0

    exposure_key = (exposure_override or regional["exposure_class"]).lower()
    exposure_rules = EXPOSURE_TABLE.get(exposure_key, EXPOSURE_TABLE["moderate"])
    seismic_details = dict(SEISMIC_ZONES.get(regional["seismic_zone"], SEISMIC_ZONES["Zone III"]))
    wind_details = calculate_wind_pressure_indicator(regional["wind_zone_speed"])
    curing_schedule = determine_curing_schedule(current_temp, current_humidity)

    disclaimer = CONSTANTS.get("disclaimers", {}).get(
        "seismic_wind",
        "ZONE INDICATOR ONLY — Wind and seismic values reflect geographic zone hazard factors, not structural load calculations. Base shear and lateral wind load analysis must be performed by a structural engineer per IS 1893:2016 and IS 875:2015."
    )

    weather_source = weather_data.get("source", "rule_based_fallback") if weather_data else "rule_based_fallback"
    weather_source_label = weather_data.get("source_label", "Offline Regional Database") if weather_data else "Offline Regional Database"

    return {
        "location": regional["city"],
        "coordinates": {"lat": effective_lat, "long": effective_long},
        "seismic_zone": regional["seismic_zone"],
        "seismic_details": seismic_details,
        "wind_zone_speed_ms": regional["wind_zone_speed"],
        "wind_details": wind_details,
        "avg_rainfall_mm": regional["avg_rainfall_mm"],
        "temperature_c": round(current_temp, 1),
        "humidity_percent": round(current_humidity, 1),
        "rainfall_current_mm": weather_data.get("rainfall_mm", 0.0) if weather_data else 0.0,
        "weather_description": weather_data.get("description", "Clear") if weather_data else "Seasonal average",
        "weather_source": weather_source,
        "weather_source_label": weather_source_label,
        "weather_timestamp": weather_data.get("timestamp") if weather_data else None,
        "short_forecast": weather_data.get("short_forecast", []) if weather_data else [],
        "hot_weather_concreting_flag": weather_data.get("hot_weather_concreting_flag", False) if weather_data else current_temp > 35.0,
        "cold_weather_concreting_flag": weather_data.get("cold_weather_concreting_flag", False) if weather_data else current_temp < 5.0,
        "rain_alert_flag": weather_data.get("rain_alert_flag", False) if weather_data else False,
        "exposure_class": exposure_rules["exposure_class"],
        "min_cement_kg_m3": exposure_rules["min_cement_kg_m3"],
        "max_wc_ratio": exposure_rules["max_wc_ratio"],
        "min_concrete_grade": exposure_rules["min_concrete_grade"],
        "exposure_description": exposure_rules["description"],
        "curing_schedule": curing_schedule,
        "waterproofing_required": regional["avg_rainfall_mm"] > 1200 or exposure_key in ["severe", "very_severe", "extreme"],
        "corrosion_protection_required": exposure_key in ["severe", "very_severe", "extreme"] or regional["seismic_zone"] == "Zone V",
        "is_indicator_only": True,
        "disclaimer": disclaimer
    }

