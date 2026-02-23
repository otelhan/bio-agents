"""
Reads and writes data/settings.json.
Reloaded on every access — no restart needed after a settings update.
"""
import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "data" / "settings.json"

DEFAULTS = {
    "designer": {"replicate_version": "", "kb_files": []},
    "farmer":   {"runs_url": "", "treatments_url": ""},
    "cfo":      {"tem_model_file": "tem_model.md"},
}


def load() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
            # Merge with defaults so missing keys are always present
            for agent, defaults in DEFAULTS.items():
                data.setdefault(agent, {})
                for k, v in defaults.items():
                    data[agent].setdefault(k, v)
            return data
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULTS))


def save(data: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)
