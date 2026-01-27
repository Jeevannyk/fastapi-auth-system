function openFingerprint(email) {
    const modal = document.getElementById("fingerprintModal");
    modal.classList.remove("hidden");

    document.getElementById("fingerprintBtn").onclick = async () => {
        try {
            await navigator.credentials.get({
                publicKey: {
                    challenge: new Uint8Array(32),
                    userVerification: "required"
                }
            });

            const res = await fetch("http://127.0.0.1:8000/fingerprint", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email })
            });

            const data = await res.json();

            modal.classList.add("hidden");
            showQR(data.session_id);

        } catch {
            alert("Fingerprint verification failed");
        }
    };
}

function showQR(sessionId) {
    // Create modal if it doesn't exist
    let qrModal = document.getElementById("qrModal");

    if (!qrModal) {
        qrModal = document.createElement("div");
        qrModal.id = "qrModal";
        qrModal.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm";
        qrModal.innerHTML = `
      <div class="bg-[#101622]/95 border border-[#232f48] rounded-xl p-8 max-w-md w-full mx-4 text-center shadow-[0_0_40px_rgba(19,91,236,0.2)]">
        <div class="inline-flex items-center justify-center size-16 rounded-full bg-primary/10 mb-4 ring-1 ring-primary/40">
          <span class="material-symbols-outlined text-primary text-4xl">qr_code_2</span>
        </div>
        <h2 class="text-2xl font-bold text-white mb-2">Scan QR Code</h2>
        <p class="text-slate-400 text-sm mb-6">Scan this code with your device to complete authentication</p>
        <img id="qrImage" class="mx-auto mb-4 rounded-lg border-2 border-primary/30" alt="QR Code" />
        <button onclick="document.getElementById('qrModal').remove()" class="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-bold rounded-lg text-white bg-[#232f48] hover:bg-[#2c3b5a] focus:outline-none focus:ring-2 focus:ring-primary transition-all">
          Close
        </button>
      </div>
    `;
        document.body.appendChild(qrModal);
    }

    const qrImage = document.getElementById("qrImage");
    qrImage.src = `http://127.0.0.1:8000/qr-image/${sessionId}`;
}
