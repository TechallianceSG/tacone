import axios from 'axios'
import type { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Send tacai_session_id cookie
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Request interceptor — attach language
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const lang = localStorage.getItem('tacai_lang') || 'ja'
  if (config.url) {
    const separator = config.url.includes('?') ? '&' : '?'
    if (!config.url.includes('lang=') && !config.params?.lang) {
      config.url = `${config.url}${separator}lang=${lang}`
    }
  }
  return config
})

// Response interceptor — handle auth failures
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      const isAuthEndpoint = url.includes('/api/auth/')
      if (isAuthEndpoint) {
        const currentPath = window.location.pathname
        if (currentPath !== '/login') {
          window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
        }
      }
    }
    return Promise.reject(error)
  }
)

export default client

// ── Auth API ──
export const authApi = {
  login: (email: string, password: string, entityCode: string) =>
    client.post('/api/auth/login', { email, password, entity_code: entityCode }),

  logout: () => client.post('/api/auth/logout'),

  validateSession: () => client.get('/api/auth/session'),

  getCurrentUser: () => client.get('/api/auth/me'),

  changePassword: (currentPassword: string, newPassword: string, confirmPassword: string) =>
    client.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
}

// ── Public API (no auth required) ──
export const publicApi = {
  entities: () => client.get('/api/public/entities'),
}

// ── Users API ──
export const usersApi = {
  list: (params?: Record<string, any>) => client.get('/api/users', { params }),
  get: (userId: string) => client.get(`/api/users/${userId}`),
  create: (data: Record<string, unknown>) => client.post('/api/users', data),
  update: (userId: string, data: Record<string, unknown>) => client.post(`/api/users/${userId}`, data),
  deactivate: (userId: string) => client.post(`/api/users/${userId}/deactivate`),
}

// ── Employees API ──
export const employeeApi = {
  list: (params?: Record<string, any>) => client.get('/api/employees', { params }),
  get: (employeeId: string) => client.get(`/api/employees/${employeeId}`),
  create: (data: Record<string, any>) => client.post('/api/employees', data),
  import: (formData: FormData) => client.post('/api/employees/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  }),
}

// ── Portal API ──
export const portalApi = {
  health: () => client.get('/api/portal/health'),
}

// ── Master Data API (for dropdowns) ──
export const masterdataApi = {
  entities: () => client.get('/api/masterdata/entities'),
  departments: () => client.get('/api/masterdata/departments'),
  teams: () => client.get('/api/masterdata/teams'),
}
