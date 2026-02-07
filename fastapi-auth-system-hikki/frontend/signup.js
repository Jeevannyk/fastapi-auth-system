document.getElementById("signupBtn").addEventListener("click", async () => {
    console.log("Signup button clicked"); // 🔍 DEBUG

    const fullName = document.getElementById("fullName").value;
    const email = document.getElementById("email").value;
    const accessKey = document.getElementById("accessKey").value;
    const verifyKey = document.getElementById("verifyKey").value;

    console.log({ fullName, email, accessKey, verifyKey }); // 🔍 DEBUG

    const res = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            full_name: fullName,
            email: email,
            access_key: accessKey,
            verify_key: verifyKey
        })
    });

    const data = await res.json();
    console.log("Signup response:", data); // 🔍 DEBUG

    if (!res.ok) {
        // Handle validation/detail objects gracefully
        const message = typeof data?.detail === "string"
            ? data.detail
            : Array.isArray(data?.detail)
                ? data.detail.map(d => d?.msg || d).join(" | ")
                : "Signup failed";
        alert(message);
        return;
    }

    // ✅ AFTER SIGNUP → LOGIN → FINGERPRINT → QR
    alert(data.message || "User identity securely registered.");
    window.location.href = "/login";
});
