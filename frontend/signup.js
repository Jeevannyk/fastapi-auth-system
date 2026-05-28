import { api, showError } from "/static/util.js";

const form = document.getElementById("signupForm");
const submit = document.getElementById("submit");
const errorBox = document.getElementById("error");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");

    const full_name = document.getElementById("fullName").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirm").value;

    if (password !== confirm) {
        showError(errorBox, "Passwords do not match");
        return;
    }

    submit.disabled = true;
    try {
        const data = await api("/api/auth/signup", {
            method: "POST",
            body: JSON.stringify({ full_name, email, password }),
        });
        if (data.email_verification_required) {
            document.querySelector(".heading h1").textContent = "Check your email";
            document.querySelector(".heading p").textContent = `Sent a link to ${email}`;
            document.querySelector(".card").innerHTML = `
                <p style="text-align:center;color:rgba(240,232,220,0.65);font-size:0.875rem;line-height:1.8;padding:0.25rem 0">
                    Click the verification link in your inbox to activate your account.<br>
                    It expires in 24 hours.<br><br>
                    Once verified, <a href="/login" style="color:#e0c07a;text-decoration:none">sign in here</a>.
                </p>`;
        } else {
            window.location.href = "/login";
        }
    } catch (err) {
        showError(errorBox, err.message);
        submit.disabled = false;
    }
});
