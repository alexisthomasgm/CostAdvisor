import axios from 'axios';

// In dev: empty baseURL → Vite proxy forwards /api and /auth to the backend.
// In prod: VITE_API_BASE_URL points at the deployed backend (e.g. https://api.yourdomain.com).
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,  // Send cookies (JWT) with every request
});

// Response interceptor: redirect to login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Only redirect if not already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;