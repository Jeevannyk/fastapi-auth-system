const DEVICE_TOKEN_KEY = "cipher_device_token";

const form     = document.getElementById("form");
const submit   = document.getElementById("submit");
const errorBox = document.getElementById("error");

// If already enrolled, skip to login
if (localStorage.getItem(DEVICE_TOKEN_KEY)) {
    window.location.href = "/login";
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");
    submit.disabled = true;

    const full_name   = document.getElementById("fullName").value.trim();
    const email       = document.getElementById("email").value.trim();
    const device_name = document.getElementById("deviceName").value.trim() || "My Device";

    try {
        const res = await fetch("/api/auth/register", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name, email, device_name }),
        });

        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.detail || "Registration failed");
        }

        const data = await res.json();

        // Persist the device token — this is the only time it is ever sent
        localStorage.setItem(DEVICE_TOKEN_KEY, data.device_token);

        // Show success state
        document.querySelector(".heading h1").textContent = "Device enrolled";
        document.querySelector(".heading p").textContent = "You're ready to scan QR codes";
        document.getElementById("formCard").innerHTML = `
            <p style="font-size:0.875rem;color:rgba(240,232,220,0.65);line-height:1.8;text-align:center;padding:0.5rem 0 1.25rem">
                Your device token has been saved to this browser.<br>
                Whenever you see a Cipher QR code, scan it with this device and tap <strong style="color:#f0e8dc;font-weight:400">Approve</strong>.
            </p>
            <a href="/login" style="
                display:block;text-align:center;
                background:linear-gradient(110deg,#9a7b2c 0%,#c9a44a 35%,#e2c472 55%,#c9a44a 75%,#9a7b2c 100%);
                background-size:200% 100%;color:#1c1408;border:none;border-radius:10px;
                padding:0.78rem 1rem;font-size:0.75rem;font-weight:500;letter-spacing:0.09em;
                text-transform:uppercase;text-decoration:none;
                box-shadow:0 2px 20px rgba(196,163,90,0.22),inset 0 1px 0 rgba(255,255,255,0.22)">
                Go to sign in
            </a>`;

    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.classList.remove("hidden");
        submit.disabled = false;
    }
});
