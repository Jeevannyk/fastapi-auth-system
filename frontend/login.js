// Login Form Handler
document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.querySelector('form');
    const emailInput = document.querySelector('input[type="text"]');
    const passwordInput = document.querySelector('input[type="password"]');
    const submitButton = document.querySelector('button[type="button"]');
    let errorContainer = document.getElementById('error-message');

    // Create error container if it doesn't exist
    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.id = 'error-message';
        errorContainer.className = 'mt-4 p-3 bg-red-500/10 border border-red-500 rounded-lg text-red-400 text-sm text-center';
        errorContainer.style.display = 'none';
        loginForm.appendChild(errorContainer);
    }

    // Add event listener to form submit button
    submitButton.addEventListener('click', async function (e) {
        e.preventDefault();

        // Clear previous errors
        errorContainer.textContent = '';
        errorContainer.style.display = 'none';
        errorContainer.className = 'mt-4 p-3 bg-red-500/10 border border-red-500 rounded-lg text-red-400 text-sm text-center';

        // Get input values
        const email = emailInput.value.trim();
        const accessKey = passwordInput.value;

        // Basic validation
        if (!email || !accessKey) {
            showError('Please enter both Email and Access Key');
            return;
        }

        // Show loading state
        submitButton.disabled = true;
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<span>Verifying...</span>';

        try {
            // Make API call to login endpoint
            const response = await fetch('http://127.0.0.1:8000/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    access_key: accessKey
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Login successful - store token and check next step
                if (data.access_token) {
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('user_email', email);
                }
                
                if (data.next === "fingerprint") {
                    showSuccess('Credentials verified! Proceeding to biometric...');
                    setTimeout(() => {
                        openFingerprint(email);
                    }, 500);
                } else {
                    // Fallback if no next step specified
                    showSuccess('Login successful!');
                    setTimeout(() => {
                        window.location.href = '/home';
                    }, 1000);
                }

            } else {
                // Login failed
                showError(data.detail || 'Invalid credentials. Please try again.');
            }
        } catch (error) {
            console.error('Login error:', error);
            showError('Connection error. Please check if the server is running.');
        } finally {
            // Restore button state
            submitButton.disabled = false;
            submitButton.innerHTML = originalText;
        }
    });

    // Helper function to show error messages
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.className = 'mt-4 p-3 bg-red-500/10 border border-red-500 rounded-lg text-red-400 text-sm text-center';
        errorContainer.style.display = 'block';
    }

    // Helper function to show success messages
    function showSuccess(message) {
        errorContainer.textContent = message;
        errorContainer.className = 'mt-4 p-3 bg-green-500/10 border border-green-500 rounded-lg text-green-400 text-sm text-center';
        errorContainer.style.display = 'block';
    }

    // Allow Enter key to submit form
    emailInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            submitButton.click();
        }
    });

    passwordInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            submitButton.click();
        }
    });

    // Password visibility toggle
    const allButtons = document.querySelectorAll('button[type="button"]');
    allButtons.forEach(button => {
        const icon = button.querySelector('.material-symbols-outlined');
        if (icon && (icon.textContent === 'visibility_off' || icon.textContent === 'visibility')) {
            button.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    icon.textContent = 'visibility';
                } else {
                    passwordInput.type = 'password';
                    icon.textContent = 'visibility_off';
                }
            });
        }
    });
});
