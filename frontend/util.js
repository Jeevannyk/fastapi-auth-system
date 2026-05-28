export async function api(path, options = {}) {
    const res = await fetch(path, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
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
