// ── Constants ────────────────────────────────────────────────────────────────
const QR_ROTATE_SECS   = 30;   // refresh QR image every 30 s
const SESSION_EXPIRE   = 90;   // show expired overlay after 90 s

// ── Cookie / CSRF helpers ──────────────────────────────────────────────────────
function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
}
// Attach the CSRF token (double-submit cookie) to state-changing requests.
function csrfHeaders(extra = {}) {
    const token = getCookie("csrf_token");
    return token ? { ...extra, "X-CSRF-Token": token } : { ...extra };
}

// ── Element refs ─────────────────────────────────────────────────────────────
const tabSignup   = document.getElementById("tabSignup");
const tabSignin   = document.getElementById("tabSignin");
const formSignup  = document.getElementById("formSignup");
const formSignin  = document.getElementById("formSignin");

const signupForm  = document.getElementById("signupForm");
const suName      = document.getElementById("su-name");
const suEmail     = document.getElementById("su-email");
const suDevice    = document.getElementById("su-device");
const suSubmit    = document.getElementById("su-submit");
const suError     = document.getElementById("su-error");

const signinForm  = document.getElementById("signinForm");
const siEmail     = document.getElementById("si-email");
const siMsg       = document.getElementById("si-msg");
const siSubmit    = document.getElementById("si-submit");

const qrLoading   = document.getElementById("qrLoading");
const qrActive    = document.getElementById("qrActive");
const qrExpired   = document.getElementById("qrExpired");
const qrSuccess   = document.getElementById("qrSuccess");
const qrImg       = document.getElementById("qrImg");
const timerBar    = document.getElementById("timerBar");
const btnRefresh  = document.getElementById("btnRefresh");

const statusBar   = document.getElementById("statusBar");
const statusDot   = document.getElementById("statusDot");
const statusText  = document.getElementById("statusText");

// ── State ────────────────────────────────────────────────────────────────────
let sessionId       = null;
let pollTimer       = null;
let rotateTimer     = null;
let expireTimer     = null;
let rotateCountdown = QR_ROTATE_SECS;
let totalElapsed    = 0;

// Read OAuth params forwarded from /oauth/authorize
const params = new URLSearchParams(window.location.search);
const oauthPayload = {
    client_id:    params.get("client_id")    || undefined,
    redirect_uri: params.get("redirect_uri") || undefined,
    scope:        params.get("scope")        || "openid profile email",
};

// ── Tab switching ─────────────────────────────────────────────────────────────
window.setMode = function setMode(mode) {
    const isSignup = mode === "signup";

    tabSignup.className = "tab-btn" + (isSignup ? " tab-btn--active" : "");
    tabSignin.className = "tab-btn" + (isSignup ? "" : " tab-btn--active");

    formSignup.classList.toggle("hidden", !isSignup);
    formSignin.classList.toggle("hidden",  isSignup);

    hideSuError();
    hideSiMsg();
};

// ── QR state machine ─────────────────────────────────────────────────────────
function setQRState(state) {
    qrLoading.classList.add("hidden");
    qrActive.classList.add("hidden");
    qrExpired.classList.add("hidden");
    qrSuccess.classList.add("hidden");

    switch (state) {
        case "loading":
            qrLoading.classList.remove("hidden");
            setStatus("gold", "Initializing session…");
            break;

        case "active":
            qrActive.classList.remove("hidden");
            setStatus("gold", "Waiting for your phone to scan…");
            break;

        case "scanned":
            qrActive.classList.remove("hidden");
            setStatus("blue", "Phone detected — tap Approve on your device");
            break;

        case "expired":
            clearTimers();
            qrExpired.classList.remove("hidden");
            setStatus("warn", "Session expired — generate a new code to continue");
            break;

        case "success":
            clearTimers();
            qrSuccess.classList.remove("hidden");
            setStatus("ok", "Identity verified — signing you in…");
            break;
    }
}

