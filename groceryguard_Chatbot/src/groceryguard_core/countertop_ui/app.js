// I generate a random conversation ID for each session so the server can keep messages organized
function newConversationId() {
  const x = crypto.getRandomValues(new Uint32Array(4));
  return `gg-${x[0].toString(16)}${x[1].toString(16)}-${x[2].toString(16)}`;
}

// I check if I've already started a conversation with an ID in localStorage, or create a new one
function getCid() {
  let cid = localStorage.getItem("gg_conversation_id");
  if (!cid) {
    cid = newConversationId();
    localStorage.setItem("gg_conversation_id", cid);
  }
  return cid;
}

// I save the conversation ID to localStorage and update the display
function setCid(cid) {
  localStorage.setItem("gg_conversation_id", cid);
  document.getElementById("cidPill").textContent = `conversation_id: ${cid}`;
}

// I add a message to the chat transcript, either from the user or from GroceryGuard
function addMsg(who, text) {
  const log = document.getElementById("log");
  const wrap = document.createElement("div");
  wrap.className = "msg";

  const title = document.createElement("div");
  title.className = `who ${who}`;
  title.textContent = who === "user" ? "You" : "GroceryGuard";
  wrap.appendChild(title);

  const body = document.createElement("div");
  body.innerHTML = text;
  wrap.appendChild(body);

  log.appendChild(wrap);
  wrap.scrollIntoView({ behavior: "smooth", block: "end" });

  return body; // return the body so we can stream text into it
}

// I show a loading indicator with bouncing dots while the API is processing the request
function addLoadingIndicator() {
  const body = addMsg("bot", '<span class="typing"><span></span><span></span><span></span></span>');
  return body.parentElement; // Return the .msg wrapper so I can remove it later
}

// I remove the loading indicator when the response arrives
function removeLoadingIndicator(msgWrapper) {
  if (msgWrapper && msgWrapper.parentElement) {
    msgWrapper.remove();
  }
}

// I update the status pill at the bottom to show what's happening
function setStatus(s) {
  document.getElementById("statusPill").textContent = s;
}

// I handle the main chat flow: send the user's message, show a loader, stream the response
async function send() {
  const btn = document.getElementById("sendBtn");
  const msgBox = document.getElementById("msg");
  const text = (msgBox.value || "").trim();
  if (!text) return;

  btn.disabled = true;
  setStatus("sending…");

  const cid = getCid();
  addMsg("user", text);
  msgBox.value = "";

  const loader = addLoadingIndicator();
  let botEl = null;

  try {
    // I send the user's message and conversation ID to the backend
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: cid, user_message: text })
    });

    if (!res.ok) {
      removeLoadingIndicator(loader);
      const errText = await res.text();
      addMsg("bot", `Server error (${res.status}): ${errText}`);
      setStatus("error");
      return;
    }

    // I remove the loader and prepare to stream the response
    removeLoadingIndicator(loader);

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let full = "";

    setStatus("streaming…");

    // I read the response stream chunk by chunk and update the message in real time
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      full += chunk;
      
      if (!botEl) {
        botEl = addMsg("bot", full);
      } else {
        botEl.textContent = full;
      }
    }

    setStatus("done");
  } catch (e) {
    removeLoadingIndicator(loader);
    addMsg("bot", `Network error: ${String(e)}`);
    setStatus("error");
  } finally {
    btn.disabled = false;
  }
}

// When the user clicks send, I call the send() function
document.getElementById("sendBtn").addEventListener("click", send);

// When the user clicks the "new conversation" button, I generate a fresh conversation ID
document.getElementById("newCidBtn").addEventListener("click", () => {
  setCid(newConversationId());
});

// When the user presses Ctrl+Enter or Cmd+Enter in the message box, I send the message
document.getElementById("msg").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
});

// I initialize the app by loading the conversation ID and setting the status to idle
setCid(getCid());
setStatus("idle");