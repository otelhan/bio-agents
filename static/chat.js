// ─── Session ──────────────────────────────────────────────
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? match[2] : null;
}

let sessionId = getCookie("bio_session") || null;
let isStreaming = false;
let activeAgent = null;

// ─── Pending image state ───────────────────────────────────
let pendingImageId  = null;
let pendingImageUrl = null;

// ─── DOM refs ─────────────────────────────────────────────
const chat           = document.getElementById("chat");
const form           = document.getElementById("form");
const input          = document.getElementById("input");
const sendBtn        = document.getElementById("send-btn");
let   suggestedEl    = document.getElementById("suggested");
const mentionMenu    = document.getElementById("mention-menu");
const clearBtn       = document.getElementById("clear-btn");
const imageInput     = document.getElementById("image-input");
const imagePreviewBar = document.getElementById("image-preview-bar");
const previewThumb   = document.getElementById("preview-thumb");
const previewRemove  = document.getElementById("preview-remove");

// ─── Agent badge activation ───────────────────────────────
function setActiveAgent(agentKey) {
  document.querySelectorAll(".badge").forEach(b => b.classList.remove("active"));
  if (agentKey) {
    const badge = document.querySelector(`.badge--${agentKey}`);
    if (badge) badge.classList.add("active");
  }
}

// ─── Suggested questions ──────────────────────────────────
async function loadSuggested() {
  // Always query the DOM directly so this works after chat is rebuilt
  const el = document.getElementById("suggested");
  if (!el) return;
  try {
    const agents = ["designer", "farmer", "cfo"];
    const results = await Promise.all(
      agents.map(a => fetch(`/api/suggested?agent=${a}`).then(r => r.json()))
    );
    el.innerHTML = "";
    el.style.display = "";
    agents.forEach((agent, i) => {
      (results[i].questions || []).forEach(q => {
        const btn = document.createElement("button");
        btn.className = `suggested-btn suggested-btn--${agent}`;
        btn.textContent = q;
        btn.onclick = () => {
          input.value = `@${agent} ${q}`;
          input.focus();
          el.style.display = "none";
        };
        el.appendChild(btn);
      });
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
function addUserMessage(text, imageUrl) {
  const el = document.createElement("div");
  el.className = "message message--user";
  if (imageUrl) {
    const img = document.createElement("img");
    img.className = "msg-image";
    img.src = imageUrl;
    el.appendChild(img);
  }
  if (text) {
    const span = document.createElement("span");
    span.textContent = text;
    el.appendChild(span);
  }
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
  body.className = `message__body message__body--${agentKey}`;
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

// ─── Image upload ─────────────────────────────────────────
async function handleImageFile(file) {
  if (!file || !file.type.startsWith("image/")) return;

  // Show local preview immediately
  if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
  pendingImageUrl = URL.createObjectURL(file);
  previewThumb.src = pendingImageUrl;
  imagePreviewBar.hidden = false;
  pendingImageId = null; // will be set after upload

  // Upload to server
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/upload/image", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const data = await res.json();
    pendingImageId = data.image_id;
  } catch (err) {
    console.error("Image upload failed:", err);
    clearImagePreview();
  }
}

function clearImagePreview() {
  pendingImageId = null;
  if (pendingImageUrl) URL.revokeObjectURL(pendingImageUrl);
  pendingImageUrl = null;
  previewThumb.src = "";
  imagePreviewBar.hidden = true;
}

imageInput.addEventListener("change", async (e) => {
  await handleImageFile(e.target.files[0]);
  imageInput.value = ""; // allow re-selecting same file
});

previewRemove.addEventListener("click", clearImagePreview);

// ─── Drag-and-drop ────────────────────────────────────────
document.body.addEventListener("dragover", (e) => e.preventDefault());
document.body.addEventListener("drop", async (e) => {
  e.preventDefault();
  const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith("image/"));
  if (file) await handleImageFile(file);
});

// ─── Send message ─────────────────────────────────────────
async function sendMessage(text) {
  if (!text.trim() && !pendingImageId) return;
  if (isStreaming) return;

  isStreaming = true;
  sendBtn.disabled = true;
  suggestedEl.style.display = "none";

  // Capture and clear pending image before async work
  const imageUrl = pendingImageUrl;
  const imageId  = pendingImageId;
  clearImagePreview();

  addUserMessage(text, imageUrl);
  const typing = addTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId, image_id: imageId }),
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

mentionItems.forEach((item) => {
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

  // Enter to send, Shift+Enter for new line
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
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
  if (!text && !pendingImageId) return;
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
  suggestedEl = document.getElementById("suggested");
  loadSuggested();
  setActiveAgent(null);
});

// ─── Init ─────────────────────────────────────────────────
loadSuggested();
