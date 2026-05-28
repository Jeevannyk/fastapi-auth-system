const heading = document.getElementById("heading");
const subheading = document.getElementById("subheading");
const icon = document.getElementById("icon");
const msg = document.getElementById("msg");
const action = document.getElementById("action");
const footer = document.getElementById("footer");

const token = new URLSearchParams(window.location.search).get("token");

if (!token) {
    setError("No verification token found in the link.", "Get a new one");
    action.href = "/signup";
} else {
    fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, { credentials: "include" })
        .then(async (res) => {
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || "Verification failed");
            }
            setSuccess();
        })
        .catch((err) => setError(err.message));
}

function setSuccess() {
    heading.textContent = "Email verified";
    subheading.textContent = "Your account is now active";
    icon.textContent = "✓";
    icon.classList.remove("loading");
    icon.style.color = "#e0c07a";
    msg.textContent = "You can now sign in to your Cipher account.";
    action.classList.remove("hidden");
}

function setError(message, linkText = "Sign in") {
    heading.textContent = "Link expired";
    subheading.textContent = "This verification link is no longer valid";
    icon.textContent = "✕";
    icon.classList.remove("loading");
    icon.style.color = "#f4a8a0";
    msg.textContent = message;
    action.textContent = linkText;
    action.classList.remove("hidden");
    footer.classList.remove("hidden");
}
