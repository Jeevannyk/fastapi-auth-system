/**
 * CyberGuard Login Module - Production Authentication
 * Features:
 * - Google OAuth 2.0
 * - WebAuthn/Passkeys (Fingerprint/Windows Hello/Touch ID)
 * - Real MFA with email verification
 */

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

// ==================== WEBAUTHN SUPPORT DETECTION ====================

async function isWebAuthnSupported() {
    if (!window.PublicKeyCredential) {
        return { supported: false, reason: 'WebAuthn not supported by browser' };
    }
    
    try {
        // Check if platform authenticator is available (fingerprint, Face ID, Windows Hello)
        const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
        return { 
            supported: available, 
            reason: available ? 'Platform authenticator available' : 'No platform authenticator found'
        };
    } catch (e) {
        return { supported: false, reason: e.message };
    }
}

// ==================== MAIN INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async function () {
    const emailInput = document.getElementById('emailInput');
    const passwordInput = document.getElementById('passwordInput');
    const loginBtn = document.getElementById('loginBtn');
    const googleSignInBtn = document.getElementById('googleSignInBtn');
    const togglePasswordBtn = document.getElementById('togglePasswordBtn');
    const fingerprintSection = document.getElementById('fingerprintSection');
    const webauthnLoginBtn = document.getElementById('webauthnLoginBtn');

    // Check for Google OAuth callback
    handleGoogleCallback();

    // Check WebAuthn support and show fingerprint option if available
    const webauthnStatus = await isWebAuthnSupported();
    console.log('WebAuthn status:', webauthnStatus);
    
    if (webauthnStatus.supported) {
        fingerprintSection.classList.remove('hidden');
    }

    // ==================== GOOGLE SIGN-IN ====================
    
    googleSignInBtn.addEventListener('click', async function() {
        try {
            // Check if Google OAuth is configured
            const statusRes = await fetch(`${API_BASE}/auth/google/status`);
            const statusData = await statusRes.json();
            
            if (!statusData.configured) {
                showPopup('error', 'Not Configured', 'Google Sign-In is not configured. Please contact the administrator.', null);
                return;
            }
            
            // Redirect to Google OAuth
            window.location.href = `${API_BASE}/auth/google`;
        } catch (error) {
            console.error('Google Sign-In error:', error);
            showPopup('error', 'Connection Error', 'Could not connect to the server. Please try again.', null);
        }
    });

    // ==================== PASSWORD LOGIN ====================

    loginBtn.addEventListener('click', async function (e) {
        e.preventDefault();
        
        const email = emailInput.value.trim();
        const accessKey = passwordInput.value;

        if (!email || !accessKey) {
            showPopup('error', 'Validation Error', 'Please enter both Email and Access Key', null);
            return;
        }

        loginBtn.disabled = true;
        const originalText = loginBtn.innerHTML;
        loginBtn.innerHTML = '<span>Verifying...</span>';

        try {
            const response = await fetch(`${API_BASE}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, access_key: accessKey })
            });

            const data = await response.json();

            if (response.ok) {
                // Store partial token for MFA
                sessionStorage.setItem('partial_token', data.partial_token);
                sessionStorage.setItem('user_email', data.user_email);
                sessionStorage.setItem('user_name', data.user_name || 'User');
                sessionStorage.setItem('mfa_methods', JSON.stringify(data.mfa_methods));

                // Show MFA modal
                showMFAModal();

            } else {
                if (response.status === 404) {
                    showPopup('error', 'Account Not Found', data.detail || 'No account exists with this email.', () => {
                        window.location.href = '/signup-page';
                    }, 'Sign Up');
                } else if (response.status === 400 && data.detail.includes('Google')) {
                    showPopup('error', 'Google Account', data.detail, () => {
                        window.location.href = `${API_BASE}/auth/google`;
                    }, 'Sign in with Google');
                } else {
                    showPopup('error', 'Login Failed', data.detail || 'Invalid credentials.', null);
                }
            }
        } catch (error) {
            console.error('Login error:', error);
            showPopup('error', 'Connection Error', 'Please check if the server is running.', null);
        } finally {
            loginBtn.disabled = false;
            loginBtn.innerHTML = originalText;
        }
    });

    // ==================== WEBAUTHN LOGIN (Fingerprint) ====================

    webauthnLoginBtn.addEventListener('click', async function() {
        const email = emailInput.value.trim();
        
        if (!email) {
            showPopup('error', 'Email Required', 'Please enter your email address first.', null);
            return;
        }

        // Check if user has registered credentials
        try {
            const credCheck = await fetch(`${API_BASE}/webauthn/credentials/${encodeURIComponent(email)}`);
            const credData = await credCheck.json();
            
            if (!credData.has_credentials) {
                showPopup('error', 'No Fingerprint Registered', 'You haven\'t set up fingerprint login yet. Please log in with password first, then set up fingerprint.', null);
                return;
            }

            // Start WebAuthn authentication
            await performWebAuthnAuth(email);

        } catch (error) {
            console.error('WebAuthn check error:', error);
            showPopup('error', 'Error', 'Could not check fingerprint status. Please try again.', null);
        }
    });

    // ==================== PASSWORD VISIBILITY TOGGLE ====================

    togglePasswordBtn.addEventListener('click', function(e) {
        e.preventDefault();
        const icon = togglePasswordBtn.querySelector('.material-symbols-outlined');
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            icon.textContent = 'visibility';
        } else {
            passwordInput.type = 'password';
            icon.textContent = 'visibility_off';
        }
    });

    // Enter key handlers
    emailInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') loginBtn.click(); });
    passwordInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') loginBtn.click(); });
});

// ==================== GOOGLE OAUTH CALLBACK HANDLER ====================

function handleGoogleCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (urlParams.get('google_success') === 'true') {
        const token = urlParams.get('token');
        const email = urlParams.get('email');
        const name = urlParams.get('name');
        
        if (token) {
            // Store credentials
            localStorage.setItem('access_token', token);
            localStorage.setItem('user_email', email);
            localStorage.setItem('user_name', name);
            
            // Clean URL
            window.history.replaceState({}, document.title, '/login');
            
            // Show success and redirect
            showPopup('success', 'Google Sign-In Successful!', `Welcome, ${name}! Redirecting to dashboard...`, () => {
                window.location.href = '/home';
            });
        }
    }
}

// ==================== MFA MODAL (Real Google-Style) ====================

async function showMFAModal() {
    const modal = document.getElementById('mfaModal');
    const challengeNumberEl = document.getElementById('mfaChallengeNumber');
    const optionsContainer = document.getElementById('mfaOptions');
    const timerEl = document.getElementById('mfaTimer');
    const errorEl = document.getElementById('mfaError');
    const sentToEl = document.getElementById('mfaSentTo');
    const cancelBtn = document.getElementById('cancelMfaBtn');

    if (!modal) return;

    const partialToken = sessionStorage.getItem('partial_token');
    if (!partialToken) {
        showPopup('error', 'Session Error', 'Please login again.', null);
        return;
    }

    try {
        // Generate MFA challenge (sends email)
        const response = await fetch(`${API_BASE}/mfa/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${partialToken}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to generate MFA challenge');
        }

        const data = await response.json();
        const { challenge_id, correct_number, options, expires_in, sent_to } = data;

        // Display the number to match
        challengeNumberEl.textContent = correct_number;
        sentToEl.textContent = `📧 Sent to: ${sent_to}`;

        // Create option buttons
        optionsContainer.innerHTML = '';
        options.forEach(num => {
            const btn = document.createElement('button');
            btn.className = 'px-6 py-4 text-xl font-bold font-mono bg-background-dark border-2 border-border-dark rounded-lg text-white hover:border-primary hover:bg-primary/10 transition-all duration-200 min-w-[80px]';
            btn.textContent = num;
            btn.dataset.number = num;
            btn.addEventListener('click', () => handleMFAOptionClick(num, challenge_id, btn));
            optionsContainer.appendChild(btn);
        });

        errorEl.classList.add('hidden');
        modal.classList.remove('hidden');

        // Start countdown
        let timeLeft = expires_in;
        const updateTimer = () => {
            const mins = Math.floor(timeLeft / 60);
            const secs = timeLeft % 60;
            timerEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                modal.classList.add('hidden');
                clearMFASession();
                showPopup('error', 'Time Expired', 'The verification time has expired. Please login again.', null);
            }
            timeLeft--;
        };
        updateTimer();
        const timerInterval = setInterval(updateTimer, 1000);

        // Cancel button
        const handleCancel = () => {
            clearInterval(timerInterval);
            clearMFASession();
            modal.classList.add('hidden');
            cancelBtn.removeEventListener('click', handleCancel);
        };
        cancelBtn.addEventListener('click', handleCancel);

        // Store timer interval for cleanup
        window.mfaTimerInterval = timerInterval;

    } catch (error) {
        console.error('MFA generation error:', error);
        showPopup('error', 'MFA Error', error.message || 'Failed to generate verification. Please try again.', null);
        clearMFASession();
    }
}

