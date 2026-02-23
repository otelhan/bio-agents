"""
AI CFO Agent — techno-economic modeling for bacterial cellulose production.
"""
import json
from agents.base import BaseAgent
from tools.cfo_calculator import main as run_tem


CFO_SYSTEM_PROMPT = """You are an AI CFO for a bacterial cellulose (BC) materials company.

You help users model and understand the techno-economics of BC production using a \
Techno-Economic Model (TEM). You can run financial scenarios and explain the results.

When a user asks for a scenario, use the run_tem_scenario tool with the parameters they specify.
If a parameter is not mentioned, use the default values.

After receiving results:
- Present the summary clearly and concisely
- Highlight what the key levers are (what to change to improve profitability)
- If the user asks "why is profit negative?" or similar, use the diagnostics from the result
- For a full breakdown, use detail_level="full"

Use design-oriented, constructive language. Avoid words like "fail" or "not viable" — \
instead say "low margin" or "needs improvement."

You respond only to financial and techno-economic questions about BC production.
"""

TEM_TOOLS = [
    {
        "name": "run_tem_scenario",
        "description": (
            "Run a techno-economic model scenario for bacterial cellulose production. "
            "Returns financial KPIs including revenue, EBITDA, net income, profit/kg, "
            "ROI, payback period, and NPV. Use default values for any unspecified parameters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "detail_level": {
                    "type": "string",
                    "enum": ["student", "full"],
                    "description": "Use 'full' for a detailed CFO breakdown, 'student' for a concise summary."
                },
                "production_capacity_tonnes": {"type": "number", "description": "Annual BC capacity in metric tonnes. Default: 60"},
                "capacity_utilization_percent": {"type": "number", "description": "% of capacity used (0-100). Default: 75"},
                "fashion_price": {"type": "number", "description": "$/kg for fashion market. Default: 20.0"},
                "automotive_price": {"type": "number", "description": "$/kg for automotive market. Default: 30.0"},
                "upholstery_price": {"type": "number", "description": "$/kg for upholstery market. Default: 25.0"},
                "fashion_mix_percent": {"type": "number", "description": "% of sales to fashion. Default: 40"},
                "automotive_mix_percent": {"type": "number", "description": "% of sales to automotive. Default: 35"},
                "upholstery_mix_percent": {"type": "number", "description": "% of sales to upholstery. Default: 25"},
                "raw_material_cost": {"type": "number", "description": "$/kg raw materials. Default: 8.0"},
                "energy_cost": {"type": "number", "description": "$/kg energy. Default: 3.5"},
                "labor_cost": {"type": "number", "description": "$/kg labor. Default: 2.5"},
                "maintenance_cost": {"type": "number", "description": "$/kg maintenance. Default: 1.5"},
                "quality_control_cost": {"type": "number", "description": "$/kg QC. Default: 1.0"},
                "packaging_logistics_cost": {"type": "number", "description": "$/kg packaging. Default: 2.0"},
                "initial_capex": {"type": "number", "description": "Initial CAPEX in $M. Default: 2.5"},
                "annual_fixed_costs": {"type": "number", "description": "Annual fixed costs in $M. Default: 0.4"},
                "rd_investment": {"type": "number", "description": "Annual R&D in $M. Default: 0.15"},
                "marketing_sales": {"type": "number", "description": "Annual marketing in $M. Default: 0.1"},
                "corporate_overhead": {"type": "number", "description": "Annual overhead in $M. Default: 0.2"},
                "depreciation_period_years": {"type": "number", "description": "Depreciation years. Default: 10"},
                "discount_rate_percent": {"type": "number", "description": "Discount rate % for NPV. Default: 12"},
                "tax_rate_percent": {"type": "number", "description": "Corporate tax rate %. Default: 25"},
                "batch_cycle_days": {"type": "number", "description": "Fermentation cycle duration in days. Default: 10"},
                "working_days_per_year": {"type": "number", "description": "Operating days/year. Default: 330"},
                "contamination_loss_percent": {"type": "number", "description": "% lost to contamination. Default: 8"},
                "drying_loss_percent": {"type": "number", "description": "% lost during drying. Default: 10"},
                "drying_method": {"type": "string", "enum": ["air_dry", "oven_low", "press_dry"], "description": "Drying method. Default: air_dry"},
                "pressing_level": {"type": "string", "enum": ["none", "light", "heavy"], "description": "Pressing intensity. Default: none"},
                "conditioning_rh_pct": {"type": "number", "description": "Conditioning RH %. Default: 50"},
                "conditioning_temp_c": {"type": "number", "description": "Conditioning temperature °C. Default: 23"},
                "final_moisture_pct": {"type": "number", "description": "Final moisture %. Default: 10"},
                "plasticizer_type": {"type": "string", "enum": ["none", "glycerol"], "description": "Plasticizer type. Default: none"},
                "plasticizer_pct": {"type": "number", "description": "Plasticizer %. Default: 0"},
                "treatment_chem_cost_per_kg": {"type": "number", "description": "Extra chemical cost $/kg. Default: 0"},
                "treatment_energy_cost_per_kg": {"type": "number", "description": "Extra energy cost $/kg. Default: 0"},
                "treatment_labor_cost_per_kg": {"type": "number", "description": "Extra labor cost $/kg. Default: 0"},
                "design_grade_pass_percent": {"type": "number", "description": "% meeting design grade. Default: 70"},
                "grade_a_price_multiplier": {"type": "number", "description": "Grade A price multiplier. Default: 1.15"},
                "grade_b_price_multiplier": {"type": "number", "description": "Grade B price multiplier. Default: 1.00"},
                "grade_c_price_multiplier": {"type": "number", "description": "Grade C price multiplier. Default: 0.60"},
                "grade_a_mix_percent": {"type": "number", "description": "% of sellable output as grade A. Default: 40"},
                "grade_b_mix_percent": {"type": "number", "description": "% of sellable output as grade B. Default: 40"},
                "grade_c_mix_percent": {"type": "number", "description": "% of sellable output as grade C. Default: 20"},
            },
            "required": [],
        },
    }
]


class CFOAgent(BaseAgent):
    name = "AI CFO"
    system_prompt = CFO_SYSTEM_PROMPT
    tools = TEM_TOOLS

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "run_tem_scenario":
            result = run_tem(**tool_input)
            return result["result"]
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


cfo_agent = CFOAgent()
