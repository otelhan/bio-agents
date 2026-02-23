"""
Techno-economic model for bacterial cellulose production.
Ported directly from AI CFO.yml Dify code node.
"""
import json


def main(
    # Output control
    detail_level: str = "student",

    # --- CFO / TEM ---
    production_capacity_tonnes: float = 60,
    capacity_utilization_percent: float = 75,

    fashion_price: float = 20.0,
    automotive_price: float = 30.0,
    upholstery_price: float = 25.0,

    fashion_mix_percent: float = 40.0,
    automotive_mix_percent: float = 35.0,
    upholstery_mix_percent: float = 25.0,

    raw_material_cost: float = 8.0,
    energy_cost: float = 3.5,
    labor_cost: float = 2.5,
    maintenance_cost: float = 1.5,
    quality_control_cost: float = 1.0,
    packaging_logistics_cost: float = 2.0,

    initial_capex: float = 2.5,
    annual_fixed_costs: float = 0.4,
    rd_investment: float = 0.15,
    marketing_sales: float = 0.1,
    corporate_overhead: float = 0.2,

    depreciation_period_years: int = 10,
    discount_rate_percent: float = 12.0,
    tax_rate_percent: float = 25.0,

    # --- BC RUN ---
    batch_cycle_days: float = 10,
    working_days_per_year: int = 330,
    contamination_loss_percent: float = 8.0,
    drying_loss_percent: float = 10.0,

    # --- Treatment ---
    drying_method: str = "air_dry",
    pressing_level: str = "none",
    conditioning_rh_pct: float = 50.0,
    conditioning_temp_c: float = 23.0,
    final_moisture_pct: float = 10.0,
    plasticizer_type: str = "none",
    plasticizer_pct: float = 0.0,

    treatment_chem_cost_per_kg: float = 0.0,
    treatment_energy_cost_per_kg: float = 0.0,
    treatment_labor_cost_per_kg: float = 0.0,

    # --- Aesthetic / Quality (TAE) ---
    design_grade_pass_percent: float = 70.0,
    grade_a_price_multiplier: float = 1.15,
    grade_b_price_multiplier: float = 1.00,
    grade_c_price_multiplier: float = 0.60,
    grade_a_mix_percent: float = 40.0,
    grade_b_mix_percent: float = 40.0,
    grade_c_mix_percent: float = 20.0,
) -> dict:

    def clamp(x, lo, hi):
        return max(lo, min(hi, x))

    def safe_div(a, b, default=0.0):
        return a / b if b else default

    BASELINE_DEFAULTS = {
        "production_capacity_tonnes": 60,
        "capacity_utilization_percent": 75,
        "design_grade_pass_percent": 70.0,
        "contamination_loss_percent": 8.0,
        "drying_loss_percent": 10.0,
        "fashion_price": 20.0,
        "automotive_price": 30.0,
        "upholstery_price": 25.0,
        "raw_material_cost": 8.0,
        "energy_cost": 3.5,
        "labor_cost": 2.5,
    }

    util = clamp(capacity_utilization_percent, 0, 100) / 100.0

    mix_sum = fashion_mix_percent + automotive_mix_percent + upholstery_mix_percent
    if mix_sum <= 0:
        mix_f = mix_a = mix_u = 0.0
    else:
        mix_f = fashion_mix_percent / mix_sum
        mix_a = automotive_mix_percent / mix_sum
        mix_u = upholstery_mix_percent / mix_sum

    gsum = grade_a_mix_percent + grade_b_mix_percent + grade_c_mix_percent
    if gsum <= 0:
        g_a = g_b = g_c = 0.0
    else:
        g_a = grade_a_mix_percent / gsum
        g_b = grade_b_mix_percent / gsum
        g_c = grade_c_mix_percent / gsum

    contam = clamp(contamination_loss_percent, 0, 100) / 100.0
    dryloss = clamp(drying_loss_percent, 0, 100) / 100.0
    pass_rate = clamp(design_grade_pass_percent, 0, 100) / 100.0
    dr = clamp(discount_rate_percent, 0, 100) / 100.0
    tax = clamp(tax_rate_percent, 0, 100) / 100.0

    gross_t = production_capacity_tonnes * util
    gross_kg = gross_t * 1000.0

    after_losses_factor = (1.0 - contam) * (1.0 - dryloss)
    sellable_factor = after_losses_factor * pass_rate
    sellable_kg = gross_kg * sellable_factor

    runs_per_year = safe_div(working_days_per_year, batch_cycle_days) if batch_cycle_days > 0 else 0.0

    base_price = fashion_price * mix_f + automotive_price * mix_a + upholstery_price * mix_u
    grade_multiplier = (
        g_a * grade_a_price_multiplier +
        g_b * grade_b_price_multiplier +
        g_c * grade_c_price_multiplier
    )
    realized_price = base_price * grade_multiplier

    base_var_cost = raw_material_cost + energy_cost + labor_cost + maintenance_cost + quality_control_cost
    treatment_adders = treatment_chem_cost_per_kg + treatment_energy_cost_per_kg + treatment_labor_cost_per_kg
    var_cost_gross_per_kg = base_var_cost + treatment_adders
    var_cost_total = gross_kg * var_cost_gross_per_kg + sellable_kg * packaging_logistics_cost

    revenue = sellable_kg * realized_price
    gross_profit = revenue - var_cost_total
    gm_pct = safe_div(gross_profit, revenue) * 100.0 if revenue > 0 else 0.0

    capex_dollars = initial_capex * 1_000_000.0
    fixed_total = (annual_fixed_costs + rd_investment + marketing_sales + corporate_overhead) * 1_000_000.0
    dep = capex_dollars / max(int(depreciation_period_years), 1)

    ebitda = gross_profit - fixed_total
    ebitda_pct = safe_div(ebitda, revenue) * 100.0 if revenue > 0 else 0.0

    ebit = ebitda - dep
    taxes = max(0.0, ebit * tax) if ebit > 0 else 0.0
    net_income = ebit - taxes

    rev_per_sellable_kg = realized_price
    cost_per_sellable_kg = safe_div(var_cost_total + fixed_total + dep, sellable_kg, float("inf"))
    profit_per_sellable_kg = rev_per_sellable_kg - cost_per_sellable_kg if sellable_kg > 0 else float("-inf")

    payback_years = (capex_dollars / net_income) if net_income > 0 else float("inf")
    roi_pct = safe_div(net_income, capex_dollars) * 100.0 if capex_dollars > 0 else 0.0

    npv = -capex_dollars
    for y in range(1, 6):
        npv += safe_div(net_income, (1.0 + dr) ** y)

    rev_f = revenue * mix_f
    rev_a = revenue * mix_a
    rev_u = revenue * mix_u

    def money(x): return f"${x:,.0f}"
    def M(x): return f"${x/1_000_000.0:.2f}M"
    def yrs(x): return "∞" if x == float("inf") else f"{x:.1f}"

    overrides = []

    def check_override(label, current, baseline, fmt=None):
        if isinstance(current, float) or isinstance(baseline, float):
            changed = abs(float(current) - float(baseline)) > 1e-9
        else:
            changed = current != baseline
        if changed:
            if fmt:
                overrides.append(f"{label} = {fmt(current)} (default {fmt(baseline)})")
            else:
                overrides.append(f"{label} = {current} (default {baseline})")

    check_override("capacity utilization", capacity_utilization_percent,
                   BASELINE_DEFAULTS["capacity_utilization_percent"], lambda x: f"{x:.0f}%")
    check_override("design-grade pass rate", design_grade_pass_percent,
                   BASELINE_DEFAULTS["design_grade_pass_percent"], lambda x: f"{x:.0f}%")
    check_override("annual capacity", production_capacity_tonnes,
                   BASELINE_DEFAULTS["production_capacity_tonnes"], lambda x: f"{x:.0f} t/yr")
    check_override("contamination loss", contamination_loss_percent,
                   BASELINE_DEFAULTS["contamination_loss_percent"], lambda x: f"{x:.1f}%")
    check_override("drying loss", drying_loss_percent,
                   BASELINE_DEFAULTS["drying_loss_percent"], lambda x: f"{x:.1f}%")
    check_override("raw materials cost", raw_material_cost,
                   BASELINE_DEFAULTS["raw_material_cost"], lambda x: f"${x:.2f}/kg")
    check_override("energy cost", energy_cost,
                   BASELINE_DEFAULTS["energy_cost"], lambda x: f"${x:.2f}/kg")
    check_override("labor cost", labor_cost,
                   BASELINE_DEFAULTS["labor_cost"], lambda x: f"${x:.2f}/kg")

    overrides_text = ""
    if overrides:
        overrides_text = "Overrides:\n- " + "\n- ".join(overrides) + "\n\n"

    diagnostics = []
    if realized_price < (var_cost_gross_per_kg + packaging_logistics_cost):
        diagnostics.append(
            "Unit margin problem: realized price is below variable cost. "
            "Improve pricing/mix or reduce variable costs."
        )
    if sellable_factor < 0.65:
        diagnostics.append(
            "Yield/quality lever: effective sellable yield is low. "
            "Improve pass rate and/or reduce contamination/drying losses."
        )
    if fixed_total > revenue * 0.5:
        diagnostics.append(
            "Scale lever: fixed costs dominate at this revenue scale. "
            "Increase sellable volume or reduce fixed costs."
        )
    if not diagnostics:
        diagnostics = ["Main levers: sellable yield, realized price, and variable costs."]
    diagnostics = diagnostics[:2]
    drivers_block = "\n".join([f"- {d}" for d in diagnostics])

    summary = f"""
BC TAE — Scenario Summary
---------------------------
{overrides_text}Sellable output: {sellable_kg:,.0f} kg/yr
Realized price: ${realized_price:.2f}/kg
Profit per sellable kg: ${profit_per_sellable_kg:.2f}/kg

Revenue: {money(revenue)} | EBITDA: {money(ebitda)} | Net income: {money(net_income)}

What to change (levers):
{drivers_block}
""".strip()

    full = f"""
BC TAE — CFO SUMMARY
================================

PRODUCTION
- Gross Production: {gross_t:.1f} t ({gross_kg:,.0f} kg)
- Sellable (Design-Grade): {sellable_kg:,.0f} kg
- Effective Sellable Yield: {sellable_factor*100.0:.1f}%
- Utilization: {capacity_utilization_percent:.0f}%
- Runs/year: {runs_per_year:.1f} | Cycle: {batch_cycle_days:.1f} days

TREATMENT
- Drying: {drying_method} | Pressing: {pressing_level}
- Conditioning: {conditioning_rh_pct:.0f}% RH @ {conditioning_temp_c:.0f}°C | Final Moisture: {final_moisture_pct:.1f}%
- Plasticizer: {plasticizer_type} {plasticizer_pct:.1f}%

PRICING
- Segment Base Price (blended): ${base_price:.2f}/kg
- Grade Multiplier: {grade_multiplier:.3f}x
- Realized Price: ${realized_price:.2f}/kg

COSTS
- Variable cost on gross: ${var_cost_gross_per_kg:.2f}/kg
- Packaging/logistics: ${packaging_logistics_cost:.2f}/kg

FINANCIALS
- Revenue: {money(revenue)} ({M(revenue)}) | Gross Margin: {gm_pct:.1f}%
- EBITDA: {money(ebitda)} ({M(ebitda)}) | EBITDA %: {ebitda_pct:.1f}%
- Net Income: {money(net_income)} ({M(net_income)})

UNIT ECONOMICS (per sellable kg)
- Revenue/kg: ${rev_per_sellable_kg:.2f}
- All-in Cost/kg: ${cost_per_sellable_kg:.2f}
- Profit/kg: ${profit_per_sellable_kg:.2f}

INVESTMENT
- CAPEX: {M(capex_dollars)} | ROI: {roi_pct:.1f}% | Payback: {yrs(payback_years)} years
- NPV (5y): {M(npv)}

SEGMENTS
- Fashion: {money(rev_f)} ({fashion_mix_percent:.0f}% @ ${fashion_price:.2f}/kg)
- Automotive: {money(rev_a)} ({automotive_mix_percent:.0f}% @ ${automotive_price:.2f}/kg)
- Upholstery: {money(rev_u)} ({upholstery_mix_percent:.0f}% @ ${upholstery_price:.2f}/kg)
""".strip()

    payload = {
        "mode": "full" if str(detail_level).strip().lower() == "full" else "student",
        "overrides": overrides,
        "kpis": {
            "gross_kg": gross_kg,
            "sellable_kg": sellable_kg,
            "effective_sellable_yield_pct": sellable_factor * 100.0,
            "realized_price_per_kg": realized_price,
            "revenue": revenue,
            "ebitda": ebitda,
            "net_income": net_income,
            "profit_per_sellable_kg": profit_per_sellable_kg,
            "roi_pct": roi_pct,
            "payback_years": None if payback_years == float("inf") else payback_years,
            "npv_5y": npv,
        },
        "drivers": {
            "utilization_pct": capacity_utilization_percent,
            "pass_rate_pct": design_grade_pass_percent,
            "contamination_loss_pct": contamination_loss_percent,
            "drying_loss_pct": drying_loss_percent,
            "base_price_per_kg": base_price,
            "grade_multiplier": grade_multiplier,
            "var_cost_gross_per_kg": var_cost_gross_per_kg,
        },
        "diagnostics": diagnostics,
    }

    result = full if str(detail_level).strip().lower() == "full" else summary
    return {"result": result, "summary": summary, "full": full, "payload": json.dumps(payload)}
