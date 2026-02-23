// ─── State ────────────────────────────────────────────────
let sessionId = null;
let isStreaming = false;

const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const suggestedEl = document.getElementById("suggested");

// ─── Suggested questions ──────────────────────────────────
async function loadSuggested() {
  try {
    const res = await fetch("/api/suggested?agent=cfo");
    const data = await res.json();
    suggestedEl.innerHTML = "";
    data.questions.forEach((q) => {
      const btn = document.createElement("button");
      btn.className = "suggested-btn";
      btn.textContent = q;
      btn.onclick = () => { input.value = "@cfo " + q; input.focus(); };
      suggestedEl.appendChild(btn);
    });
  } catch (e) {
    console.warn("Could not load suggested questions", e);
  }
}

// ─── Simple markdown renderer ─────────────────────────────
function renderMarkdown(text) {
  // Tables
  text = text.replace(/^\|(.+)\|\s*\n\|[-| :]+\|\s*\n((?:\|.+\|\s*\n?)*)/gm, (match, header, rows) => {
    const ths = header.split("|").filter(Boolean).map(h => `<th>${h.trim()}</th>`).join("");
    const trs = rows.trim().split("\n").map(row => {
      const tds = row.split("|").filter(Boolean).map(c => `<td>${c.trim()}</td>`).join("");
      return `<tr>${tds}</tr>`;
    }).join("");
    return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
  });
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic
  text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Code inline
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Line breaks
  text = text.replace(/\n/g, "<br>");
  return text;
}

// ─── Message helpers ──────────────────────────────────────
function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "message message--user";
  el.textContent = text;
  chat.appendChild(el);
  scrollToBottom();
  return el;
}

function addAgentMessage(agentName) {
  const wrapper = document.createElement("div");
  wrapper.className = "message message--agent";

  const agentKey = agentName.toLowerCase().replace("ai ", "");
  const label = document.createElement("div");
  label.className = `message__label message__label--${agentKey}`;
  label.textContent = agentName;

  const body = document.createElement("div");
  body.className = "message__body";

  wrapper.appendChild(label);
  wrapper.appendChild(body);
  chat.appendChild(wrapper);
  scrollToBottom();
  return body;
}

function addTypingIndicator() {
  const el = document.createElement("div");
  el.className = "typing";
  el.innerHTML = "<span></span><span></span><span></span>";
  chat.appendChild(el);
  scrollToBottom();
  return el;
}

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

// ─── Send message ─────────────────────────────────────────
async function sendMessage(text) {
  if (!text.trim() || isStreaming) return;

  isStreaming = true;
  sendBtn.disabled = true;
  suggestedEl.style.display = "none";

  addUserMessage(text);
  const typing = addTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let agentBody = null;
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.type === "session_id") {
          sessionId = payload.session_id;
        } else if (payload.type === "agent") {
          typing.remove();
          agentBody = addAgentMessage(payload.agent);
        } else if (payload.type === "text") {
          if (agentBody) {
            agentBody.innerHTML = renderMarkdown(
              (agentBody._raw || "") + payload.content
            );
            agentBody._raw = (agentBody._raw || "") + payload.content;
            scrollToBottom();
          }
        } else if (payload.type === "done") {
          break;
        }
      }
    }
  } catch (err) {
    typing.remove();
    const errEl = document.createElement("div");
    errEl.className = "message message--agent";
    errEl.textContent = "Error: " + err.message;
    chat.appendChild(errEl);
  } finally {
    isStreaming = false;
    sendBtn.disabled = false;
  }
}

// ─── Form submit ──────────────────────────────────────────
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  sendMessage(text);
});

// Auto-resize textarea
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 120) + "px";
});

// Cmd/Ctrl+Enter to send
input.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    form.dispatchEvent(new Event("submit"));
  }
});

// ─── Init ─────────────────────────────────────────────────
loadSuggested();