function setStatus(variant, text) {
    const styles = {
        gold: {
            bg:     "rgba(196,163,90,0.07)",
            border: "rgba(196,163,90,0.14)",
            color:  "rgba(240,232,220,0.55)",
            dot:    "rgba(196,163,90,0.70)",
        },
        blue: {
            bg:     "rgba(80,100,200,0.09)",
            border: "rgba(80,100,200,0.20)",
            color:  "rgba(200,210,255,0.65)",
            dot:    "rgba(120,140,255,0.80)",
        },
        ok: {
            bg:     "rgba(109,191,138,0.09)",
            border: "rgba(109,191,138,0.22)",
            color:  "rgba(109,191,138,0.80)",
            dot:    "#6dbf8a",
        },
        warn: {
            bg:     "rgba(200,80,72,0.09)",
            border: "rgba(200,80,72,0.22)",
            color:  "#f4a8a0",
            dot:    "#f4a8a0",
        },
    };
    const s = styles[variant] || styles.gold;
    statusBar.style.background   = s.bg;
    statusBar.style.border       = `1px solid ${s.border}`;
    statusBar.style.color        = s.color;
    statusDot.style.background   = s.dot;
    statusText.textContent       = text;
}

// ── Session creation ─────────────────────────────────────────────────────────
async function createSession() {
    clearTimers();
    sessionId    = null;
    totalElapsed = 0;

    setQRState("loading");

    try {
        const body = Object.fromEntries(
            Object.entries(oauthPayload).filter(([, v]) => v !== undefined)
        );
        const res = await fetch("/api/qr/sessions", {
            method: "POST",
            credentials: "include",
            headers: csrfHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Server error");

        const data = await res.json();
        sessionId = data.session_id;

        qrImg.src = data.qr_data_url;
        setQRState("active");
        startCountdown(data.qr_ttl || QR_ROTATE_SECS);
        startPolling();

    } catch (err) {
        setStatus("warn", "Could not create session — " + err.message);
    }
}

// ── Countdown & rotation ─────────────────────────────────────────────────────
function startCountdown(ttl) {
    rotateCountdown = ttl;
    timerBar.style.width = "100%";

    const tick = () => {
        rotateCountdown--;
        totalElapsed++;

        // Visual timer bar (counts down to 0 then resets)
        timerBar.style.width = `${Math.max(0, (rotateCountdown / ttl) * 100)}%`;

        // Hard session expiry (90 s total)
        if (totalElapsed >= SESSION_EXPIRE) {
            setQRState("expired");
            return;
        }

        if (rotateCountdown <= 0) {
            refreshQR();
        } else {
            rotateTimer = setTimeout(tick, 1000);
        }
    };

    rotateTimer = setTimeout(tick, 1000);
}

async function refreshQR() {
    if (!sessionId) return;
    try {
        const res = await fetch(`/api/qr/sessions/${sessionId}/qr`, { credentials: "include" });
        if (!res.ok) { setQRState("expired"); return; }
        const data = await res.json();
        qrImg.src = data.qr_data_url;
        startCountdown(data.ttl || QR_ROTATE_SECS);
    } catch {
        setQRState("expired");
    }
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling() {
    pollTimer = setInterval(poll, 2000);
}

async function poll() {
    if (!sessionId) return;
    try {
        const res = await fetch(`/api/qr/sessions/${sessionId}/status`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();

        switch (data.status) {
            case "pending":
                break;

            case "scanned":
                setQRState("scanned");
                break;

            case "approved": {
                clearInterval(pollTimer);
                pollTimer = null;
                setQRState("success");

                if (data.redirect_url) {
                    setTimeout(() => { window.location.href = data.redirect_url; }, 600);
                    return;
                }

                // Direct login — exchange approved session for a JWT cookie
                try {
                    const tok = await fetch(`/api/qr/sessions/${sessionId}/token`, {
                        method: "POST",
                        credentials: "include",
                        headers: csrfHeaders(),
                    });
                    if (tok.ok) {
                        setTimeout(() => { window.location.href = "/home"; }, 800);
                    } else {
                        setStatus("warn", "Token exchange failed — please try again");
                    }
                } catch {
                    setStatus("warn", "Network error during token exchange");
                }
                break;
            }

            case "expired":
            case "consumed":
                if (data.status === "expired") setQRState("expired");
                break;
        }
    } catch {
        // transient network error — keep polling
    }
}

// ── Helper: clear all timers ──────────────────────────────────────────────────
function clearTimers() {
    clearInterval(pollTimer);
    clearTimeout(rotateTimer);
    pollTimer    = null;
    rotateTimer  = null;
}

// ── Signup form ───────────────────────────────────────────────────────────────
function showSuError(msg) {
    suError.textContent = msg;
    suError.classList.remove("hidden");
}
function hideSuError() {
    suError.classList.add("hidden");
}

signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideSuError();
    suSubmit.disabled = true;
    suSubmit.textContent = "Enrolling…";

    const full_name   = suName.value.trim();
    const email       = suEmail.value.trim();
    const device_name = suDevice.value.trim() || "My Device";

    try {
        const res = await fetch("/api/auth/register", {
            method: "POST",
            credentials: "include",
            headers: csrfHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ full_name, email, device_name }),
        });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.detail || "Registration failed");
        }
        await res.json();
        // Device token is now an HttpOnly cookie set by the server.
        window.location.href = "/home";

    } catch (err) {
        showSuError(err.message);
        suSubmit.disabled = false;
        suSubmit.textContent = "Enroll & Activate";
    }
});

