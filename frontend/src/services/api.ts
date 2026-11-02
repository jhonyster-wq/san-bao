import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para inyectar token JWT y sociedad activa
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sanbao_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const activeCompanyId = localStorage.getItem('sanbao_active_company_id');
  if (activeCompanyId) {
    config.headers['X-Company-ID'] = activeCompanyId;
  }

  return config;
});

// Interceptor para redirección por sesión expirada
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('sanbao_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
