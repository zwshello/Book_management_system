import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('library_access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const path = error.config?.url ?? ''
      if (!path.startsWith('/auth/login')) {
        for (const key of ['library_access', 'library_refresh', 'library_user']) sessionStorage.removeItem(key)
        if (window.location.pathname !== '/login') window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)
