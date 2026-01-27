// Home Page Dashboard Handler
document.addEventListener('DOMContentLoaded', function () {
    // Check if user is logged in
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        // No token found, redirect to login
        window.location.href = '/';
        return;
    }

    // Handle logout button
    const logoutButton = document.querySelector('button');
    if (logoutButton && logoutButton.textContent.includes('Sign Out')) {
        logoutButton.addEventListener('click', function (e) {
            e.preventDefault();

            // Clear stored tokens
            localStorage.removeItem('access_token');
            sessionStorage.removeItem('user_id');

            // Show logout message briefly
            const originalText = this.innerHTML;
            this.innerHTML = '<span class="material-symbols-outlined text-[20px]">logout</span> Signing Out...';

            // Redirect to login page after brief delay
            setTimeout(() => {
                window.location.href = '/';
            }, 500);
        });
    }

    // Handle mobile menu toggle
    const menuButton = document.querySelector('button[class*="md:hidden"]');
    const sidebar = document.querySelector('aside');

    if (menuButton && sidebar) {
        menuButton.addEventListener('click', function () {
            sidebar.classList.toggle('hidden');
            sidebar.classList.toggle('flex');
        });
    }

    // Add animation to stats on page load
    animateStats();
});

// Animate stats counter on page load
function animateStats() {
    const statValues = document.querySelectorAll('h3.text-3xl');

    statValues.forEach(stat => {
        const text = stat.textContent;
        // Only animate numeric values
        const match = text.match(/[\d,]+/);
        if (match) {
            const finalValue = parseInt(match[0].replace(/,/g, ''));
            animateValue(stat, 0, finalValue, 1500, text);
        }
    });
}

function animateValue(element, start, end, duration, originalText) {
    const range = end - start;
    const increment = range / (duration / 16); // 60fps
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= end) {
            current = end;
            clearInterval(timer);
        }

        // Format with commas
        const formattedValue = Math.floor(current).toLocaleString();
        element.textContent = originalText.replace(/[\d,]+/, formattedValue);
    }, 16);
}
