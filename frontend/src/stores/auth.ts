import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, publicApi } from '@/api/client'
import type { UserInfo, SessionInfo } from '@/types'

const BYPASS_AUTH = import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'

const MOCK_USER: UserInfo = {
  user_id: 'USR-0001',
  username: 'admin',
  display_name: 'Dev Admin',
  email: 'admin@tacai.local',
  user_type: 'admin',
  language_preference: 'en',
  roles: ['system_admin'],
  permissions: [
    'user_management.access', 'user_management.manage_users',
    'user_management.manage_roles', 'user_management.manage_permissions',
    'user_management.audit.view', 'masterdata.access', 'masterdata.view',
    'masterdata.maintain', 'masterdata.admin', 'employee_management.access',
    'employee_management.view', 'employee_management.edit',
    'timesheet.access', 'payroll.access', 'payroll.view',
    'tacaipay_sg.access', 'tacaipay_sg.view', 'tacaipay_sg.manage',
    'tacaipay_jp.access', 'tacaipay_jp.view', 'tacaipay_jp.manage',
    'tacaipay_cn.access', 'tacaipay_cn.view', 'tacaipay_cn.manage',
    'invoice.access', 'invoice.view', 'invoice.maintain', 'invoice.approve',
  ],
  entity: {
    entity_id: 'ENT-0003',
    entity_code: 'TAKK',
    entity_name_en: 'Tech Alliance Co., Ltd.',
    entity_name_ja: 'Tech Alliance株式会社',
    entity_name_zh: 'Tech Alliance株式会社',
  },
  entity_id: 'ENT-0003',
  entity_code: 'TAKK',
  entity_name: 'Tech Alliance Co., Ltd.',
  employee_id: '',
  employee_no: '',
  employee_number: '',
  employee_name: 'Dev Admin',
  department: 'System',
  linked_employee_id: '',
  department_id: null as any,
  department_code: null as any,
  department_name: null as any,
  employee_context: {},
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const session = ref<SessionInfo | null>(null)
  const loading = ref(false)
  const error = ref('')
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isSystemAdmin = computed(() => user.value?.roles?.includes('system_admin') ?? false)
  const currentEntity = computed(() => user.value?.entity || null)
  const currentEntityLabel = computed(() => {
    const e = currentEntity.value
    if (!e) return ''
    const code = e.entity_code || ''
    const name = e.entity_name_en || ''
    return name ? `${code} - ${name}` : code
  })

  async function init(): Promise<boolean> {
    if (initialized.value) return isAuthenticated.value

    // ── Dev bypass: skip API, auto-authenticate ──
    if (BYPASS_AUTH) {
      user.value = { ...MOCK_USER }
      session.value = { session_id: 'dev-bypass', login_time: new Date().toISOString() }
      initialized.value = true
      console.log('[DEV] Auth bypass enabled — logged in as', MOCK_USER.email)
      return true
    }

    loading.value = true
    try {
      const response = await authApi.validateSession()
      if (response.data?.valid && response.data?.user) {
        user.value = response.data.user
        session.value = response.data.session || null
      }
    } catch {
      // Not authenticated — that's fine
    } finally {
      loading.value = false
      initialized.value = true
    }
    return isAuthenticated.value
  }

  async function login(email: string, password: string, entityCode: string): Promise<boolean> {
    // ── Dev bypass: always succeed ──
    if (BYPASS_AUTH) {
      user.value = { ...MOCK_USER, email: email || MOCK_USER.email, entity_code: entityCode || MOCK_USER.entity_code }
      session.value = { session_id: 'dev-bypass', login_time: new Date().toISOString() }
      initialized.value = true
      console.log('[DEV] Auth bypass — login skipped for', email || MOCK_USER.email)
      return true
    }

    loading.value = true
    error.value = ''
    try {
      const response = await authApi.login(email, password, entityCode)
      if (response.data?.authenticated) {
        user.value = response.data.user
        session.value = response.data.session || null
        return true
      }
      error.value = response.data?.message || 'Invalid login'
      return false
    } catch (err: any) {
      error.value = err?.response?.data?.message || err?.message || 'Invalid login'
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    if (BYPASS_AUTH) {
      user.value = null
      session.value = null
      return
    }
    try {
      await authApi.logout()
    } catch {
      // Logout best-effort
    } finally {
      user.value = null
      session.value = null
    }
  }

  return {
    user, session, loading, error, initialized,
    isAuthenticated, isSystemAdmin, currentEntity, currentEntityLabel,
    init, login, logout,
  }
})
