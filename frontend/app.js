/* ==================================================================
   AI Developer Agent — Frontend Logic
   ================================================================== */

const API_URL = "http://localhost:8000";

// ── DOM references ──────────────────────────────────────────────
const messagesEl    = document.getElementById("messages");
const chatWindow    = document.getElementById("chatWindow");
const questionInput = document.getElementById("questionInput");
const sendBtn       = document.getElementById("sendBtn");
const clearBtn      = document.getElementById("clearBtn");
const quickChips    = document.getElementById("quickChips");
const menuToggle    = document.getElementById("menuToggle");
const sidebar       = document.getElementById("sidebar");
const overlay       = document.getElementById("overlay");
const statusBadge   = document.getElementById("statusBadge");
const statusText    = document.getElementById("statusText");
const sendIcon      = sendBtn.querySelector(".send-icon");
const spinner       = sendBtn.querySelector(".spinner");

let isProcessing = false;

// ── Helpers ─────────────────────────────────────────────────────

function toPlainText(value) {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function scrollToBottom() {
  chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: "smooth" });
}

/** Minimal markdown-ish formatting for agent responses */
function formatText(text) {
  const raw = toPlainText(text);
  const hasMarked = typeof window !== "undefined" && typeof window.marked !== "undefined";
  const hasPurify = typeof window !== "undefined" && typeof window.DOMPurify !== "undefined";

  if (!hasMarked) {
    return raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
  }

  const rendered = window.marked.parse(raw, { breaks: true, gfm: true });
  if (!hasPurify) return rendered;
  return window.DOMPurify.sanitize(rendered);
}

/** Extract "📁 Sources: [...]" line and return { body, sources[] } */
function extractSources(text) {
  const sourceLine = text.match(/📁\s*Sources?:\s*(.+)/i);
  if (!sourceLine) return { body: text, sources: [] };

  const body = text.replace(sourceLine[0], "").trim();
  const raw  = sourceLine[1];

  // Prefer splitting by comma to preserve full Windows paths + function refs
  const sources = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  if (sources.length === 0) {
    return { body, sources: [raw.trim()] };
  }
  return { body, sources };
}

// ── Message rendering ───────────────────────────────────────────

function addMessage(text, sender) {
  text = toPlainText(text);
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = sender === "user" ? "👤" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (sender === "agent") {
    const { body, sources } = extractSources(text);
    bubble.innerHTML = formatText(body);

    // Add copy buttons to fenced code blocks
    bubble.querySelectorAll("pre").forEach((pre) => {
      if (pre.closest(".codeblock")) return;
      const wrapper = document.createElement("div");
      wrapper.className = "codeblock";
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(pre);

      const btn = document.createElement("button");
      btn.className = "copy-btn";
      btn.type = "button";
      btn.textContent = "Copy";
      btn.addEventListener("click", async () => {
        const codeEl = pre.querySelector("code");
        const codeText = codeEl ? codeEl.textContent : pre.textContent;
        try {
          await navigator.clipboard.writeText(codeText);
          btn.textContent = "Copied";
          setTimeout(() => (btn.textContent = "Copy"), 1200);
        } catch {
          btn.textContent = "Failed";
          setTimeout(() => (btn.textContent = "Copy"), 1200);
        }
      });
      wrapper.appendChild(btn);
    });

    if (sources.length > 0) {
      const tagsContainer = document.createElement("div");
      tagsContainer.className = "source-tags";
      sources.forEach((src) => {
        const tag = document.createElement("span");
        tag.className = "source-tag";
        tag.textContent = src;
        tagsContainer.appendChild(tag);
      });
      bubble.appendChild(tagsContainer);
    }
  } else {
    bubble.textContent = text;
  }

  msg.appendChild(avatar);
  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
}

// ── Typing indicator ────────────────────────────────────────────

function showTypingIndicator() {
  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.id = "typingIndicator";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = "🤖";

  const dots = document.createElement("div");
  dots.className = "typing-dots";
  dots.innerHTML = "<span></span><span></span><span></span>";

  el.appendChild(avatar);
  el.appendChild(dots);
  messagesEl.appendChild(el);
  scrollToBottom();
}

function hideTypingIndicator() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

// ── Loading state on send button ────────────────────────────────

function setLoading(loading) {
  isProcessing = loading;
  sendBtn.disabled = loading;
  sendIcon.style.display = loading ? "none" : "block";
  spinner.style.display  = loading ? "block" : "none";
}

// ── Send message ────────────────────────────────────────────────

async function sendMessage(question) {
  question = question.trim();
  if (!question || isProcessing) return;

  // Show user bubble
  addMessage(question, "user");
  questionInput.value = "";
  questionInput.style.height = "auto";

  // Show typing indicator + loading state
  setLoading(true);
  showTypingIndicator();

  try {
    const res = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await res.json();

    hideTypingIndicator();

    if (data.status === "success" && data.answer) {
      let text = toPlainText(data.answer);

      if (Array.isArray(data.sources) && data.sources.length > 0) {
        text += "\n\n📁 Sources: " + data.sources.join(", ");
      }

      addMessage(text, "agent");
    } else {
      const errorText = data && Object.prototype.hasOwnProperty.call(data, "error") ? toPlainText(data.error) : "Unknown error";
      addMessage("⚠️ Something went wrong: " + errorText, "agent");
    }
  } catch (err) {
    hideTypingIndicator();
    addMessage(
      "⚠️ Could not reach the agent. Make sure the backend is running on port 8000.\n\n" +
      "Start it with: `uvicorn backend.main:app --reload --port 8000`\n\n" +
      "Error: " + err.message,
      "agent"
    );
  } finally {
    setLoading(false);
    questionInput.focus();
  }
}

// ── Welcome message ─────────────────────────────────────────────

function showWelcomeMessage() {
  addMessage(
    "👋 Hi! I'm your AI Developer Agent. I have access to your codebase " +
    "and documentation. Ask me anything — from how OAuth works to what " +
    "a specific function does.\n\n" +
    "Try one of the **quick questions** in the sidebar, or type your own below!",
    "agent"
  );
}

// ── Health check ────────────────────────────────────────────────

async function checkHealth() {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (res.ok) {
      statusBadge.className = "status-badge online";
      statusText.textContent = "Online";
    } else {
      throw new Error("unhealthy");
    }
  } catch {
    statusBadge.className = "status-badge offline";
    statusText.textContent = "Offline";
  }
}

// ── Event listeners ─────────────────────────────────────────────

// Send button
sendBtn.addEventListener("click", () => {
  sendMessage(questionInput.value);
});

// Enter to send, Shift+Enter for newline
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(questionInput.value);
  }
});

// Auto-grow textarea
questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
});

// Clear button
clearBtn.addEventListener("click", () => {
  messagesEl.innerHTML = "";
  showWelcomeMessage();
});

// Quick question chips
quickChips.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const question = chip.getAttribute("data-question");
  if (question) {
    // Close sidebar on mobile
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    sendMessage(question);
  }
});

// Mobile sidebar toggle
menuToggle.addEventListener("click", () => {
  sidebar.classList.toggle("open");
  overlay.classList.toggle("active");
});

overlay.addEventListener("click", () => {
  sidebar.classList.remove("open");
  overlay.classList.remove("active");
});

// ── Init ────────────────────────────────────────────────────────
showWelcomeMessage();
checkHealth();
// Re-check health every 30 seconds
setInterval(checkHealth, 30000);
