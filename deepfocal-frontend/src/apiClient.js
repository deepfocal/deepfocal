import axios from 'axios';

const normalizeBaseUrl = (url) => {
  if (!url) {
    return null;
  }
  return url.replace(/\/$/, '');
};

const envBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_URL);

const apiClient = axios.create({
  baseURL: envBaseUrl || 'http://localhost:8000',
});

export const setAuthToken = (token) => {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Token ${token}`;
  } else {
    delete apiClient.defaults.headers.common.Authorization;
  }
};

export default apiClient;
