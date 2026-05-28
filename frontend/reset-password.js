import { api, showError } from "/static/util.js";

const form = document.getElementById("form");
const submit = document.getElementById("submit");
const errorBox = document.getElementById("error");

const token = new URLSearchParams(window.location.search).get("token");

if (!token) {
    document.querySelector(".heading h1").textContent = "Link invalid";
    document.querySelector(".heading p").textContent = "No reset token in this URL";
    document.getElementById("card").innerHTML = `
        <p style="text-align:center;color:rgba(240,232,220,0.65);font-size:0.875rem;line-height:1.8">
            Request a new link from the <a href="/forgot-password" style="color:#e0c07a;text-decoration:none">forgot password</a> page.
        </p>`;
}

form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");

    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirm").value;

    if (password !== confirm) {
        showError(errorBox, "Passwords do not match");
        return;
    }

    submit.disabled = true;
    try {
        await api("/api/auth/reset-password", {
            method: "POST",
            body: JSON.stringify({ token, password }),
        });
        document.querySelector(".heading h1").textContent = "Password updated";
        document.querySelector(".heading p").textContent = "You can now sign in";
        document.getElementById("card").innerHTML = `
            <p style="text-align:center;color:rgba(240,232,220,0.65);font-size:0.875rem;line-height:1.8">
                Your password has been reset.<br>
                <a href="/login" style="color:#e0c07a;text-decoration:none">Sign in →</a>
            </p>`;
    } catch (err) {
        showError(errorBox, err.message);
        submit.disabled = false;
    }
});
