/**
 * CyberGuard WebAuthn/Passkey Module
 * Production-grade biometric authentication using W3C WebAuthn API
 * 
 * Supports:
 * - Windows Hello (fingerprint, face, PIN)
 * - Apple Touch ID / Face ID
 * - Android biometrics
 * - FIDO2 security keys
 * 
 * Security Notes:
 * - NO biometric data is stored on the server
 * - Uses public-key cryptography
 * - Private keys never leave the device
 */

const WebAuthnModule = (function() {
    const API_BASE = 'http://127.0.0.1:8000';

    // ==================== UTILITY FUNCTIONS ====================

    function base64urlToBuffer(base64url) {
        const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
        const padding = '='.repeat((4 - base64.length % 4) % 4);
        const binary = atob(base64 + padding);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    function bufferToBase64url(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    }

    // ==================== FEATURE DETECTION ====================

    /**
     * Check if WebAuthn is supported and platform authenticator is available
     */
    async function isSupported() {
        // Check basic WebAuthn support
        if (!window.PublicKeyCredential) {
            return {
                supported: false,
                platformAuthenticator: false,
                reason: 'WebAuthn API not supported by this browser'
            };
        }

        // Check if platform authenticator is available
        try {
            const platformAvailable = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
            
            // Check for conditional UI support (autofill)
            let conditionalUISupported = false;
            if (PublicKeyCredential.isConditionalMediationAvailable) {
                conditionalUISupported = await PublicKeyCredential.isConditionalMediationAvailable();
            }

            return {
                supported: true,
                platformAuthenticator: platformAvailable,
                conditionalUI: conditionalUISupported,
                reason: platformAvailable ? 
                    'Platform authenticator available (fingerprint/face)' : 
                    'Only external security keys supported'
            };
        } catch (error) {
            return {
                supported: true,
                platformAuthenticator: false,
                conditionalUI: false,
                reason: `Feature detection error: ${error.message}`
            };
        }
    }

    /**
     * Get device-specific authenticator name
     */
    function getAuthenticatorName() {
        const ua = navigator.userAgent.toLowerCase();
        
        if (ua.includes('windows')) {
            return 'Windows Hello';
        } else if (ua.includes('mac') || ua.includes('iphone') || ua.includes('ipad')) {
            return ua.includes('iphone') || ua.includes('ipad') ? 'Face ID / Touch ID' : 'Touch ID';
        } else if (ua.includes('android')) {
            return 'Android Biometrics';
        } else if (ua.includes('linux')) {
            return 'Fingerprint Scanner';
        }
        return 'Biometric Authentication';
    }

    // ==================== REGISTRATION ====================

    /**
     * Register a new WebAuthn credential (passkey)
     * @param {string} email - User's email address
     * @returns {Promise<Object>} - Registration result
     */
    async function register(email) {
        if (!email) {
            throw new Error('Email is required for registration');
        }

        // Get registration options from server
        const optionsResponse = await fetch(`${API_BASE}/webauthn/register/options`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (!optionsResponse.ok) {
            const error = await optionsResponse.json();
            throw new Error(error.detail || 'Failed to get registration options');
        }

        const { options } = await optionsResponse.json();

        // Convert server options to WebAuthn format
        const publicKeyCredentialCreationOptions = {
            challenge: base64urlToBuffer(options.challenge),
            rp: options.rp,
            user: {
                id: base64urlToBuffer(options.user.id),
                name: options.user.name,
                displayName: options.user.displayName
            },
            pubKeyCredParams: options.pubKeyCredParams,
            authenticatorSelection: options.authenticatorSelection,
            timeout: options.timeout,
            attestation: options.attestation,
            excludeCredentials: (options.excludeCredentials || []).map(cred => ({
                type: cred.type,
                id: base64urlToBuffer(cred.id),
                transports: cred.transports
            }))
        };

        // Call WebAuthn API - triggers biometric prompt
        let credential;
        try {
            credential = await navigator.credentials.create({
                publicKey: publicKeyCredentialCreationOptions
            });
        } catch (error) {
            if (error.name === 'NotAllowedError') {
                throw new Error('Biometric registration was cancelled or timed out');
            } else if (error.name === 'InvalidStateError') {
                throw new Error('This device is already registered');
            } else if (error.name === 'NotSupportedError') {
                throw new Error('This device does not support the required security features');
            }
            throw error;
        }

        // Prepare credential data for server
        const credentialData = {
            id: bufferToBase64url(credential.rawId),
            type: credential.type,
            rawId: bufferToBase64url(credential.rawId),
            response: {
                clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
                attestationObject: bufferToBase64url(credential.response.attestationObject)
            },
            authenticatorAttachment: credential.authenticatorAttachment || 'platform',
            transports: credential.response.getTransports ? credential.response.getTransports() : ['internal']
        };

        // Complete registration on server
        const completeResponse = await fetch(`${API_BASE}/webauthn/register/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, credential: credentialData })
        });

        if (!completeResponse.ok) {
            const error = await completeResponse.json();
            throw new Error(error.detail || 'Failed to complete registration');
        }

        return await completeResponse.json();
    }

    // ==================== AUTHENTICATION ====================

    /**
     * Authenticate using WebAuthn credential (passkey)
     * @param {string} email - User's email address
     * @returns {Promise<Object>} - Authentication result with access token
     */
    async function authenticate(email) {
        if (!email) {
            throw new Error('Email is required for authentication');
        }

        // Get authentication options from server
        const optionsResponse = await fetch(`${API_BASE}/webauthn/authenticate/options`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (!optionsResponse.ok) {
            const error = await optionsResponse.json();
            throw new Error(error.detail || 'Failed to get authentication options');
        }

        const { options, user_name } = await optionsResponse.json();

        // Convert server options to WebAuthn format
        const publicKeyCredentialRequestOptions = {
            challenge: base64urlToBuffer(options.challenge),
            rpId: options.rpId,
            timeout: options.timeout,
            userVerification: options.userVerification,
            allowCredentials: (options.allowCredentials || []).map(cred => ({
                type: cred.type,
                id: base64urlToBuffer(cred.id),
                transports: cred.transports
            }))
        };

        // Call WebAuthn API - triggers biometric prompt
        let assertion;
        try {
            assertion = await navigator.credentials.get({
                publicKey: publicKeyCredentialRequestOptions
            });
        } catch (error) {
            if (error.name === 'NotAllowedError') {
                throw new Error('Biometric verification was cancelled or timed out');
            } else if (error.name === 'SecurityError') {
                throw new Error('Security error during biometric verification');
            }
            throw error;
        }

        // Prepare assertion data for server
        const assertionData = {
            id: bufferToBase64url(assertion.rawId),
            type: assertion.type,
            rawId: bufferToBase64url(assertion.rawId),
            response: {
                clientDataJSON: bufferToBase64url(assertion.response.clientDataJSON),
                authenticatorData: bufferToBase64url(assertion.response.authenticatorData),
                signature: bufferToBase64url(assertion.response.signature),
                userHandle: assertion.response.userHandle ? 
                    bufferToBase64url(assertion.response.userHandle) : null
            }
        };

        // Complete authentication on server
        const completeResponse = await fetch(`${API_BASE}/webauthn/authenticate/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, credential: assertionData })
        });

        if (!completeResponse.ok) {
            const error = await completeResponse.json();
            throw new Error(error.detail || 'Biometric verification failed');
        }

        return await completeResponse.json();
    }

    // ==================== CREDENTIAL MANAGEMENT ====================

    /**
     * Check if user has registered WebAuthn credentials
     * @param {string} email - User's email address
     * @returns {Promise<Object>} - Credential status
     */
    async function getCredentials(email) {
        const response = await fetch(`${API_BASE}/webauthn/credentials/${encodeURIComponent(email)}`);
        return await response.json();
    }

    // ==================== PUBLIC API ====================

    return {
        isSupported,
        getAuthenticatorName,
        register,
        authenticate,
        getCredentials,
        
        // Utility exports for advanced usage
        utils: {
            base64urlToBuffer,
            bufferToBase64url
        }
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebAuthnModule;
}

// Global availability for browser
window.WebAuthnModule = WebAuthnModule;

// ==================== LEGACY COMPATIBILITY ====================

/**
 * Legacy fingerprint function - now uses WebAuthn
 * Kept for backward compatibility
 */
function openFingerprint(email) {
    console.warn('openFingerprint() is deprecated. Use WebAuthnModule.authenticate() instead.');
    
    const modal = document.getElementById("fingerprintModal");
    if (!modal) {
        console.error("Fingerprint modal not found");
        return;
    }
    modal.classList.remove("hidden");

    document.getElementById("fingerprintBtn").onclick = async () => {
        try {
            const result = await WebAuthnModule.authenticate(email);
            
            modal.classList.add("hidden");
            
            // Store token
            localStorage.setItem('access_token', result.access_token);
            localStorage.setItem('user_email', result.user_email);
            localStorage.setItem('user_name', result.user_name);
            
            // Redirect to home
            window.location.href = '/home';
            
        } catch (error) {
            console.error("Fingerprint verification error:", error);
            alert(error.message || "Fingerprint verification failed");
        }
    };
}

/**
 * Legacy QR display function
 */
function showQR(sessionId) {
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
                <button onclick="closeQRAndRedirect()" class="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-bold rounded-lg text-white bg-primary hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-primary transition-all">
                    Continue to Dashboard
                </button>
            </div>
        `;
        document.body.appendChild(qrModal);
    }

    const qrImage = document.getElementById("qrImage");
    qrImage.src = `http://127.0.0.1:8000/qr-image/${sessionId}`;
}

function closeQRAndRedirect() {
    const qrModal = document.getElementById("qrModal");
    if (qrModal) {
        qrModal.remove();
    }
    window.location.href = '/home';
}

// ==================== AUTO-INIT ====================

document.addEventListener('DOMContentLoaded', async function() {
    // Check WebAuthn support on page load
    const support = await WebAuthnModule.isSupported();
    console.log('WebAuthn Support:', support);
    console.log('Authenticator:', WebAuthnModule.getAuthenticatorName());
    
    // Add indicator to page if supported
    if (support.platformAuthenticator) {
        const badge = document.createElement('div');
        badge.className = 'fixed bottom-4 right-4 z-50 flex items-center gap-2 bg-green-500/20 border border-green-500/50 rounded-full px-3 py-1 text-xs text-green-400';
        badge.innerHTML = `
            <span class="material-symbols-outlined text-sm">fingerprint</span>
            <span>${WebAuthnModule.getAuthenticatorName()} Available</span>
        `;
        badge.style.cssText = 'opacity: 0; transition: opacity 0.3s;';
        document.body.appendChild(badge);
        
        // Fade in after a short delay
        setTimeout(() => {
            badge.style.opacity = '0.8';
        }, 1000);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            badge.style.opacity = '0';
            setTimeout(() => badge.remove(), 300);
        }, 5000);
    }
});
