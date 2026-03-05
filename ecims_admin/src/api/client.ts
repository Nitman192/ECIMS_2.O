import axios from 'axios';

let tokenGetter: (() => string | null) | null = null;
let unauthorizedHandler: (() => void) | null = null;

export const bindAuthHandlers = (getToken: () => string | null, onUnauthorized: () => void) => {
  tokenGetter = getToken;
  unauthorizedHandler = onUnauthorized;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000
});

api.interceptors.request.use((config) => {
  const token = tokenGetter?.();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      const requestUrl = String(error?.config?.url ?? '');
      const isAuthLoginRequest = requestUrl.includes('/auth/login');
      const hasAuthHeader = Boolean(error?.config?.headers?.Authorization);
      const hasToken = Boolean(tokenGetter?.());
      if (!isAuthLoginRequest && (hasAuthHeader || hasToken)) {
        unauthorizedHandler?.();
      }
    }
    return Promise.reject(error);
  }
);
