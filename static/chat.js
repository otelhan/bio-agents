// ─── Session ──────────────────────────────────────────────
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? match[2] : null;
}

let sessionId = getCookie("bio_session") || null;
let isStreaming = false;
let activeAgent = null;

// ─── DOM refs ─────────────────────────────────────────────
const chat       = document.getElementById("chat");
const form       = document.getElementById("form");
const input      = document.getElementById("input");
const sendBtn    = document.getElementById("send-btn");
const suggestedEl = document.getElementById("suggested");
const mentionMenu = document.getElementById("mention-menu");
const clearBtn   = document.getElementById("clear-btn");

// ─── Agent badge activation ───────────────────────────────
function setActiveAgent(agentKey) {
  document.querySelectorAll(".badge").forEach(b => b.classList.remove("active"));
  if (agentKey) {
    const badge = document.querySelector(`.badge--${agentKey}`);
    if (badge) badge.classList.add("active");
  }
}

// ─── Suggested questions ──────────────────────────────────
async function loadSuggested(agent = "cfo") {
  try {
    const res = await fetch(`/api/suggested?agent=${agent}`);
    const data = await res.json();
    suggestedEl.innerHTML = "";
    data.questions.forEach((q) => {
      const btn = document.createElement("button");
      btn.className = "suggested-btn";
      btn.textContent = q;
      btn.onclick = () => {
        input.value = `@${agent} ${q}`;
        input.focus();
        suggestedEl.style.display = "none";
      };
      suggestedEl.appendChild(btn);
    });
  } catch (e) {
    console.warn("Could not load suggested questions", e);
  }
}

// ─── Markdown renderer ────────────────────────────────────
function renderMarkdown(text) {
  // Tables
  text = text.replace(
    /^\|(.+)\|\s*\n\|[-| :]+\|\s*\n((?:\|.+\|\s*\n?)*)/gm,
    (_, header, rows) => {
      const ths = header.split("|").filter(Boolean)
        .map(h => `<th>${h.trim()}</th>`).join("");
      const trs = rows.trim().split("\n").map(row => {
        const tds = row.split("|").filter(Boolean)
          .map(c => `<td>${c.trim()}</td>`).join("");
        return `<tr>${tds}</tr>`;
      }).join("");
      return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
    }
  );
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
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
}

function addAgentMessage(agentName, agentKey) {
  const wrapper = document.createElement("div");
  wrapper.className = "message message--agent";

  const label = document.createElement("div");
  label.className = `message__label message__label--${agentKey}`;
  label.textContent = agentName;

  const body = document.createElement("div");
  body.className = "message__body";
  body._raw = "";

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
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let payload;
        try { payload = JSON.parse(line.slice(6)); } catch { continue; }

        if (payload.type === "session_id") {
          sessionId = payload.session_id;
        } else if (payload.type === "agent") {
          typing.remove();
          activeAgent = payload.agent_key;
          setActiveAgent(activeAgent);
          agentBody = addAgentMessage(payload.agent, payload.agent_key);
        } else if (payload.type === "text") {
          if (agentBody) {
            agentBody._raw += payload.content;
            agentBody.innerHTML = renderMarkdown(agentBody._raw);
            scrollToBottom();
          }
        } else if (payload.type === "error") {
          typing.remove();
          const errEl = document.createElement("div");
          errEl.className = "message message--agent";
          errEl.textContent = "Error: " + payload.content;
          chat.appendChild(errEl);
        } else if (payload.type === "done") {
          break;
        }
      }
    }
  } catch (err) {
    typing.remove();
    const errEl = document.createElement("div");
    errEl.className = "message message--agent";
    errEl.textContent = "Connection error: " + err.message;
    chat.appendChild(errEl);
  } finally {
    isStreaming = false;
    sendBtn.disabled = false;
    setActiveAgent(null);
  }
}

// ─── @mention autocomplete ────────────────────────────────
const mentionItems = mentionMenu.querySelectorAll(".mention-item");
let mentionIndex = -1;

function showMentionMenu() {
  mentionMenu.hidden = false;
  mentionIndex = -1;
  mentionItems.forEach(i => i.classList.remove("selected"));
}

function hideMentionMenu() {
  mentionMenu.hidden = true;
  mentionIndex = -1;
}

function selectMention(mention) {
  const val = input.value;
  const atPos = val.lastIndexOf("@");
  input.value = val.slice(0, atPos) + mention + " ";
  hideMentionMenu();
  input.focus();
}

mentionItems.forEach((item, i) => {
  item.addEventListener("mousedown", (e) => {
    e.preventDefault();
    selectMention(item.dataset.mention);
  });
});

input.addEventListener("input", () => {
  // Auto-resize
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 120) + "px";

  // Show mention menu when user types @
  const val = input.value;
  const atPos = val.lastIndexOf("@");
  if (atPos !== -1 && atPos === val.length - 1) {
    showMentionMenu();
  } else if (atPos !== -1) {
    const partial = val.slice(atPos + 1).toLowerCase();
    const hasMatch = ["designer", "farmer", "cfo"].some(a => a.startsWith(partial));
    if (hasMatch && !val.slice(atPos).includes(" ")) {
      showMentionMenu();
    } else {
      hideMentionMenu();
    }
  } else {
    hideMentionMenu();
  }
});

input.addEventListener("keydown", (e) => {
  // Navigate autocomplete
  if (!mentionMenu.hidden) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      mentionIndex = (mentionIndex + 1) % mentionItems.length;
      mentionItems.forEach((i, idx) => i.classList.toggle("selected", idx === mentionIndex));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      mentionIndex = (mentionIndex - 1 + mentionItems.length) % mentionItems.length;
      mentionItems.forEach((i, idx) => i.classList.toggle("selected", idx === mentionIndex));
      return;
    }
    if (e.key === "Enter" || e.key === "Tab") {
      if (mentionIndex >= 0) {
        e.preventDefault();
        selectMention(mentionItems[mentionIndex].dataset.mention);
        return;
      }
    }
    if (e.key === "Escape") {
      hideMentionMenu();
      return;
    }
  }

  // Cmd/Ctrl+Enter to send
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    form.dispatchEvent(new Event("submit"));
  }
});

document.addEventListener("click", (e) => {
  if (!mentionMenu.contains(e.target) && e.target !== input) {
    hideMentionMenu();
  }
});

// ─── Form submit ──────────────────────────────────────────
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  hideMentionMenu();
  sendMessage(text);
});

// ─── Clear conversation ───────────────────────────────────
clearBtn.addEventListener("click", async () => {
  await fetch("/api/session", { method: "DELETE" });
  sessionId = null;
  chat.innerHTML = '<div class="suggested" id="suggested"></div>';
  const newSuggested = document.getElementById("suggested");
  loadSuggested("cfo");
  setActiveAgent(null);
});

// ─── Init ─────────────────────────────────────────────────
loadSuggested("cfo");
