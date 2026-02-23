"""
TEM model markdown parser.
Reads YAML frontmatter from tem_model.md and returns parameter overrides
for cfo_calculator.main(). No PyYAML dependency — pure stdlib.

Example tem_model.md:
---
production_capacity_tonnes: 80
capacity_utilization_percent: 80
contamination_loss_percent: 5
fashion_price: 22.0
---
# TEM Model Notes
This model reflects our current pilot plant assumptions...
"""
from pathlib import Path

KB_DIR = Path(__file__).parent.parent / "data" / "kb"

# All numeric parameters accepted by cfo_calculator.main()
_FLOAT_PARAMS = {
    "production_capacity_tonnes", "capacity_utilization_percent",
    "fashion_price", "automotive_price", "upholstery_price",
    "fashion_mix_percent", "automotive_mix_percent", "upholstery_mix_percent",
    "raw_material_cost", "energy_cost", "labor_cost", "maintenance_cost",
    "quality_control_cost", "packaging_logistics_cost",
    "initial_capex", "annual_fixed_costs", "rd_investment",
    "marketing_sales", "corporate_overhead",
    "depreciation_period_years", "discount_rate_percent", "tax_rate_percent",
    "batch_cycle_days", "working_days_per_year",
    "contamination_loss_percent", "drying_loss_percent",
    "conditioning_rh_pct", "conditioning_temp_c", "final_moisture_pct",
    "plasticizer_pct",
    "treatment_chem_cost_per_kg", "treatment_energy_cost_per_kg",
    "treatment_labor_cost_per_kg",
    "design_grade_pass_percent",
    "grade_a_price_multiplier", "grade_b_price_multiplier", "grade_c_price_multiplier",
    "grade_a_mix_percent", "grade_b_mix_percent", "grade_c_mix_percent",
}

_STRING_PARAMS = {"drying_method", "pressing_level", "plasticizer_type", "detail_level"}


def _parse_frontmatter(text: str) -> dict:
    """Extract key: value pairs from YAML frontmatter (between --- delimiters)."""
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}

    result = {}
    for line in lines[1:end]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw_val = line.partition(":")
        key = key.strip()
        val = raw_val.strip()

        if key in _FLOAT_PARAMS:
            try:
                result[key] = float(val)
            except ValueError:
                pass
        elif key in _STRING_PARAMS:
            result[key] = val.strip('"').strip("'")

    return result


def load_overrides(tem_file: str = "tem_model.md") -> dict:
    """
    Load TEM parameter overrides from the markdown file.
    Returns an empty dict if the file doesn't exist or has no frontmatter.
    """
    path = KB_DIR / Path(tem_file).name  # prevent path traversal
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return _parse_frontmatter(text)
    except Exception:
        return {}
