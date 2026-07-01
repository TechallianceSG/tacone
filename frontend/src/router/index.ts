import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/modules/auth/Login.vue'),
    meta: { guest: true },
  },
  // ── Dashboard (standalone — simple two-card entry) ──
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/modules/portal/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  // ── AppLayout wrapper for all internal pages ──
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      // ── Root → Dashboard redirect ──
      {
        path: '',
        redirect: '/dashboard',
      },
      // ── User Management ──
      {
        path: 'users',
        name: 'UserList',
        component: () => import('@/modules/users/UserList.vue'),
        meta: { requiresAuth: true, permission: 'user_management.manage_users', titleKey: 'nav.users' },
      },
      {
        path: 'users/new',
        name: 'UserCreate',
        component: () => import('@/modules/users/UserForm.vue'),
        meta: { requiresAuth: true, permission: 'user_management.manage_users', titleKey: 'users.create' },
      },
      {
        path: 'users/:id',
        name: 'UserDetail',
        component: () => import('@/modules/users/UserDetail.vue'),
        meta: { requiresAuth: true, permission: 'user_management.manage_users', titleKey: 'users.detail' },
      },
      // ── Employee Management ──
      {
        path: 'employees',
        name: 'EmployeeList',
        component: () => import('@/modules/employees/EmployeeList.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.access', titleKey: 'nav.employees' },
      },
      {
        path: 'employees/new',
        name: 'EmployeeCreate',
        component: () => import('@/modules/employees/EmployeeForm.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.create' },
      },
      {
        path: 'employees/import',
        name: 'EmployeeImport',
        component: () => import('@/modules/employees/EmployeeImport.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.import' },
      },
      {
        path: 'employees/:id/edit',
        name: 'EmployeeEdit',
        component: () => import('@/modules/employees/EmployeeDetail.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.edit' },
      },
      {
        path: 'employees/:id',
        name: 'EmployeeDetail',
        component: () => import('@/modules/employees/EmployeeDetail.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.access', titleKey: 'employees.detail' },
      },
      // ── Payroll ──
      {
        path: 'payroll',
        name: 'PayrollLanding',
        component: () => import('@/modules/payroll/PayrollLanding.vue'),
        meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'nav.payroll' },
      },
      // SG Payroll
      {
        path: 'payroll/sg/salary-master',
        name: 'SgSalaryMaster',
        component: () => import('@/modules/payroll/sg/SalaryMaster.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_sg.view', titleKey: 'payroll.sg.salary_master' },
      },
      {
        path: 'payroll/sg/batches',
        name: 'SgPayrollBatches',
        component: () => import('@/modules/payroll/sg/PayrollBatches.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_sg.view', titleKey: 'payroll.sg.batches' },
      },
      {
        path: 'payroll/sg/batches/:id',
        name: 'SgPayrollBatchDetail',
        component: () => import('@/modules/payroll/sg/PayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_sg.view', titleKey: 'payroll.sg.batch_detail' },
      },
      {
        path: 'payroll/sg/payslips',
        name: 'SgPayslips',
        component: () => import('@/modules/payroll/sg/Payslips.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_sg.view', titleKey: 'payroll.sg.payslips' },
      },
      // JP Payroll
      {
        path: 'payroll/jp/item-definitions',
        name: 'JpItemDefinitions',
        component: () => import('@/modules/payroll/jp/ItemDefinitions.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.item_definitions' },
      },
      {
        path: 'payroll/jp/parameters',
        name: 'JpPayrollParameters',
        component: () => import('@/modules/payroll/jp/PayrollParameters.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.parameters' },
      },
      {
        path: 'payroll/jp/employees',
        name: 'JpEmployees',
        component: () => import('@/modules/payroll/jp/JpEmployees.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.employees' },
      },
      {
        path: 'payroll/jp/batches',
        name: 'JpPayrollBatches',
        component: () => import('@/modules/payroll/jp/JpPayrollBatches.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.batches' },
      },
      {
        path: 'payroll/jp/batches/:id',
        name: 'JpPayrollBatchDetail',
        component: () => import('@/modules/payroll/jp/JpPayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.batch_detail' },
      },
      {
        path: 'payroll/jp/payslips',
        name: 'JpPayslips',
        component: () => import('@/modules/payroll/jp/JpPayslips.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.payslips' },
      },
      // CN Payroll
      {
        path: 'payroll/cn/social-insurance-rules',
        name: 'CnSIRules',
        component: () => import('@/modules/payroll/cn/SocialInsuranceRules.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.rules' },
      },
      {
        path: 'payroll/cn/tax-brackets',
        name: 'CnTaxBrackets',
        component: () => import('@/modules/payroll/cn/TaxBrackets.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.tax_brackets' },
      },
      {
        path: 'payroll/cn/employees',
        name: 'CnEmployees',
        component: () => import('@/modules/payroll/cn/CnEmployees.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.employees' },
      },
      {
        path: 'payroll/cn/batches',
        name: 'CnPayrollBatches',
        component: () => import('@/modules/payroll/cn/CnPayrollBatches.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.batches' },
      },
      {
        path: 'payroll/cn/batches/:id',
        name: 'CnPayrollBatchDetail',
        component: () => import('@/modules/payroll/cn/CnPayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.batch_detail' },
      },
      {
        path: 'payroll/cn/payslips',
        name: 'CnPayslips',
        component: () => import('@/modules/payroll/cn/CnPayslips.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.payslips' },
      },
      // ── Invoice Management ──
      {
        path: 'invoice',
        name: 'InvoiceLanding',
        component: () => import('@/modules/invoice/InvoiceLanding.vue'),
        meta: { requiresAuth: true, permission: 'invoice.access', titleKey: 'nav.invoice' },
      },
      {
        path: 'invoice/projects',
        name: 'CustomerProjects',
        component: () => import('@/modules/invoice/CustomerProjects.vue'),
        meta: { requiresAuth: true, permission: 'invoice.maintain', titleKey: 'invoice.projects' },
      },
      {
        path: 'invoice/pending',
        name: 'PendingInvoices',
        component: () => import('@/modules/invoice/PendingInvoices.vue'),
        meta: { requiresAuth: true, permission: 'invoice.maintain', titleKey: 'invoice.pending' },
      },
      {
        path: 'invoice/invoices',
        name: 'InvoiceList',
        component: () => import('@/modules/invoice/InvoiceList.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.list' },
      },
      {
        path: 'invoice/invoices/:id',
        name: 'InvoiceDetail',
        component: () => import('@/modules/invoice/InvoiceDetail.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.detail' },
      },
      {
        path: 'invoice/overdue',
        name: 'OverdueInvoices',
        component: () => import('@/modules/invoice/OverdueInvoices.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.overdue' },
      },
    ],
  },
  // ── Catch-all: redirect to Dashboard ──
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ── Navigation guard ──
router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()

  // Initialize auth state on first navigation
  if (!auth.initialized) {
    await auth.init()
  }

  // Guest-only routes (login) — redirect authenticated users to dashboard
  if (to.meta.guest && auth.isAuthenticated) {
    next('/dashboard')
    return
  }

  // Auth-required routes — redirect unauthenticated users to login
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // Permission check
  if (to.meta.permission && auth.user) {
    const perms = auth.user.permissions || []
    const roles = auth.user.roles || []
    if (!perms.includes(to.meta.permission as string) && !roles.includes('system_admin')) {
      next('/dashboard')
      return
    }
  }

  next()
})

// ── Session expiry handler (SPA navigation, no hard reload) ──
window.addEventListener('tacai:session-expired', async () => {
  const auth = useAuthStore()
  await auth.logout()
  // Only redirect if not already on the login page
  if (window.location.pathname !== '/login') {
    router.push('/login')
  }
})

export default router