async function handleMFAOptionClick(selectedNumber, challengeId, btnElement) {
    const modal = document.getElementById('mfaModal');
    const optionsContainer = document.getElementById('mfaOptions');
    const errorEl = document.getElementById('mfaError');

    // Disable all buttons
    optionsContainer.querySelectorAll('button').forEach(b => b.disabled = true);
    btnElement.textContent = '...';

    const partialToken = sessionStorage.getItem('partial_token');

    try {
        const response = await fetch(`${API_BASE}/mfa/verify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${partialToken}`
            },
            body: JSON.stringify({
                challenge_id: challengeId,
                selected_number: selectedNumber
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Success! Clear timer and store full token
            if (window.mfaTimerInterval) clearInterval(window.mfaTimerInterval);
            
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_email', sessionStorage.getItem('user_email'));
            localStorage.setItem('user_name', sessionStorage.getItem('user_name'));
            clearMFASession();

            modal.classList.add('hidden');
            
            // Check if user should set up WebAuthn
            const webauthnStatus = await isWebAuthnSupported();
            if (webauthnStatus.supported) {
                const email = localStorage.getItem('user_email');
                const credCheck = await fetch(`${API_BASE}/webauthn/credentials/${encodeURIComponent(email)}`);
                const credData = await credCheck.json();
                
                if (!credData.has_credentials) {
                    // Offer to set up WebAuthn
                    showWebAuthnRegisterModal();
                    return;
                }
            }
            
            // Redirect to home
            showPopup('success', 'Login Successful!', 'Welcome back! Redirecting to dashboard...', () => {
                window.location.href = '/home';
            });

        } else {
            // Wrong number
            if (window.mfaTimerInterval) clearInterval(window.mfaTimerInterval);
            btnElement.classList.add('border-red-500', 'bg-red-500/20');
            btnElement.textContent = selectedNumber;
            errorEl.textContent = data.detail || 'Wrong number selected.';
            errorEl.classList.remove('hidden');
            
            setTimeout(() => {
                modal.classList.add('hidden');
                clearMFASession();
                showPopup('error', 'Verification Failed', data.detail || 'Please login and try again.', null);
            }, 1500);
        }

    } catch (error) {
        console.error('MFA verification error:', error);
        if (window.mfaTimerInterval) clearInterval(window.mfaTimerInterval);
        errorEl.textContent = 'Connection error. Please try again.';
        errorEl.classList.remove('hidden');
        optionsContainer.querySelectorAll('button').forEach(b => {
            b.disabled = false;
            b.textContent = b.dataset.number;
        });
    }
}

function clearMFASession() {
    sessionStorage.removeItem('partial_token');
    sessionStorage.removeItem('user_email');
    sessionStorage.removeItem('user_name');
    sessionStorage.removeItem('mfa_methods');
}

// ==================== WEBAUTHN REGISTRATION ====================

function showWebAuthnRegisterModal() {
    const modal = document.getElementById('webauthnRegisterModal');
    const skipBtn = document.getElementById('skipWebauthnBtn');
    const registerBtn = document.getElementById('registerWebauthnBtn');

    modal.classList.remove('hidden');

    skipBtn.onclick = () => {
        modal.classList.add('hidden');
        showPopup('success', 'Login Successful!', 'Redirecting to dashboard...', () => {
            window.location.href = '/home';
        });
    };

    registerBtn.onclick = async () => {
        modal.classList.add('hidden');
        await performWebAuthnRegistration();
    };
}

async function performWebAuthnRegistration() {
    const email = localStorage.getItem('user_email');
    
    try {
        // Get registration options from server
        const optionsRes = await fetch(`${API_BASE}/webauthn/register/options`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (!optionsRes.ok) {
            const error = await optionsRes.json();
            throw new Error(error.detail || 'Failed to get registration options');
        }

        const { options } = await optionsRes.json();

        // Convert base64url to ArrayBuffer
        const publicKeyOptions = {
            ...options,
            challenge: base64urlToBuffer(options.challenge),
            user: {
                ...options.user,
                id: base64urlToBuffer(options.user.id)
            },
            excludeCredentials: options.excludeCredentials?.map(cred => ({
                ...cred,
                id: base64urlToBuffer(cred.id)
            })) || []
        };

        // Call WebAuthn API (triggers fingerprint/Windows Hello)
        const credential = await navigator.credentials.create({
            publicKey: publicKeyOptions
        });

        // Prepare credential for server
        const credentialData = {
            id: bufferToBase64url(credential.rawId),
            type: credential.type,
            rawId: bufferToBase64url(credential.rawId),
            response: {
                clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
                attestationObject: bufferToBase64url(credential.response.attestationObject)
            },
            authenticatorAttachment: credential.authenticatorAttachment,
            transports: credential.response.getTransports ? credential.response.getTransports() : ['internal']
        };

        // Complete registration on server
        const completeRes = await fetch(`${API_BASE}/webauthn/register/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, credential: credentialData })
        });

        if (!completeRes.ok) {
            const error = await completeRes.json();
            throw new Error(error.detail || 'Failed to complete registration');
        }

        showPopup('success', 'Fingerprint Registered!', 'You can now use fingerprint for faster login. Redirecting...', () => {
            window.location.href = '/home';
        });

    } catch (error) {
        console.error('WebAuthn registration error:', error);
        if (error.name === 'NotAllowedError') {
            showPopup('error', 'Cancelled', 'Fingerprint setup was cancelled. Redirecting...', () => {
                window.location.href = '/home';
            });
        } else {
            showPopup('error', 'Registration Failed', error.message || 'Could not register fingerprint.', () => {
                window.location.href = '/home';
            });
        }
    }
}

// ==================== WEBAUTHN AUTHENTICATION ====================

async function performWebAuthnAuth(email) {
    const modal = document.getElementById('webauthnAuthModal');
    const statusEl = document.getElementById('webauthnAuthStatus');
    const cancelBtn = document.getElementById('cancelWebauthnAuthBtn');

    modal.classList.remove('hidden');
    statusEl.textContent = 'Requesting authentication options...';

    let cancelled = false;
    cancelBtn.onclick = () => {
        cancelled = true;
        modal.classList.add('hidden');
    };

    try {
        // Get authentication options from server
        const optionsRes = await fetch(`${API_BASE}/webauthn/authenticate/options`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (!optionsRes.ok) {
            const error = await optionsRes.json();
            throw new Error(error.detail || 'Failed to get authentication options');
        }

        const { options, user_name } = await optionsRes.json();

        statusEl.textContent = 'Touch your fingerprint sensor...';

        // Convert base64url to ArrayBuffer
        const publicKeyOptions = {
            ...options,
            challenge: base64urlToBuffer(options.challenge),
            allowCredentials: options.allowCredentials?.map(cred => ({
                ...cred,
                id: base64urlToBuffer(cred.id)
            })) || []
        };

        // Call WebAuthn API
        const assertion = await navigator.credentials.get({
            publicKey: publicKeyOptions
        });

        if (cancelled) return;

        statusEl.textContent = 'Verifying...';

        // Prepare assertion for server
        const assertionData = {
            id: bufferToBase64url(assertion.rawId),
            type: assertion.type,
            rawId: bufferToBase64url(assertion.rawId),
            response: {
                clientDataJSON: bufferToBase64url(assertion.response.clientDataJSON),
                authenticatorData: bufferToBase64url(assertion.response.authenticatorData),
                signature: bufferToBase64url(assertion.response.signature),
                userHandle: assertion.response.userHandle ? bufferToBase64url(assertion.response.userHandle) : null
            }
        };

        // Complete authentication on server
        const completeRes = await fetch(`${API_BASE}/webauthn/authenticate/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, credential: assertionData })
        });

        const data = await completeRes.json();

        if (!completeRes.ok) {
            throw new Error(data.detail || 'Authentication failed');
        }

        modal.classList.add('hidden');

        // Store credentials
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user_email', data.user_email);
        localStorage.setItem('user_name', data.user_name);

        showPopup('success', 'Biometric Verified!', `Welcome back, ${data.user_name}! Redirecting...`, () => {
            window.location.href = '/home';
        });

    } catch (error) {
        console.error('WebAuthn authentication error:', error);
        modal.classList.add('hidden');
        
        if (error.name === 'NotAllowedError') {
            showPopup('error', 'Cancelled', 'Fingerprint verification was cancelled.', null);
        } else {
            showPopup('error', 'Verification Failed', error.message || 'Fingerprint verification failed.', null);
        }
    }
}

