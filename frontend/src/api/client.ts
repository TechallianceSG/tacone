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
// When a non-auth API call returns 401, the session has expired.
// Dispatch a custom event so the router can handle navigation (SPA, no hard reload).
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      const isAuthEndpoint = url.includes('/api/auth/')
      // Only redirect on non-auth endpoints — auth endpoints return 401 for bad credentials
      if (!isAuthEndpoint) {
        window.dispatchEvent(new CustomEvent('tacai:session-expired'))
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
  delete: (employeeId: string) => client.delete(`/api/employees/${employeeId}`),
  update: (employeeId: string, data: Record<string, any>) => client.post(`/api/employees/${employeeId}`, data),
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

// ── Payroll SG API ──
export const payrollSgApi = {
  salaryMaster: (params?: Record<string, any>) => client.get('/api/payroll/sg/salary-master', { params }),
  saveSalaryMaster: (data: Record<string, any>) => client.post('/api/payroll/sg/salary-master', data),
  batches: (params?: Record<string, any>) => client.get('/api/payroll/sg/batches', { params }),
  createBatch: (data: Record<string, any>) => client.post('/api/payroll/sg/batches', data),
  getBatch: (batchId: string) => client.get(`/api/payroll/sg/batches/${batchId}`),
  calculateBatch: (batchId: string, data?: Record<string, any>) =>
    client.post(`/api/payroll/sg/batches/${batchId}/calculate`, data || {}),
  sheets: (params?: Record<string, any>) => client.get('/api/payroll/sg/sheets', { params }),
  getSheet: (sheetId: string) => client.get(`/api/payroll/sg/sheets/${sheetId}`),
  confirmSheet: (sheetId: string) => client.post(`/api/payroll/sg/sheets/${sheetId}/confirm`, {}),
  releaseSheet: (sheetId: string) => client.post(`/api/payroll/sg/sheets/${sheetId}/release`, {}),
  payslips: (params?: Record<string, any>) => client.get('/api/payroll/sg/payslips', { params }),
  emailPayslip: (payslipId: string) => client.post(`/api/payroll/sg/payslips/${payslipId}/email`, {}),
  batchEmailPayslips: (data: Record<string, any>) => client.post('/api/payroll/sg/payslips/batch-email', data),
}

// ── Payroll JP API ──
export const payrollJpApi = {
  itemDefinitions: (params?: Record<string, any>) => client.get('/api/payroll/jp/item-definitions', { params }),
  saveItemDefinition: (data: Record<string, any>) => client.post('/api/payroll/jp/item-definitions', data),
  parameters: (params?: Record<string, any>) => client.get('/api/payroll/jp/parameters', { params }),
  saveParameter: (data: Record<string, any>) => client.post('/api/payroll/jp/parameters', data),
  employees: (params?: Record<string, any>) => client.get('/api/payroll/jp/employees', { params }),
  saveEmployee: (data: Record<string, any>) => client.post('/api/payroll/jp/employees', data),
  batches: (params?: Record<string, any>) => client.get('/api/payroll/jp/batches', { params }),
  createBatch: (data: Record<string, any>) => client.post('/api/payroll/jp/batches', data),
  calculateBatch: (batchId: string) => client.post(`/api/payroll/jp/batches/${batchId}/calculate`, {}),
  sheets: (params?: Record<string, any>) => client.get('/api/payroll/jp/sheets', { params }),
  confirmSheet: (sheetId: string) => client.post(`/api/payroll/jp/sheets/${sheetId}/confirm`, {}),
  payslips: (params?: Record<string, any>) => client.get('/api/payroll/jp/payslips', { params }),
  emailPayslip: (payslipId: string) => client.post(`/api/payroll/jp/payslips/${payslipId}/email`, {}),
}

// ── Payroll CN API ──
export const payrollCnApi = {
  socialInsuranceRules: (params?: Record<string, any>) => client.get('/api/payroll/cn/social-insurance-rules', { params }),
  saveSIRule: (data: Record<string, any>) => client.post('/api/payroll/cn/social-insurance-rules', data),
  taxBrackets: (params?: Record<string, any>) => client.get('/api/payroll/cn/tax-brackets', { params }),
  saveTaxBracket: (data: Record<string, any>) => client.post('/api/payroll/cn/tax-brackets', data),
  employees: (params?: Record<string, any>) => client.get('/api/payroll/cn/employees', { params }),
  saveEmployee: (data: Record<string, any>) => client.post('/api/payroll/cn/employees', data),
  batches: (params?: Record<string, any>) => client.get('/api/payroll/cn/batches', { params }),
  createBatch: (data: Record<string, any>) => client.post('/api/payroll/cn/batches', data),
  calculateBatch: (batchId: string) => client.post(`/api/payroll/cn/batches/${batchId}/calculate`, {}),
  payslips: (params?: Record<string, any>) => client.get('/api/payroll/cn/payslips', { params }),
  emailPayslip: (payslipId: string) => client.post(`/api/payroll/cn/payslips/${payslipId}/email`, {}),
}

// ── Invoice API ──
export const invoiceApi = {
  // Flow 1: Customer Projects
  projects: (params?: Record<string, any>) => client.get('/api/invoice/customer-projects', { params }),
  getProject: (projectId: string) => client.get(`/api/invoice/customer-projects/${projectId}`),
  saveProject: (data: Record<string, any>) => client.post('/api/invoice/customer-projects', data),
  // Flow 2: Pending Invoices
  pending: (params?: Record<string, any>) => client.get('/api/invoice/pending', { params }),
  scanPending: (data?: Record<string, any>) => client.post('/api/invoice/pending/scan', data || {}),
  convertPending: (pendingId: string, data?: Record<string, any>) =>
    client.post(`/api/invoice/pending/${pendingId}/convert`, data || {}),
  remindPending: (pendingId: string) => client.post(`/api/invoice/pending/${pendingId}/remind`, {}),
  // Flow 3: Invoice CRUD
  list: (params?: Record<string, any>) => client.get('/api/invoice/invoices', { params }),
  get: (invoiceId: string) => client.get(`/api/invoice/invoices/${invoiceId}`),
  create: (data: Record<string, any>) => client.post('/api/invoice/invoices', data),
  update: (invoiceId: string, data: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/update`, data),
  submit: (invoiceId: string, data?: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/submit`, data || {}),
  // Flow 4: Approval & Sending
  approve: (invoiceId: string, data?: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/approve`, data || {}),
  reject: (invoiceId: string, data?: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/reject`, data || {}),
  sendEmail: (invoiceId: string, data?: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/send-email`, data || {}),
  getEmailLogs: (invoiceId: string) => client.get(`/api/invoice/invoices/${invoiceId}/email-logs`),
  getApprovals: (invoiceId: string) => client.get(`/api/invoice/invoices/${invoiceId}/approvals`),
  // Flow 5: Payment & Reconciliation
  registerPayment: (invoiceId: string, data: Record<string, any>) => client.post(`/api/invoice/invoices/${invoiceId}/payments`, data),
  getPayments: (invoiceId: string) => client.get(`/api/invoice/invoices/${invoiceId}/payments`),
  getReconciliation: (invoiceId: string) => client.get(`/api/invoice/invoices/${invoiceId}/reconciliation`),
  reconcile: (invoiceId: string) => client.post(`/api/invoice/invoices/${invoiceId}/reconcile`, {}),
  overdue: (params?: Record<string, any>) => client.get('/api/invoice/overdue', { params }),
}
