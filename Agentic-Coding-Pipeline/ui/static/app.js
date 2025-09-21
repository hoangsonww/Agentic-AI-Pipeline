const timelineEl = document.getElementById("timeline");
const chatEl = document.getElementById("chat-stream");
const controlsEl = document.getElementById("controls");
const launcherForm = document.getElementById("task-launcher");
const launcherButton = launcherForm.querySelector("button");
const taskField = document.getElementById("task");

let currentSession = null;

const statusClassMap = {
  pending: "stage--pending",
  active: "stage--active",
  awaiting: "stage--awaiting",
  completed: "stage--completed",
  failed: "stage--failed",
};

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function renderMarkdown(text) {
  const codeBlock = /```(\w+)?\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let result = "";
  let match;
  while ((match = codeBlock.exec(text)) !== null) {
    result += renderInlineMarkdown(text.slice(lastIndex, match.index));
    const code = escapeHtml(match[2].trim());
    result += `<pre><code>${code}</code></pre>`;
    lastIndex = match.index + match[0].length;
  }
  result += renderInlineMarkdown(text.slice(lastIndex));
  return result;
}

async function createSession(task) {
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Unable to create session");
  }
  return response.json();
}

async function sendFeedback(action, comment) {
  const response = await fetch(`/api/sessions/${currentSession.session_id}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, comment }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Unable to submit feedback");
  }
  return response.json();
}

async function advance(action) {
  const response = await fetch(`/api/sessions/${currentSession.session_id}/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Unable to advance session");
  }
  return response.json();
}

function renderTimeline(timeline) {
  timelineEl.innerHTML = "";
  timeline.forEach((stage) => {
    const stageEl = document.createElement("article");
    stageEl.className = `stage ${statusClassMap[stage.status] || ""}`;
    stageEl.innerHTML = `
      <h3>${stage.title}</h3>
      <p>${stage.description}</p>
      <small>${stage.status.replace(/-/g, " ")}</small>
    `;
    timelineEl.appendChild(stageEl);
  });
}

function renderMessages(messages) {
  chatEl.innerHTML = "";
  messages.forEach((msg) => {
    const article = document.createElement("article");
    article.className = `message role-${msg.role}`;
    const header = document.createElement("header");
    const roleLabel = document.createElement("span");
    roleLabel.textContent = msg.role === "assistant" ? "Agent swarm" : "You";
    const stamp = document.createElement("span");
    stamp.textContent = new Date(msg.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    header.appendChild(roleLabel);
    header.appendChild(stamp);

    const content = document.createElement("div");
    content.className = "content";
    content.innerHTML = renderMarkdown(msg.content);

    article.appendChild(header);
    article.appendChild(content);

    if (msg.attachments && msg.attachments.proposed_code) {
      const pre = document.createElement("pre");
      pre.innerText = msg.attachments.proposed_code;
      article.appendChild(pre);
    }

    if (msg.attachments && msg.attachments.test_output) {
      const pre = document.createElement("pre");
      pre.innerText = msg.attachments.test_output;
      article.appendChild(pre);
    }

    if (msg.attachments && msg.attachments.qa_reports) {
      Object.entries(msg.attachments.qa_reports).forEach(([agent, report]) => {
        const block = document.createElement("pre");
        block.innerText = `${agent}:\n${report}`;
        article.appendChild(block);
      });
    }

    chatEl.appendChild(article);
  });
  chatEl.scrollTop = chatEl.scrollHeight;
}

function showError(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4200);
}

function renderControls(session) {
  controlsEl.innerHTML = "";
  if (!session) {
    controlsEl.innerHTML = '<p class="hint">Launch a mission to unlock human review controls.</p>';
    return;
  }

  if (session.stage === "review") {
    controlsEl.innerHTML = `
      <p class="hint">Review the agents' proposal. Request a revision with notes or approve to continue.</p>
      <textarea id="feedback" placeholder="e.g. Cover edge cases for empty payloads and add docstrings"></textarea>
      <div class="button-row">
        <button class="button secondary" id="revise">Request revision</button>
        <button class="button primary" id="approve">Approve & continue</button>
      </div>
    `;
    const feedback = document.getElementById("feedback");
    document.getElementById("revise").addEventListener("click", async () => {
      if (!feedback.value.trim()) {
        feedback.focus();
        showError("Add feedback before requesting another coding pass.");
        return;
      }
      try {
        controlsEl.classList.add("busy");
        currentSession = await sendFeedback("revise", feedback.value.trim());
        renderAll();
      } catch (error) {
        showError(error.message);
      } finally {
        controlsEl.classList.remove("busy");
      }
    });
    document.getElementById("approve").addEventListener("click", async () => {
      try {
        controlsEl.classList.add("busy");
        currentSession = await sendFeedback("approve", feedback.value.trim() || undefined);
        renderAll();
      } catch (error) {
        showError(error.message);
      } finally {
        controlsEl.classList.remove("busy");
      }
    });
    return;
  }

  if (session.stage === "testing") {
    controlsEl.innerHTML = `
      <p class="hint">Trigger automated regression tests when you're ready.</p>
      <div class="button-row">
        <button class="button primary" id="run-tests">Run tests</button>
      </div>
    `;
    document.getElementById("run-tests").addEventListener("click", async () => {
      try {
        controlsEl.classList.add("busy");
        currentSession = await advance("run_tests");
        renderAll();
      } catch (error) {
        showError(error.message);
      } finally {
        controlsEl.classList.remove("busy");
      }
    });
    return;
  }

  if (session.stage === "qa") {
    controlsEl.innerHTML = `
      <p class="hint">All checks are green. Forward the build to the QA agent for release notes.</p>
      <div class="button-row">
        <button class="button primary" id="run-qa">Send to QA</button>
      </div>
    `;
    document.getElementById("run-qa").addEventListener("click", async () => {
      try {
        controlsEl.classList.add("busy");
        currentSession = await advance("send_to_qa");
        renderAll();
      } catch (error) {
        showError(error.message);
      } finally {
        controlsEl.classList.remove("busy");
      }
    });
    return;
  }

  if (session.stage === "complete") {
    controlsEl.innerHTML = `
      <p class="hint">Pipeline complete. Run another mission from the launcher above.</p>
      <div class="button-row">
        <button class="button secondary" id="reset">Start another build</button>
      </div>
    `;
    document.getElementById("reset").addEventListener("click", () => {
      currentSession = null;
      launcherForm.classList.remove("disabled");
      launcherButton.disabled = false;
      taskField.disabled = false;
      renderAll();
      chatEl.innerHTML = "";
      timelineEl.innerHTML = "";
    });
    return;
  }

  controlsEl.innerHTML = '<p class="hint">The pipeline is processing… hang tight.</p>';
}

function renderAll() {
  if (!currentSession) {
    renderControls(null);
    return;
  }
  renderTimeline(currentSession.timeline);
  renderMessages(currentSession.messages);
  renderControls(currentSession);
}

launcherForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = taskField.value.trim();
  if (!task) return;
  launcherButton.disabled = true;
  taskField.disabled = true;
  launcherForm.classList.add("disabled");
  try {
    currentSession = await createSession(task);
    renderAll();
  } catch (error) {
    launcherButton.disabled = false;
    taskField.disabled = false;
    showError(error.message);
  }
});

renderAll();
