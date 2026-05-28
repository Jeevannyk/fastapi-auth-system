import { api, showError } from "/static/util.js";

const form = document.getElementById("form");
const submit = document.getElementById("submit");
const errorBox = document.getElementById("error");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");
    submit.disabled = true;

    const email = document.getElementById("email").value.trim();

    try {
        await api("/api/auth/forgot-password", {
            method: "POST",
            body: JSON.stringify({ email }),
        });
        showSuccessState(email);
    } catch (err) {
        showError(errorBox, err.message);
        submit.disabled = false;
    }
});

function showSuccessState(email) {
    document.querySelector(".heading h1").textContent = "Check your inbox";
    document.querySelector(".heading p").textContent = `Sent to ${email}`;
    document.getElementById("form-card").innerHTML = `
        <p style="text-align:center;color:rgba(240,232,220,0.65);font-size:0.875rem;line-height:1.8;padding:0.25rem 0 1rem">
            If that address is registered you'll receive a reset link.<br>
            It expires in 1 hour.<br><br>
            <a href="/login" style="color:#e0c07a;text-decoration:none">Back to sign in</a>
        </p>
        <button id="dev-trigger" style="
            display:block;width:100%;
            background:rgba(255,255,255,0.04);
            border:1px dashed rgba(255,255,255,0.14);
            border-radius:10px;padding:0.6rem 1rem;
            font-size:0.75rem;font-family:'DM Sans',sans-serif;
            color:rgba(240,232,220,0.45);letter-spacing:0.05em;
            cursor:pointer;transition:border-color .2s,color .2s;
        " onmouseover="this.style.borderColor='rgba(196,163,90,0.4)';this.style.color='rgba(240,232,220,0.75)'"
           onmouseout="this.style.borderColor='rgba(255,255,255,0.14)';this.style.color='rgba(240,232,220,0.45)'">
            ⚙ Dev — get test link
        </button>`;

    document.getElementById("dev-trigger").addEventListener("click", async () => {
        try {
            const data = await api(`/api/auth/debug/reset-link?email=${encodeURIComponent(email)}`);
            showModal(data.message);
        } catch {
            showModal(null);
        }
    });
}

function showModal(url) {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
        position:fixed;inset:0;
        background:rgba(0,0,0,0.72);
        backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
        z-index:1000;display:flex;align-items:center;justify-content:center;padding:1.5rem`;

    overlay.innerHTML = url ? `
        <div style="
            background:#0d1229;
            border:1px solid rgba(255,255,255,0.12);
            border-top:1px solid rgba(255,255,255,0.20);
            border-radius:18px;padding:1.75rem;
            max-width:480px;width:100%;
            box-shadow:0 24px 64px rgba(0,0,0,0.72),inset 0 1px 0 rgba(255,255,255,0.06)">
            <p style="font-size:0.6875rem;font-weight:500;letter-spacing:0.10em;text-transform:uppercase;color:rgba(196,163,90,0.7);margin-bottom:0.75rem">
                Dev · Reset Link
            </p>
            <p style="font-size:0.75rem;color:rgba(240,232,220,0.45);margin-bottom:0.75rem;line-height:1.5">
                This link is only visible in dev mode (<code style="background:rgba(255,255,255,0.06);padding:0 4px;border-radius:4px">EMAIL_ENABLED=false</code>).
            </p>
            <a href="${url}" target="_blank" style="
                display:block;word-break:break-all;
                color:#e0c07a;font-size:0.8125rem;line-height:1.6;
                text-decoration:none;
                background:rgba(196,163,90,0.06);
                border:1px solid rgba(196,163,90,0.18);
                border-radius:10px;padding:0.75rem 0.875rem;
                transition:background .2s"
                onmouseover="this.style.background='rgba(196,163,90,0.10)'"
                onmouseout="this.style.background='rgba(196,163,90,0.06)'">${url}</a>
            <button id="modal-close" style="
                margin-top:1rem;width:100%;padding:0.65rem;
                background:rgba(255,255,255,0.05);
                border:1px solid rgba(255,255,255,0.09);
                border-radius:10px;
                color:rgba(240,232,220,0.55);
                font-family:'DM Sans',sans-serif;font-size:0.8125rem;
                cursor:pointer;transition:background .2s"
                onmouseover="this.style.background='rgba(255,255,255,0.09)'"
                onmouseout="this.style.background='rgba(255,255,255,0.05)'">Dismiss</button>
        </div>` : `
        <div style="
            background:#0d1229;border:1px solid rgba(200,80,72,0.22);
            border-radius:18px;padding:1.75rem;max-width:380px;width:100%;text-align:center">
            <p style="color:#f4a8a0;font-size:0.875rem;margin-bottom:1rem">
                Could not fetch link — make sure the email is registered.
            </p>
            <button id="modal-close" style="
                width:100%;padding:0.65rem;
                background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.09);
                border-radius:10px;color:rgba(240,232,220,0.55);
                font-family:'DM Sans',sans-serif;font-size:0.8125rem;cursor:pointer">Dismiss</button>
        </div>`;

    document.body.appendChild(overlay);
    overlay.querySelector("#modal-close").addEventListener("click", () => overlay.remove());
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
}
