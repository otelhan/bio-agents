import json
import uuid
from fastapi import APIRouter, Cookie
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from agents.cfo import cfo_agent
from agents.farmer import farmer_agent
from router.mention_router import parse_message
from router.orchestrator import classify_agent
from session.context_store import context_store

router = APIRouter()

AGENT_REGISTRY = {
    "cfo": cfo_agent,
    "farmer": farmer_agent,
    # "designer": designer_agent,  # Phase 4
}

SUGGESTED_QUESTIONS = {
    "cfo": [
        "What is the scenario using all defaults?",
        "Why is profit negative?",
        "What is driving profit/kg? What should I change to improve this?",
        "Run a scenario with contamination loss reduced to 4%.",
    ],
    "farmer": [
        "What was our best recipe for yield in 2024?",
        "Show yield by recipe as a table",
        "Which variables explain variation in yield the best?",
        "Show the production dataset from 2024",
    ],
    "designer": [
        "How can I improve my bacterial cellulose pellicles?",
        "What are the best ways to design my experiments?",
        "What are some good applications of Bacterial Cellulose?",
    ],
}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    image_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    # Resolve or create session ID
    session_id = request.session_id or str(uuid.uuid4())
    parsed = parse_message(request.message, request.image_id)
    user_content = parsed.clean_text or request.message

    history = context_store.get_claude_messages(session_id)

    NOT_YET = {"designer": "AI Designer", "farmer": "AI Farmer"}

    # If user explicitly mentioned an agent not yet implemented, say so
    if parsed.target_agent in NOT_YET and parsed.target_agent not in AGENT_REGISTRY:
        agent_label = NOT_YET[parsed.target_agent]
        async def not_implemented():
            msg = f"{agent_label} is coming soon! For now, only @cfo is available."
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'type': 'agent', 'agent': agent_label, 'agent_key': parsed.target_agent})}\n\n"
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(not_implemented(), media_type="text/event-stream")

    # Determine target agent — use orchestrator if no @mention
    if parsed.target_agent and parsed.target_agent in AGENT_REGISTRY:
        target = parsed.target_agent
    else:
        target = await classify_agent(history, user_content)
        if target not in AGENT_REGISTRY:
            target = "cfo"

    agent = AGENT_REGISTRY[target]
    context_store.add_message(session_id, "user", "user", user_content)

    async def event_stream():
        full_response = []

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
        yield f"data: {json.dumps({'type': 'agent', 'agent': agent.name, 'agent_key': target})}\n\n"

        messages = history + [{"role": "user", "content": user_content}]

        try:
            async for chunk in agent.stream_response(messages):
                full_response.append(chunk)
                yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        complete_response = "".join(full_response)
        if complete_response:
            context_store.add_message(session_id, "assistant", agent.name, complete_response)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    # Set session cookie so the browser persists the session across page refreshes
    response.set_cookie(
        key="bio_session",
        value=session_id,
        max_age=60 * 60 * 24,  # 24 hours
        samesite="lax",
        httponly=False,  # JS needs to read it for the initial page load
    )
    return response


@router.get("/suggested")
async def suggested_questions(agent: str = "cfo"):
    return {"questions": SUGGESTED_QUESTIONS.get(agent, [])}


@router.delete("/session")
async def clear_session(bio_session: str = Cookie(default=None)):
    if bio_session:
        context_store.clear(bio_session)
    response = JSONResponse({"cleared": True})
    response.delete_cookie("bio_session")
    return response