// ==================== POPUP MODAL ====================

function showPopup(type, title, message, onClose, buttonText = 'OK') {
    const modal = document.getElementById('popupModal');
    const content = document.getElementById('popupContent');
    const icon = document.getElementById('popupIcon');
    const titleEl = document.getElementById('popupTitle');
    const messageEl = document.getElementById('popupMessage');
    const closeBtn = document.getElementById('popupCloseBtn');

    if (!modal) return;

    if (type === 'success') {
        icon.className = 'inline-flex items-center justify-center size-16 rounded-full mb-4 bg-green-500/20 ring-1 ring-green-500/40';
        icon.innerHTML = '<span class="material-symbols-outlined text-green-400 text-4xl">check_circle</span>';
        closeBtn.className = 'w-full py-3 px-4 text-sm font-bold rounded-lg bg-green-500 hover:bg-green-600 text-white transition-all duration-200 shadow-[0_0_15px_rgba(34,197,94,0.4)]';
    } else {
        icon.className = 'inline-flex items-center justify-center size-16 rounded-full mb-4 bg-red-500/20 ring-1 ring-red-500/40';
        icon.innerHTML = '<span class="material-symbols-outlined text-red-400 text-4xl">error</span>';
        closeBtn.className = 'w-full py-3 px-4 text-sm font-bold rounded-lg bg-primary hover:bg-blue-600 text-white transition-all duration-200 shadow-[0_0_15px_rgba(19,91,236,0.4)]';
    }

    titleEl.textContent = title;
    messageEl.textContent = message;
    closeBtn.textContent = buttonText;

    modal.classList.remove('hidden');
    setTimeout(() => {
        content.classList.remove('scale-95');
        content.classList.add('scale-100');
    }, 10);

    const handleClose = () => {
        content.classList.remove('scale-100');
        content.classList.add('scale-95');
        setTimeout(() => {
            modal.classList.add('hidden');
            if (onClose) onClose();
        }, 200);
        closeBtn.removeEventListener('click', handleClose);
    };

    closeBtn.addEventListener('click', handleClose);
}
