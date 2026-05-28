import { api, showError } from "/static/util.js";

const params = new URLSearchParams(window.location.search);
const mode = params.get("mode") === "verify" ? "verify" : "setup";

if (mode === "setup") {
    document.getElementById("setupView").classList.remove("hidden");
    bootSetup();
} else {
    document.getElementById("verifyView").classList.remove("hidden");
    bootVerify();
}

async function bootSetup() {
    const errorBox = document.getElementById("setupError");
    const submit = document.getElementById("setupSubmit");
    const codeInput = document.getElementById("setupCode");

    try {
        const data = await api("/api/2fa/setup", { method: "POST" });
        document.getElementById("secretText").textContent = data.secret;
        document.getElementById("qrCanvas").src = data.qr_code_data_url;
    } catch (err) {
        showError(errorBox, err.message);
        submit.disabled = true;
        return;
    }

    submit.addEventListener("click", async () => {
        errorBox.classList.add("hidden");
        submit.disabled = true;
        try {
            await api("/api/2fa/enable", {
                method: "POST",
                body: JSON.stringify({ code: codeInput.value }),
            });
            window.location.href = "/home";
        } catch (err) {
            showError(errorBox, err.message);
            submit.disabled = false;
        }
    });
}

function bootVerify() {
    const form = document.getElementById("verifyForm");
    const submit = document.getElementById("verifySubmit");
    const errorBox = document.getElementById("verifyError");
    const codeInput = document.getElementById("verifyCode");

    const userId = Number(sessionStorage.getItem("pending_user_id") || 0);
    if (!userId) {
        window.location.href = "/login";
        return;
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        errorBox.classList.add("hidden");
        submit.disabled = true;
        try {
            await api("/api/auth/login/2fa", {
                method: "POST",
                body: JSON.stringify({ user_id: userId, code: codeInput.value }),
            });
            sessionStorage.removeItem("pending_user_id");
            window.location.href = "/home";
        } catch (err) {
            showError(errorBox, err.message);
            submit.disabled = false;
        }
    });
}