// ── Signin form ───────────────────────────────────────────────────────────────
function showSiMsg(text, variant) {
    const variants = {
        ok:   { bg: "rgba(109,191,138,0.09)", border: "rgba(109,191,138,0.22)", color: "rgba(109,191,138,0.90)" },
        info: { bg: "rgba(196,163,90,0.07)",  border: "rgba(196,163,90,0.18)",  color: "rgba(240,232,220,0.65)" },
        err:  { bg: "rgba(200,80,72,0.09)",   border: "rgba(200,80,72,0.22)",   color: "#f4a8a0" },
    };
    const s = variants[variant] || variants.info;
    siMsg.style.background = s.bg;
    siMsg.style.border     = `1px solid ${s.border}`;
    siMsg.style.color      = s.color;
    siMsg.textContent      = text;
    siMsg.classList.remove("hidden");
}
function hideSiMsg() {
    siMsg.classList.add("hidden");
}

signinForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideSiMsg();
    siSubmit.disabled = true;
    siSubmit.textContent = "Checking…";

    const email = siEmail.value.trim();

    try {
        const res = await fetch("/api/auth/lookup", {
            method: "POST",
            credentials: "include",
            headers: csrfHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ email }),
        });

        if (res.status === 404) {
            showSiMsg("No account found for that email — create one using the tab above.", "err");
            siSubmit.disabled = false;
            siSubmit.textContent = "Continue";
            return;
        }

        if (!res.ok) throw new Error("Lookup failed");

        // Account found — check if this browser is an enrolled device
        const enrolled = getCookie("device_enrolled");
        if (enrolled) {
            showSiMsg(
                "Account found. Use your registered phone to scan the QR code on the right — then tap Approve.",
                "ok"
            );
        } else {
            showSiMsg(
                "Account found. Open your QR code scanner on your mobile and scan the code on the right to sign in.",
                "info"
            );
        }

    } catch {
        showSiMsg("Could not reach the server — please try again.", "err");
    } finally {
        siSubmit.disabled = false;
        siSubmit.textContent = "Continue";
    }
});

// ── Refresh button ────────────────────────────────────────────────────────────
btnRefresh.addEventListener("click", createSession);

// ── Boot ──────────────────────────────────────────────────────────────────────
createSession();
