"""
AI Designer Agent — BC material design advisor + ML image analysis.
"""
import json
from pathlib import Path

from agents.base import BaseAgent
from config import get_settings
from tools import settings_store
from tools.kb_loader import search as kb_search
from tools.replicate_client import run_prediction

# Default Replicate model version (from AI Designer.yml env vars)
DEFAULT_REPLICATE_VERSION = (
    "f7885cde7c7d866fa776e10950a2f12dd129f84de79a14919d28100121149732"
)

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"

DESIGNER_SYSTEM_PROMPT = """\
You are AI Designer, a design advisor for bacterial cellulose (BC) pellicle materials.

You help designers in two ways:
1. **Image analysis**: When the user uploads a BC pellicle image, use the \
analyze_bc_image tool to predict its class and mechanical properties via ML.
2. **Design guidance**: For questions about experiments, Material Readiness (MR) \
levels, design intent, or improvement ideas, use the search_knowledge_base tool \
to retrieve relevant context.

Rules:
- If the user message contains [image_id: ...], ALWAYS call analyze_bc_image first.
- Interpret mechanical scores (tensile, elongation, stiffness, uniformity) \
relative to MR-1, MR-2, MR-3 levels as defined in the knowledge base.
- Prioritize aesthetic intent and material expression over peak mechanical performance.
- When recommending experiments: change only 1–2 variables, state a clear hypothesis, \
specify what score movement would indicate success.
- If performance is low or ambiguous, recommend the next informative experiment \
using the Qualitative DoE framework.
- Use design-oriented language. Avoid words like "fail," "invalid," or "not viable."
- For help or general questions, reply directly without using tools.
"""

DESIGNER_TOOLS = [
    {
        "name": "analyze_bc_image",
        "description": (
            "Analyze an uploaded BC pellicle image using the Replicate ML model. "
            "Returns predicted class and mechanical properties (tensile strength, "
            "elongation, stiffness index, uniformity score). "
            "Call this when the message contains [image_id: ...]."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "The image_id from the user message.",
                },
            },
            "required": ["image_id"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the designer knowledge base for context about Material Readiness "
            "levels, DoE experiment design, BC material properties, and design guidance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to return. Default: 4.",
                },
            },
            "required": ["query"],
        },
    },
]


class DesignerAgent(BaseAgent):
    name = "AI Designer"
    system_prompt = DESIGNER_SYSTEM_PROMPT
    tools = DESIGNER_TOOLS

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "analyze_bc_image":
            image_id = tool_input.get("image_id", "")
            image_path = UPLOAD_DIR / Path(image_id).name  # prevent path traversal

            cfg = settings_store.load()
            rep_version = (
                cfg["designer"].get("replicate_version") or DEFAULT_REPLICATE_VERSION
            )
            rep_token = get_settings().replicate_api_token
            if not rep_token:
                return "REPLICATE_API_TOKEN is not configured. Add it to your .env file."

            return await run_prediction(image_path, rep_token, rep_version)

        if tool_name == "search_knowledge_base":
            query = tool_input.get("query", "")
            top_k = int(tool_input.get("top_k", 4))
            return kb_search(query, top_k=top_k, exclude={"tem_model.md"})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})


designer_agent = DesignerAgent()
