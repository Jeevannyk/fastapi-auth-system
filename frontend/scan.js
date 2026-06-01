// Reads QR params from the URL, validates the challenge, then shows approve/deny UI.
// Device authentication rides on the HttpOnly "device_token" cookie set at
// enrollment — JS never sees the token. State-changing calls carry the CSRF
// token from the readable "csrf_token" cookie.

import { getCookie, withCsrf } from "/static/util.js";

const states = {
    loading:  document.getElementById("stateLoading"),
    approve:  document.getElementById("stateApprove"),
    success:  document.getElementById("stateSuccess"),
    denied:   document.getElementById("stateDenied"),
    noDevice: document.getElementById("stateNoDevice"),
    error:    document.getElementById("stateError"),
};

function show(name) {
    Object.values(states).forEach(el => el.classList.remove("active"));
    states[name].classList.add("active");
}

function setError(msg) {
    document.getElementById("errorMsg").textContent = msg;
    show("error");
}

// ── Parse QR params ──────────────────────────────────────────────────────────

const sp = new URLSearchParams(window.location.search);
const sessionId = sp.get("s");
const timestamp = parseInt(sp.get("t") || "0", 10);
const sig       = sp.get("sig");

if (!sessionId || !timestamp || !sig) {
    setError("Missing or malformed QR parameters. Please scan the QR code again.");
} else {
    init();
}

async function init() {
    // No readable device token anymore — detect enrollment via the flag cookie.
    if (!getCookie("device_enrolled")) { show("noDevice"); return; }

    // 1. Scan — identify user and mark session as scanned (device cookie auth)
    const scanRes = await fetch(`/api/qr/sessions/${sessionId}/scan`, {
        method: "POST",
        credentials: "include",
        headers: withCsrf("POST", { "Content-Type": "application/json" }),
        body: JSON.stringify({ timestamp, sig }),
    });

    if (!scanRes.ok) {
        if (scanRes.status === 401) { show("noDevice"); return; }
        const err = await scanRes.json().catch(() => ({}));
        setError(err.detail || "QR code is invalid or has expired. Please ask for a new one.");
        return;
    }

    // 2. Identify who this device belongs to
    const meRes = await fetch("/api/devices/me", { credentials: "include" });

    if (!meRes.ok) { setError("Could not identify device user."); return; }
    const user = await meRes.json();

    // 3. Show approve/deny UI
    const initials = user.full_name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
    document.getElementById("avatar").textContent = initials;
    document.getElementById("userName").textContent = user.full_name;
    document.getElementById("userEmail").textContent = user.email;
    show("approve");

    document.getElementById("btnApprove").addEventListener("click", approve);
    document.getElementById("btnDeny").addEventListener("click", deny);
}

async function approve() {
    document.getElementById("btnApprove").disabled = true;
    document.getElementById("btnDeny").disabled = true;

    const res = await fetch(`/api/qr/sessions/${sessionId}/approve`, {
        method: "POST",
        credentials: "include",
        headers: withCsrf("POST"),
    });

    if (res.ok) {
        show("success");
    } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Approval failed. Please try again.");
    }
}

async function deny() {
    await fetch(`/api/qr/sessions/${sessionId}/deny`, {
        method: "POST",
        credentials: "include",
        headers: withCsrf("POST"),
    });
    show("denied");
}
