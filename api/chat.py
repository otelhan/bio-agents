import json
import uuid
from fastapi import APIRouter, Request, Cookie
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.cfo import cfo_agent
from router.mention_router import parse_message
from session.context_store import context_store

router = APIRouter()

AGENT_REGISTRY = {
    "cfo": cfo_agent,
    # "designer": designer_agent,  # added in Phase 4
    # "farmer": farmer_agent,      # added in Phase 3
}

SUGGESTED_QUESTIONS = {
    "cfo": [
        "What is the scenario using all defaults?",
        "Why is profit negative?",
        "What is driving profit/kg? What should I change to improve this?",
        "Run a scenario with contamination loss reduced to 4%.",
    ]
}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    image_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    parsed = parse_message(request.message, request.image_id)

    # Default to CFO in Phase 1 (orchestrator added in Phase 2)
    target = parsed.target_agent or "cfo"
    agent = AGENT_REGISTRY.get(target, cfo_agent)

    history = context_store.get_claude_messages(session_id)
    user_content = parsed.clean_text or request.message

    context_store.add_message(session_id, "user", "user", user_content)

    async def event_stream():
        full_response = []
        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
        yield f"data: {json.dumps({'type': 'agent', 'agent': agent.name})}\n\n"

        messages = history + [{"role": "user", "content": user_content}]

        async for chunk in agent.stream_response(messages):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

        complete_response = "".join(full_response)
        context_store.add_message(session_id, "assistant", agent.name, complete_response)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/suggested")
async def suggested_questions(agent: str = "cfo"):
    return {"questions": SUGGESTED_QUESTIONS.get(agent, [])}
