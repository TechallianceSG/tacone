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

// ── Master Data API (for dropdowns + CRUD) ──
export const masterdataApi = {
  // Entities
  entities: () => client.get('/api/masterdata/entities'),
  entity: (id: string) => client.get(`/api/masterdata/entities/${id}`),
  createEntity: (data: Record<string, unknown>) => client.post('/api/masterdata/entities', data),
  updateEntity: (id: string, data: Record<string, unknown>) => client.post(`/api/masterdata/entities/${id}`, data),
  deleteEntity: (id: string, data?: Record<string, unknown>) => client.delete(`/api/masterdata/entities/${id}`, { data }),
  // Departments
  departments: () => client.get('/api/masterdata/departments'),
  department: (id: string) => client.get(`/api/masterdata/departments/${id}`),
  createDepartment: (data: Record<string, unknown>) => client.post('/api/masterdata/departments', data),
  updateDepartment: (id: string, data: Record<string, unknown>) => client.post(`/api/masterdata/departments/${id}`, data),
  deleteDepartment: (id: string, data?: Record<string, unknown>) => client.delete(`/api/masterdata/departments/${id}`, { data }),
  // Teams
  teams: () => client.get('/api/masterdata/teams'),
  team: (id: string) => client.get(`/api/masterdata/teams/${id}`),
  createTeam: (data: Record<string, unknown>) => client.post('/api/masterdata/teams', data),
  updateTeam: (id: string, data: Record<string, unknown>) => client.post(`/api/masterdata/teams/${id}`, data),
  deleteTeam: (id: string, data?: Record<string, unknown>) => client.delete(`/api/masterdata/teams/${id}`, { data }),
}

// ── Dashboard Statistics API ──
export const dashboardApi = {
  stats: () => client.get('/api/dashboard'),
  sessions: () => client.get('/api/login-sessions'),
}

// ── Payroll JP API ──
export const payrollJpApi = {
  // Item Definitions
  itemDefinitions: (params?: Record<string, any>) => client.get('/api/payroll/jp/item-definitions', { params }),
  saveItemDefinition: (data: Record<string, any>) => client.post('/api/payroll/jp/item-definitions', data),
  // Parameters
  parameters: (params?: Record<string, any>) => client.get('/api/payroll/jp/parameters', { params }),
  saveParameter: (data: Record<string, any>) => client.post('/api/payroll/jp/parameters', data),
  // Rate Type Labels (data dictionary)
  rateTypeLabels: (params?: Record<string, any>) => client.get('/api/payroll/jp/rate-type-labels', { params }),
  // Master Data (from PostgreSQL md_* tables, replaces JSON file storage)
  entities: () => client.get('/api/payroll/jp/entities'),
  departments: () => client.get('/api/payroll/jp/departments'),
  teams: () => client.get('/api/payroll/jp/teams'),
  // Employees (Salary Master)
  employees: (params?: Record<string, any>) => client.get('/api/payroll/jp/employees', { params }),
  saveEmployee: (data: Record<string, any>) => client.post('/api/payroll/jp/employees', data),
  getEmployee: (id: string) => client.get(`/api/payroll/jp/employees/${id}`),
  deactivateEmployee: (id: string, data: Record<string, any>) => client.post(`/api/payroll/jp/employees/${id}/deactivate`, data),
  activateEmployee: (id: string) => client.post(`/api/payroll/jp/employees/${id}/activate`),
  calcPreview: (id: string, params?: Record<string, any>) => client.get(`/api/payroll/jp/employees/${id}/calc-preview`, { params }),
  importableEmployees: (params?: Record<string, any>) => client.get('/api/payroll/jp/employees/importable', { params }),
  importEmployees: (data: { employee_ids: string[] }) => client.post('/api/payroll/jp/employees/import', data),
  // Batches (Monthly Sheets)
  batches: (params?: Record<string, any>) => client.get('/api/payroll/jp/batches', { params }),
  getBatch: (id: string) => client.get(`/api/payroll/jp/batches/${id}`),
  createBatch: (data: Record<string, any>) => client.post('/api/payroll/jp/batches', data),
  calculateBatch: (batchId: string) => client.post(`/api/payroll/jp/batches/${batchId}/calculate`, {}),
  // Sheet operations
  sheets: (params?: Record<string, any>) => client.get('/api/payroll/jp/sheets', { params }),
  getSheet: (sheetId: string) => client.get(`/api/payroll/jp/sheets/${sheetId}`),
  confirmSheet: (batchId: string) => client.post(`/api/payroll/jp/batches/${batchId}/confirm`, {}),
  voidSheet: (batchId: string, data: { reason: string }) => client.post(`/api/payroll/jp/batches/${batchId}/void`, data),
  deleteSheet: (batchId: string) => client.delete(`/api/payroll/jp/batches/${batchId}`),
  importEmployeesToSheet: (sheetId: string, data: { employee_ids: string[] }) => client.post(`/api/payroll/jp/sheets/${sheetId}/import-employees`, data),
  saveSheetRecords: (sheetId: string, data: { records: any[] }) => client.post(`/api/payroll/jp/sheets/${sheetId}/records/bulk-save`, data),
  // Payslips
  payslips: (params?: Record<string, any>) => client.get('/api/payroll/jp/payslips', { params }),
  viewPayslipHtml: (recordId: string) => client.get(`/api/payroll/jp/payslips/${recordId}/html`),
  sendSinglePayslip: (recordId: string) => client.post(`/api/payroll/jp/payslips/${recordId}/send`, {}),
  // ── Workflow: Recalculate / Edit / Rollback / Audit ──
  recalculateSingleRecord: (batchId: string, recordId: string) => client.post(`/api/payroll/jp/batches/${batchId}/records/${recordId}/recalculate`, {}),
  editRecord: (batchId: string, recordId: string, data: Record<string, any>) => client.put(`/api/payroll/jp/batches/${batchId}/records/${recordId}`, data),
  rollbackBatch: (batchId: string, data: { reason: string }) => client.post(`/api/payroll/jp/batches/${batchId}/rollback`, data),
  getBatchAuditLogs: (batchId: string) => client.get(`/api/payroll/jp/batches/${batchId}/audit-logs`),
  auditLogs: (params?: Record<string, any>) => client.get('/api/payroll/jp/audit-logs', { params }),
  getSmtpStatus: () => client.get('/api/payroll/jp/smtp-status'),
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
