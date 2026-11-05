"""One local page with two tabs: the DON Mishap Classification Assistant (assets/voice-rmi.html, served as it is) and
this app's dashboard. The dashboard tab also records in the browser: the recording is sent to the local server and
goes through the same steps as a voice memo. Served at / only when the assistant file is in assets/."""

import json

TITLE = "DON Mishap Reporting Assistant"
TABS = ("assistant", "dashboard")

PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice Form Filler</title>
<style>
:root{font-family:Segoe UI,-apple-system,Arial,sans-serif;color:#172b42;background:#f0f4f8}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;flex-direction:column}
header{background:#102e4c;color:white;padding:13px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap;border-bottom:3px solid #1f75bb}
.brand{font-size:1.1rem;font-weight:700;letter-spacing:.2px}nav{display:flex;gap:8px}
nav button{cursor:pointer;border:1px solid #89a8c6;border-radius:7px;background:transparent;color:white;font:inherit;padding:9px 15px;font-weight:600}
nav button[aria-selected="true"]{background:#fff;color:#10395c;border-color:white}
nav button:focus-visible{outline:3px solid #f1b44b;outline-offset:2px}
main{flex:1;display:flex;min-height:0}section{flex:1;min-width:0}section[hidden]{display:none}
.recorder{background:#e9f3fb;border-bottom:1px solid #b7cde0;padding:10px 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;color:#173650}
.recorder button{background:#145c94;color:white;border:0;border-radius:6px;padding:9px 13px;cursor:pointer;font-weight:600}
.recorder button:disabled{opacity:.5;cursor:not-allowed}
.recorder select{border:1px solid #9cb3c5;border-radius:6px;padding:9px;background:#fff;max-width:250px;font:inherit}
.recorder .status{flex:1;min-width:180px;font-size:.86rem}
iframe{border:0;width:100%;height:calc(100vh - 71px);display:block;background:#fff}
#dashboardFrame{height:calc(100vh - 137px)}
@media(max-width:520px){header{padding:10px;gap:10px}.brand{width:100%}iframe{height:calc(100vh - 112px)}}
</style></head><body>
<header><div class="brand">__TITLE__</div><nav aria-label="Application sections" role="tablist">
<button id="tab-assistant" role="tab" aria-controls="panel-assistant" aria-selected="true" tabindex="0">Voice RMI Assistant</button>
<button id="tab-dashboard" role="tab" aria-controls="panel-dashboard" aria-selected="false" tabindex="-1">Reporting Dashboard</button>
</nav></header><main>
<section id="panel-assistant" role="tabpanel" aria-labelledby="tab-assistant"><iframe title="Voice RMI Assistant" src="/assistant" allow="microphone"></iframe></section>
<section id="panel-dashboard" role="tabpanel" aria-labelledby="tab-dashboard" hidden>
<div class="recorder" role="group" aria-label="Record an incident in the browser">
<strong>Browser voice recording</strong>
<label for="recForm">Report form:</label><select id="recForm"><option value="any">Any form that fits</option></select>
<button id="recStart" type="button">🎙 Start recording</button>
<button id="recStop" type="button" disabled>■ Stop &amp; process</button>
<span id="recStatus" class="status" role="status" aria-live="polite">Records with this browser's microphone; allow it when asked. Or use the Record button in the dashboard below.</span>
</div><iframe id="dashboardFrame" title="Reporting Dashboard" src="/dashboard" loading="lazy"></iframe></section>
</main><script>
const TOKEN = __TOKEN__;
const FORMS = __FORMS__;
const names = ["assistant", "dashboard"];
function selectTab(name, updateHash = true) {
  if (!names.includes(name)) name = "assistant";
  for (const n of names) {
    const active = n === name, btn = document.getElementById("tab-" + n);
    btn.setAttribute("aria-selected", String(active)); btn.tabIndex = active ? 0 : -1;
    document.getElementById("panel-" + n).hidden = !active;
  }
  if (updateHash) history.replaceState(null, "", "#" + name);
}
for (const n of names) document.getElementById("tab-" + n).addEventListener("click", () => selectTab(n));
window.addEventListener("hashchange", () => selectTab(location.hash.slice(1), false));
selectTab(location.hash.slice(1) || "assistant", false);

// Record with the browser's microphone, send the file to the local server, then run the same steps as a voice memo.
const recForm = document.getElementById("recForm");
for (const [id, title] of FORMS) { const o = document.createElement("option"); o.value = id; o.textContent = title; recForm.appendChild(o); }
const start = document.getElementById("recStart"), stop = document.getElementById("recStop"), status = document.getElementById("recStatus");
let recorder = null, stream = null, chunks = [];
const say = s => { status.textContent = s; };
function reset() { start.disabled = false; stop.disabled = true; recForm.disabled = false; if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; } }
async function send(blob, ext) {
  say("Sending the recording to the local server…");
  let r = await fetch("/upload", {method: "POST", headers: {"X-VFF-Token": TOKEN, "X-VFF-Name": "browser-recording." + ext, "Content-Type": "application/octet-stream"}, body: blob});
  let j = await r.json(); if (!j.ok) throw Error(j.message || "the upload failed");
  r = await fetch("/run/memo", {method: "POST", headers: {"X-VFF-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify({choice: recForm.value, file: j.file})});
  j = await r.json(); if (!j.ok) throw Error(j.message || "the report didn't start");
  say("Filling the report — the dashboard below follows along and shows the form when it's done.");
}
start.addEventListener("click", async () => {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { say("This browser can't record. Use a recent Edge or Chrome, or the Record button in the dashboard below."); return; }
  start.disabled = true; recForm.disabled = true;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find(t => MediaRecorder.isTypeSupported(t));
    recorder = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
    chunks = [];
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    recorder.onerror = e => { say("Recording failed: " + (e.error?.message || "unknown error")); reset(); };
    recorder.onstop = async () => {
      const typ = recorder.mimeType || "audio/webm", ext = typ.includes("mp4") ? "m4a" : typ.includes("ogg") ? "ogg" : "webm";
      const blob = new Blob(chunks, {type: typ});
      if (!blob.size) { say("No sound was captured. Check the microphone permission."); reset(); return; }
      try { await send(blob, ext); } catch (e) { say("Couldn't process the recording: " + e.message); } finally { reset(); }
    };
    recorder.start(); stop.disabled = false;
    say("Recording. Tell what happened, then click Stop & process.");
  } catch (e) { say("Microphone unavailable: " + e.message + ". Check the browser's site permissions and the computer's microphone settings."); reset(); }
});
stop.addEventListener("click", () => { if (recorder?.state === "recording") { stop.disabled = true; say("Finishing the recording…"); recorder.stop(); } });
</script></body></html>'''


def combined_html(token: str, forms: list[tuple[str, str]]) -> str:
    """The page with the token and the form choices filled in (as JSON, so no text lands in the markup unescaped)."""
    forms_js = json.dumps(forms, ensure_ascii=False).replace("<", "\\u003c")
    return PAGE.replace("__TITLE__", TITLE).replace("__TOKEN__", json.dumps(token)).replace("__FORMS__", forms_js)
