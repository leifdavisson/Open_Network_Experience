export const ADMIN_KEY = window.ADMIN_KEY || "admin-noc-key-change-me";

export async function apiClient(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-API-Key': ADMIN_KEY,
        ...options.headers
    };

    const config = {
        ...options,
        headers
    };

    try {
        const response = await fetch(endpoint, config);

        // Handle 204 No Content
        if (response.status === 204) {
            return null;
        }

        const data = await response.json().catch(() => null);

        if (!response.ok) {
            const errorMessage = data?.detail || data?.message || \`HTTP Error: \${response.status}\`;
            throw new Error(errorMessage);
        }

        return data;
    } catch (error) {
        console.error(\`API Error [\${options.method || 'GET'} \${endpoint}]:\`, error);
        throw error;
    }
}
