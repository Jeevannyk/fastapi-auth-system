import { getCookie, withCsrf } from "/static/util.js";

async function api(path, options = {}) {
    const method = options.method || "GET";
    const res = await fetch(path, {
        credentials: "include",
        ...options,
        headers: withCsrf(method, options.headers || {}),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    return res.status === 204 ? null : res.json();
}

// ── Load user ────────────────────────────────────────────────────────────────
let me;
try {
    me = await api("/api/auth/me");
} catch {
    window.location.href = "/login";
}

const initials = me.full_name.trim().split(/\s+/).map(w => w[0]).join("").toUpperCase().slice(0, 2);
document.getElementById("avatarInitials").textContent = initials;
document.getElementById("profileName").textContent    = me.full_name;
document.getElementById("profileEmail").textContent   = me.email;
document.getElementById("profileDate").textContent    =
    new Date(me.created_at).toLocaleDateString("en-US", { year: "numeric", month: "long" });

// ── Device icon SVG (phone) ───────────────────────────────────────────────────
const PHONE_SVG = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
    <circle cx="12" cy="17" r="1"/>
</svg>`;

// ── Load devices ─────────────────────────────────────────────────────────────
const devicesList = document.getElementById("devicesList");

function renderSkeleton() {
    devicesList.innerHTML = [1, 2].map(() => `
        <div class="device-row" style="gap:1rem;padding:1rem 0;border-bottom:1px solid rgba(255,255,255,0.065)">
            <div class="skeleton" style="width:36px;height:36px;border-radius:9px;flex-shrink:0"></div>
            <div style="flex:1;display:flex;flex-direction:column;gap:0.45rem">
                <div class="skeleton" style="height:13px;width:38%"></div>
                <div class="skeleton" style="height:10px;width:24%;opacity:0.6"></div>
            </div>
        </div>`).join("");
}

function formatLastUsed(iso) {
    if (!iso) return "Never";
    const d    = new Date(iso);
    const now  = new Date();
    const diff = now - d;
    const mins = Math.floor(diff / 60000);
    if (mins < 2)   return "Just now";
    if (mins < 60)  return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)   return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days === 1) return "Yesterday";
    if (days < 7)   return `${days}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

async function loadDevices() {
    renderSkeleton();
    try {
        const devices = await api("/api/devices");
        if (!devices.length) {
            devicesList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        ${PHONE_SVG}
                    </div>
                    <p>No devices registered yet.</p>
                    <p style="font-size:0.75rem;color:rgba(240,232,220,0.28)">Add a device to enable QR authentication.</p>
                </div>`;
            return;
        }
        devicesList.innerHTML = devices.map((d, i) => `
            <div class="device-row" id="dev-${d.id}" style="animation:fadeUp .5s cubic-bezier(.16,1,.3,1) ${i * 0.06}s both">
                <div class="device-icon">${PHONE_SVG}</div>
                <div class="device-info">
                    <p class="device-name">${escHtml(d.name)}</p>
                    <p class="device-last">${formatLastUsed(d.last_used_at)}</p>
                </div>
                <button class="device-revoke" onclick="revokeDevice(${d.id})">Revoke</button>
            </div>`).join("");

    } catch {
        devicesList.innerHTML = `
            <div class="empty-state">
                <p style="color:#f4a8a0">Could not load devices. Try reloading.</p>
            </div>`;
    }
}

window.revokeDevice = async (id) => {
    if (!confirm("Revoke this device? It will no longer be able to approve sign-ins.")) return;
    try {
        await api(`/api/devices/${id}`, { method: "DELETE" });
        const row = document.getElementById(`dev-${id}`);
        if (row) {
            row.style.transition = "opacity .3s, transform .3s";
            row.style.opacity    = "0";
            row.style.transform  = "translateX(8px)";
            setTimeout(loadDevices, 320);
        } else {
            loadDevices();
        }
    } catch (err) {
        alert(err.message);
    }
};

loadDevices();

// ── Add device ────────────────────────────────────────────────────────────────
document.getElementById("btnAddDevice").addEventListener("click", async () => {
    if (!getCookie("device_enrolled")) {
        alert("This browser is not enrolled. Register at /register first.");
        return;
    }
    const name = prompt("Name for the new device:", "New Device");
    if (!name) return;
    try {
        // Authenticated by the HttpOnly device_token cookie; the returned raw
        // token is for transferring to the new device, not stored here.
        const d = await api(`/api/devices/enroll?device_name=${encodeURIComponent(name)}`, {
            method: "POST",
        });
        prompt("New device token (copy it onto the new device):", d.device_token);
        loadDevices();
    } catch (err) {
        alert("Failed: " + err.message);
    }
});

// ── Logout ────────────────────────────────────────────────────────────────────
document.getElementById("logout").addEventListener("click", () => {
    document.cookie = "access_token=; Max-Age=0; path=/";
    window.location.href = "/login";
});

function escHtml(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
