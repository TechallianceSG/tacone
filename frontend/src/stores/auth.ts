import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, publicApi } from '@/api/client'
import type { UserInfo, SessionInfo } from '@/types'

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
    user,
    session,
    loading,
    error,
    initialized,
    isAuthenticated,
    isSystemAdmin,
    currentEntity,
    currentEntityLabel,
    init,
    login,
    logout,
  }
})
