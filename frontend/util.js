// Read a cookie value by name (used for the readable CSRF token cookie).
export function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

// Build headers for a request, attaching the CSRF token on state-changing calls.
export function withCsrf(method, headers = {}) {
    const out = { ...headers };
    if (UNSAFE_METHODS.has((method || "GET").toUpperCase())) {
        const token = getCookie("csrf_token");
        if (token) out["X-CSRF-Token"] = token;
    }
    return out;
}

export async function api(path, options = {}) {
    const method = options.method || "GET";
    const res = await fetch(path, {
        credentials: "include",
        ...options,
        headers: withCsrf(method, { "Content-Type": "application/json", ...(options.headers || {}) }),
    });
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            if (body && body.detail) detail = body.detail;
        } catch {}
        throw new Error(typeof detail === "string" ? detail : "Request failed");
    }
    if (res.status === 204) return null;
    return res.json();
}

export function showError(node, message) {
    node.textContent = message;
    node.classList.remove("hidden");
}
