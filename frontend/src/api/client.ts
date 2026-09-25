import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? '/api' });

// Attach token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401: try refresh, retry once, else force logout. Skipped for the auth
// endpoints themselves — a 401 there means "wrong credentials," not "your
// session expired," and the redirect this does (window.location.href, a
// full page reload) was wiping LoginPage's error state before React could
// render "Invalid email or password" (caught by an E2E test — see
// audits/testing_audit.md Finding C6 / frontend/e2e/login-and-view-devices.spec.ts).
const _AUTH_ENDPOINTS = ['/auth/login', '/auth/mfa/login', '/auth/refresh'];
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    const isAuthEndpoint = _AUTH_ENDPOINTS.some((p) => original?.url?.includes(p));
    if (err.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const res = await axios.post('/api/auth/refresh', null, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          });
          const newToken = res.data.access_token;
          localStorage.setItem('access_token', newToken);
          original.headers.Authorization = `Bearer ${newToken}`;
          return api(original);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      } else {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export default api;
