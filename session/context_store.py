from collections import defaultdict
from datetime import datetime

MAX_MESSAGES = 50


class ContextStore:
    def __init__(self):
        self._sessions: dict[str, list[dict]] = defaultdict(list)

    def add_message(self, session_id: str, role: str, agent: str, content: str):
        self._sessions[session_id].append({
            "role": role,
            "agent": agent,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(self._sessions[session_id]) > MAX_MESSAGES:
            self._sessions[session_id] = self._sessions[session_id][-MAX_MESSAGES:]

    def get_claude_messages(self, session_id: str) -> list[dict]:
        """Return conversation history in Claude API format with agent prefixes."""
        out = []
        for m in self._sessions[session_id]:
            prefix = f"[{m['agent']}]: " if m["role"] == "assistant" else ""
            out.append({"role": m["role"], "content": prefix + m["content"]})
        return out

    def clear(self, session_id: str):
        self._sessions.pop(session_id, None)


# Singleton
context_store = ContextStore()
