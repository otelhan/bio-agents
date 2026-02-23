"""
Orchestrator: classifies which agent to use when no @mention is present.
Uses a fast, cheap Claude call with minimal tokens.
"""
import anthropic
from config import get_settings

CLASSIFIER_SYSTEM = """You route user messages to one of three agents.
Reply with exactly one word — no punctuation, no explanation:
  designer  (material design, BC pellicle properties, images, experiments)
  farmer    (production data, yields, recipes, spreadsheets, runs, CSV)
  cfo       (costs, revenue, profit, financial model, TEM, scenarios)"""


async def classify_agent(history: list[dict], new_message: str) -> str:
    """
    Returns 'designer', 'farmer', or 'cfo' based on conversation context.
    Falls back to 'cfo' on any error.
    """
    client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)

    # Use last 6 messages for context, keep it cheap
    context = history[-6:] + [{"role": "user", "content": new_message}]

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            system=CLASSIFIER_SYSTEM,
            messages=context,
            max_tokens=5,
        )
        agent = response.content[0].text.strip().lower()
        if agent in ("designer", "farmer", "cfo"):
            return agent
    except Exception:
        pass

    return "cfo"  # safe default
