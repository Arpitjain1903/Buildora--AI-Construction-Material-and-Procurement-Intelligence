import json
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
en_path = base_dir / "public" / "locales" / "en.json"
hi_path = base_dir / "public" / "locales" / "hi.json"

with open(en_path, "r", encoding="utf-8") as f:
    en_dict = json.load(f)

with open(hi_path, "r", encoding="utf-8") as f:
    hi_dict = json.load(f)

i18n_combined = {
    "en": en_dict,
    "hi": hi_dict
}

template_path = base_dir / "scripts" / "index_template.html"
target_path = base_dir / "public" / "index.html"

with open(template_path, "r", encoding="utf-8") as f:
    template_content = f.read()

output_content = template_content.replace("__EMBEDDED_I18N_JSON__", json.dumps(i18n_combined, ensure_ascii=False))

with open(target_path, "w", encoding="utf-8") as f:
    f.write(output_content)

print(f"Generated {target_path} successfully ({len(output_content)} bytes)")
