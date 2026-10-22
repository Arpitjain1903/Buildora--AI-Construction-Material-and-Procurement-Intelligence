import re
from pathlib import Path

# Load en.json and hi.json to create embedded fallback in index.html
import json

base_dir = Path(__file__).resolve().parent.parent
en_path = base_dir / "public" / "locales" / "en.json"
hi_path = base_dir / "public" / "locales" / "hi.json"

with open(en_path, "r", encoding="utf-8") as f:
    en_dict = json.load(f)

with open(hi_path, "r", encoding="utf-8") as f:
    hi_dict = json.load(f)

print(f"Loaded {len(en_dict)} EN sections and {len(hi_dict)} HI sections.")
