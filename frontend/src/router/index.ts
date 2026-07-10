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
        meta: { requiresAuth: true, permission: 'user_management.manage_users', titleKey: 'users.create', parent: 'UserList' },
      },
      {
        path: 'users/:id',
        name: 'UserDetail',
        component: () => import('@/modules/users/UserDetail.vue'),
        meta: { requiresAuth: true, permission: 'user_management.manage_users', titleKey: 'users.detail', parent: 'UserList' },
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
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.create', parent: 'EmployeeList' },
      },
      {
        path: 'employees/import',
        name: 'EmployeeImport',
        component: () => import('@/modules/employees/EmployeeImport.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.import', parent: 'EmployeeList' },
      },
      {
        path: 'employees/:id/edit',
        name: 'EmployeeEdit',
        component: () => import('@/modules/employees/EmployeeDetail.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.edit', titleKey: 'employees.edit', parent: 'EmployeeList' },
      },
      {
        path: 'employees/:id',
        name: 'EmployeeDetail',
        component: () => import('@/modules/employees/EmployeeDetail.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.access', titleKey: 'employees.detail', parent: 'EmployeeList' },
      },
      // ── Master Data Management ──
      {
        path: 'masterdata',
        name: 'MasterData',
        component: () => import('@/modules/masterdata/MasterDataLayout.vue'),
        meta: { requiresAuth: true, permission: 'masterdata.access', titleKey: 'nav.masterdata' },
      },
      // ── Data Dictionary ──
      {
        path: 'datadict',
        name: 'DataDictionary',
        component: () => import('@/modules/datadict/DataDictionaryList.vue'),
        meta: { requiresAuth: true, permission: 'datadict.access', titleKey: 'nav.datadict' },
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
        path: 'payroll/sg',
        name: 'SgPayrollLanding',
        component: () => import('@/modules/payroll/sg/SgLanding.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_sg.access', titleKey: 'payroll.sg.title', parent: 'PayrollLanding' },
      },
      {
        path: 'payroll/sg/item-definitions',
        name: 'SgItemDefinitions',
        component: () => import('@/modules/payroll/PayrollItemDefinitions.vue'),
        
        props: { countryCode: 'sg' },meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.jp.item_definitions', parent: 'SgPayrollLanding' },
      },
      {
        path: 'payroll/sg/employees',
        name: 'SgEmployees',
        component: () => import('@/modules/payroll/sg/SgEmployees.vue'),
        meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.sg.salary_master', parent: 'SgPayrollLanding' },
      },
      {
        path: 'payroll/sg/batches',
        name: 'SgPayrollBatches',
        component: () => import('@/modules/payroll/PayrollBatches.vue'),
        
        props: { countryCode: 'sg' },meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.sg.batches', parent: 'SgPayrollLanding' },
      },
      {
        path: 'payroll/sg/batches/:id',
        name: 'SgPayrollBatchDetail',
        component: () => import('@/modules/payroll/sg/SgPayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.sg.batch_detail', parent: 'SgPayrollBatches' },
      },
      {
        path: 'payroll/sg/payslips',
        name: 'SgPayslips',
        component: () => import('@/modules/payroll/PayrollPayslips.vue'),
        
        props: { countryCode: 'sg' },meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.sg.payslips', parent: 'SgPayrollLanding' },
      },
      {
        path: 'payroll/sg/email-settings',
        name: 'SgEmailSettings',
        component: () => import('@/modules/payroll/PayrollEmailSettings.vue'),
        
        props: { countryCode: 'sg' },meta: { requiresAuth: true, permission: 'payroll.access', titleKey: 'payroll.jp.email_settings', parent: 'SgPayrollLanding' },
      },
      // JP Payroll
      {
        path: 'payroll/jp',
        name: 'JpPayrollLanding',
        component: () => import('@/modules/payroll/jp/JpLanding.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.title', parent: 'PayrollLanding' },
      },
      // CN Payroll
      {
        path: 'payroll/cn',
        name: 'CnPayrollLanding',
        component: () => import('@/modules/payroll/cn/CnLanding.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.title', parent: 'PayrollLanding' },
      },
      {
        path: 'payroll/cn/item-definitions',
        name: 'CnItemDefinitions',
        component: () => import('@/modules/payroll/PayrollItemDefinitions.vue'),
        props: { countryCode: 'cn' },meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.item_definitions', parent: 'CnPayrollLanding' },
      },
      {
        path: 'payroll/cn/employees',
        name: 'CnEmployees',
        component: () => import('@/modules/payroll/cn/CnEmployees.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.employees', parent: 'CnPayrollLanding' },
      },
      {
        path: 'payroll/cn/batches',
        name: 'CnPayrollBatches',
        component: () => import('@/modules/payroll/PayrollBatches.vue'),
        props: { countryCode: 'cn' },meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.batches', parent: 'CnPayrollLanding' },
      },
      {
        path: 'payroll/cn/batches/:id',
        name: 'CnPayrollBatchDetail',
        component: () => import('@/modules/payroll/cn/CnPayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.batch_detail', parent: 'CnPayrollBatches' },
      },
      {
        path: 'payroll/cn/payslips',
        name: 'CnPayslips',
        component: () => import('@/modules/payroll/PayrollPayslips.vue'),
        props: { countryCode: 'cn' },meta: { requiresAuth: true, permission: 'tacaipay_cn.view', titleKey: 'payroll.cn.payslips', parent: 'CnPayrollLanding' },
      },
      {
        path: 'payroll/cn/email-settings',
        name: 'CnEmailSettings',
        component: () => import('@/modules/payroll/PayrollEmailSettings.vue'),
        props: { countryCode: 'cn' },meta: { requiresAuth: true, permission: 'tacaipay_cn.manage', titleKey: 'payroll.jp.email_settings', parent: 'CnPayrollLanding' },
      },
      {
        path: 'payroll/jp/item-definitions',
        name: 'JpItemDefinitions',
        component: () => import('@/modules/payroll/PayrollItemDefinitions.vue'),
        
        props: { countryCode: 'jp' },meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.item_definitions', parent: 'JpPayrollLanding' },
      },
      {
        path: 'payroll/jp/parameters',
        name: 'JpPayrollParameters',
        component: () => import('@/modules/payroll/jp/PayrollParameters.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.parameters', parent: 'JpPayrollLanding' },
      },
      {
        path: 'payroll/jp/employees',
        name: 'JpEmployees',
        component: () => import('@/modules/payroll/jp/JpEmployees.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.employees', parent: 'JpPayrollLanding' },
      },
      {
        path: 'payroll/jp/batches',
        name: 'JpPayrollBatches',
        component: () => import('@/modules/payroll/PayrollBatches.vue'),
        
        props: { countryCode: 'jp' },meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.batches', parent: 'JpPayrollLanding' },
      },
      {
        path: 'payroll/jp/batches/:id',
        name: 'JpPayrollBatchDetail',
        component: () => import('@/modules/payroll/jp/JpPayrollBatchDetail.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.batch_detail', parent: 'JpPayrollBatches' },
      },
      {
        path: 'payroll/jp/payslips',
        name: 'JpPayslips',
        component: () => import('@/modules/payroll/PayrollPayslips.vue'),
        
        props: { countryCode: 'jp' },meta: { requiresAuth: true, permission: 'tacaipay_jp.view', titleKey: 'payroll.jp.payslips', parent: 'JpPayrollLanding' },
      },
      {
        path: 'payroll/jp/email-settings',
        name: 'JpEmailSettings',
        component: () => import('@/modules/payroll/jp/JpEmailSettings.vue'),
        meta: { requiresAuth: true, permission: 'tacaipay_jp.manage', titleKey: 'payroll.jp.email_settings', parent: 'JpPayrollLanding' },
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
        meta: { requiresAuth: true, permission: 'invoice.maintain', titleKey: 'invoice.projects', parent: 'InvoiceLanding' },
      },
      {
        path: 'invoice/pending',
        name: 'PendingInvoices',
        component: () => import('@/modules/invoice/PendingInvoices.vue'),
        meta: { requiresAuth: true, permission: 'invoice.maintain', titleKey: 'invoice.pending', parent: 'InvoiceLanding' },
      },
      {
        path: 'invoice/invoices',
        name: 'InvoiceList',
        component: () => import('@/modules/invoice/InvoiceList.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.list', parent: 'InvoiceLanding' },
      },
      {
        path: 'invoice/invoices/:id',
        name: 'InvoiceDetail',
        component: () => import('@/modules/invoice/InvoiceDetail.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.detail', parent: 'InvoiceList' },
      },
      {
        path: 'invoice/overdue',
        name: 'OverdueInvoices',
        component: () => import('@/modules/invoice/OverdueInvoices.vue'),
        meta: { requiresAuth: true, permission: 'invoice.view', titleKey: 'invoice.overdue', parent: 'InvoiceLanding' },
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

// ⚠️ TEMPORARY: 跳过认证用于开发测试，测试完成后改 false 并删除 client.ts 对应 if 块
const SKIP_AUTH_FOR_DEV = true
if (typeof window !== 'undefined' && SKIP_AUTH_FOR_DEV) {
  sessionStorage.setItem('tacai_skip_auth', '1')
}

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()

  if (SKIP_AUTH_FOR_DEV) {
    if (!auth.user) {
      auth.$patch({
        user: {
          email: 'dev@test.com', display_name: 'Dev Test',
          permissions: ['tacaipay_cn.view','tacaipay_cn.manage','tacaipay_cn.calculate','tacaipay_cn.approve',
                        'tacaipay_jp.view','tacaipay_sg.view','payroll.access','system_admin'],
          roles: ['system_admin'],
        },
        initialized: true,
      } as any)
    }
    next()
    return
  }

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
  if (SKIP_AUTH_FOR_DEV) return
  const auth = useAuthStore()
  await auth.logout()
  // Only redirect if not already on the login page
  if (window.location.pathname !== '/login') {
    router.push('/login')
  }
})

export default router
