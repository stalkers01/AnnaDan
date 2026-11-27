/**
 * Small, shared API client for Annadan's static frontend.
 * Configure the API origin once with window.ANNADAN_API_BASE_URL when deploying.
 */
(function () {
    const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    const API_BASE_URL = window.ANNADAN_API_BASE_URL || (isLocal
        ? 'http://127.0.0.1:8000/api/v1'
        : 'https://annadan-api.onrender.com/api/v1');
    const TOKEN_KEY = 'annadanAccessToken';
    const USER_KEY = 'annadanCurrentUser';

    async function request(path, options = {}) {
        const headers = new Headers(options.headers || {});
        const token = sessionStorage.getItem(TOKEN_KEY);

        if (options.body && !(options.body instanceof FormData)) {
            headers.set('Content-Type', 'application/json');
        }
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
        }

        let response;
        try {
            response = await fetch(`${API_BASE_URL}${path}`, {
                ...options,
                headers,
            });
        } catch (error) {
            throw new Error('The Annadan server could not be reached. Check that the API is running.');
        }

        if (response.status === 204) {
            return null;
        }

        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json')
            ? await response.json()
            : await response.text();

        if (!response.ok) {
            const detail = typeof payload === 'object' && payload !== null
                ? payload.detail
                : payload;
            throw new Error(Array.isArray(detail)
                ? detail.map((item) => item.msg || 'Invalid input').join(', ')
                : (detail || `Request failed (${response.status})`));
        }

        return payload;
    }

    function saveSession(authResponse) {
        sessionStorage.setItem(TOKEN_KEY, authResponse.access_token);
        sessionStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
    }

    function getCachedUser() {
        try {
            return JSON.parse(sessionStorage.getItem(USER_KEY) || 'null');
        } catch (_error) {
            return null;
        }
    }

    function clearSession() {
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(USER_KEY);
    }

    async function currentUser(forceRefresh = false) {
        const cachedUser = getCachedUser();
        if (cachedUser && !forceRefresh) {
            return cachedUser;
        }
        if (!sessionStorage.getItem(TOKEN_KEY)) {
            return null;
        }
        try {
            const user = await request('/auth/me');
            sessionStorage.setItem(USER_KEY, JSON.stringify(user));
            return user;
        } catch (error) {
            clearSession();
            throw error;
        }
    }

    window.AnnadanAPI = {
        request,
        saveSession,
        getCachedUser,
        currentUser,
        clearSession,
        apiBaseUrl: API_BASE_URL,
    };
})();
