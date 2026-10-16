"""
Constants Loader for Construction Material Intelligence Platform.
Loads engineering constants, factors, and thresholds from config/constants.yaml.
Provides robust fallbacks and typed helper accessors.
"""

import os
from pathlib import Path
from typing import Dict, Any
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONSTANTS_FILE = CONFIG_DIR / "constants.yaml"

_cached_constants: Dict[str, Any] = {}

def get_constants() -> Dict[str, Any]:
    global _cached_constants
    if _cached_constants:
        return _cached_constants

    if CONSTANTS_FILE.exists():
        with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
            _cached_constants = yaml.safe_load(f) or {}
    else:
        _cached_constants = {}
    return _cached_constants

def reload_constants() -> Dict[str, Any]:
    global _cached_constants
    _cached_constants = {}
    return get_constants()

CONSTANTS = get_constants()

def get_section_meta(section_name: str) -> Dict[str, Any]:
    """Retrieves source and verification metadata for any constant section."""
    c = get_constants().get(section_name, {})
    meta = c.get("_meta", {})
    return {
        "source": meta.get("source", "Configurable platform default"),
        "verified": bool(meta.get("verified", False)),
        "verification_notes": meta.get("verification_notes", "Unverified default" if not meta.get("verified") else "Verified citation")
    }
