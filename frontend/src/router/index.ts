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
        path: 'employees/:id',
        name: 'EmployeeDetail',
        component: () => import('@/modules/employees/EmployeeDetail.vue'),
        meta: { requiresAuth: true, permission: 'employee_management.access', titleKey: 'employees.detail' },
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

export default router
