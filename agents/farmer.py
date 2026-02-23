"""
AI Farmer Agent — BC production data analysis.
"""
import json
from agents.base import BaseAgent
from tools.farmer_analytics import main as run_analytics
from tools.farmer_schema import main as run_schema
from tools.google_sheets import sheets_url_to_csv
from tools import settings_store

FARMER_SYSTEM_PROMPT = """You are AI Farmer, a data analyst for bacterial cellulose (BC) \
static tray production.

You help users explore and understand production datasets (runs and treatments) \
from 2024 and 2025. You can compute summaries, find best recipes, compare trends, \
identify anomalies, and explain dataset structure.

When answering data questions, use the query_production_data tool.
When answering schema/structure questions (what fields exist, what does a field mean, \
coverage statistics), use the query_schema tool.
When the user asks for help or example questions, reply directly without using a tool.

Present results clearly. If the tool returns a markdown table, show it as-is. \
Add 1–3 short bullet points explaining what the table shows.
Never invent numbers. Only use what the tool returns.
"""

FARMER_TOOLS = [
    {
        "name": "query_production_data",
        "description": (
            "Query BC production data. Supports: summary, filter_table, best, compare, "
            "trend, feature_importance, anomaly_detection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset":    {"type": "string", "enum": ["runs", "treatments"],
                               "description": "runs=fermentation runs; treatments=post-processing treatments"},
                "intent":     {"type": "string",
                               "enum": ["summary", "filter_table", "best", "compare",
                                        "trend", "feature_importance", "anomaly_detection"]},
                "year":       {"type": "integer", "description": "Filter by year (2024 or 2025). Omit for all years."},
                "recipe":     {"type": "string", "description": "Filter by recipe name (lowercase)."},
                "metric":     {"type": "string",
                               "description": "Metric to analyse. Runs: yield_per_m2_gm2, dry_mass_total_g, "
                                              "avg_thickness_mm, defects_pct. Treatments: tensile_strength_mpa, "
                                              "elongation_pct, youngs_modulus_mpa."},
                "aggregation": {"type": "string", "enum": ["sum", "avg", "median", "min", "max", "count"],
                                "description": "How to aggregate. Default: avg"},
                "group_by":   {"type": "string",
                               "enum": ["none", "recipe", "year", "month", "recipe_year",
                                        "drying_method", "pressing_level", "surface_class"],
                               "description": "Grouping for compare/trend. Default: none"},
                "top_k":      {"type": "integer", "description": "Number of top results. Default: 5"},
                "min_defects_pct": {"type": "number"},
                "max_defects_pct": {"type": "number"},
                "only_contaminated": {"type": "boolean"},
                "as_table":   {"type": "boolean", "description": "Return raw table of rows"},
            },
            "required": ["dataset", "intent"],
        },
    },
    {
        "name": "query_schema",
        "description": "Answer schema/structure questions: list fields, describe a field, "
                       "show coverage stats, compare 2024 vs 2025 schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_fields", "describe_field", "list_outputs",
                             "dataset_diff", "coverage_stats"],
                },
                "dataset_scope": {"type": "string", "enum": ["2024", "2025", "both"],
                                  "description": "Which year(s) to inspect. Default: both"},
                "table":        {"type": "string", "enum": ["runs", "treatments", "both"],
                                 "description": "Which table. Default: both"},
                "field_name":   {"type": "string", "description": "Required for describe_field action."},
            },
            "required": ["action"],
        },
    },
]


class FarmerAgent(BaseAgent):
    name = "AI Farmer"
    system_prompt = FARMER_SYSTEM_PROMPT
    tools = FARMER_TOOLS

    def _get_urls(self):
        cfg = settings_store.load()["farmer"]
        runs_url       = sheets_url_to_csv(cfg.get("runs_url", ""))
        treatments_url = sheets_url_to_csv(cfg.get("treatments_url", ""))
        if not runs_url or not treatments_url:
            raise ValueError(
                "Farmer data sources are not configured. "
                "Please set the Google Sheets (or CSV) URLs in the settings panel."
            )
        return runs_url, treatments_url

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        try:
            runs_url, treatments_url = self._get_urls()
        except ValueError as e:
            return json.dumps({"result": str(e)})

        if tool_name == "query_production_data":
            result = run_analytics(
                runs_csv_url=runs_url,
                treatments_csv_url=treatments_url,
                **tool_input,
            )
            return result["result"]

        if tool_name == "query_schema":
            result = run_schema(
                runs_csv_url=runs_url,
                treatments_csv_url=treatments_url,
                **tool_input,
            )
            return result["result"]

        return json.dumps({"error": f"Unknown tool: {tool_name}"})


farmer_agent = FarmerAgent()
