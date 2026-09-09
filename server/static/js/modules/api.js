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
            response.data = null;
            return response;
        }

        const data = await response.json().catch(() => null);
        response.data = data;
        // Also provide .json() resolving to data so calling `await res.json()` works
        response.json = async () => data;

        if (!response.ok) {
            const errorMessage = data?.detail || data?.message || `HTTP Error: ${response.status}`;
            console.error(`API Error [${options.method || 'GET'} ${endpoint}]:`, errorMessage);
        }

        return response;
    } catch (error) {
        console.error(`API Error [${options.method || 'GET'} ${endpoint}]:`, error);
        throw error;
    }
}
