<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { useI18n } from 'vue-i18n'
import type { SupportedLang } from '@/types'
import type { DashboardModule } from '@/modules/portal/types'
import {
  UserFilled,
  Avatar,
  Money,
  Document,
  Collection,
  Clock,
  Tickets,
  Wallet,
  Coin,
  ChatDotRound,
} from '@element-plus/icons-vue'
import ModuleCard from '@/components/ModuleCard.vue'

const router = useRouter()
const auth = useAuthStore()
const i18nStore = useI18nStore()
const { t } = useI18n()

const languages: { code: SupportedLang; label: string }[] = [
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
]

const currentEntityLabel = computed(() => auth.currentEntityLabel)

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

// ── Module definitions ──
const allModules: DashboardModule[] = [
  {
    key: 'employee_management',
    icon: UserFilled,
    titleKey: 'module.employee_management',
    descKey: 'dashboard.employee_desc',
    route: '/employees',
    color: 'employee',
    status: 'active',
    permission: 'employee_management.access',
    actionKey: 'action.manage_employees',
  },
  {
    key: 'user_management',
    icon: Avatar,
    titleKey: 'module.user_management',
    descKey: 'dashboard.user_desc',
    route: '/users',
    color: 'user',
    status: 'active',
    permission: 'user_management.manage_users',
    actionKey: 'action.open',
  },
  {
    key: 'payroll',
    icon: Money,
    titleKey: 'module.payroll',
    descKey: 'dashboard.payroll_desc',
    route: '/payroll',
    color: 'payroll',
    status: 'active',
    permission: 'payroll.access',
    actionKey: 'action.open',
  },
  {
    key: 'invoice',
    icon: Document,
    titleKey: 'module.invoice',
    descKey: 'dashboard.invoice_desc',
    route: '/invoice',
    color: 'invoice',
    status: 'active',
    permission: 'invoice.access',
    actionKey: 'action.open',
  },
  {
    key: 'masterdata',
    icon: Collection,
    titleKey: 'module.masterdata',
    descKey: 'dashboard.organization_desc',
    route: '/employees',
    color: 'masterdata',
    status: 'active',
    actionKey: 'action.open_master',
  },
  {
    key: 'timesheet',
    icon: Clock,
    titleKey: 'module.timesheet',
    descKey: 'dashboard.timesheet_desc',
    route: '#',
    color: 'timesheet',
    status: 'planned',
    actionKey: 'common.coming_soon',
  },
  {
    key: 'customerbilling',
    icon: Tickets,
    titleKey: 'module.customerbilling',
    descKey: 'dashboard.customers.description',
    route: '#',
    color: 'customer',
    status: 'planned',
    actionKey: 'common.coming_soon',
  },
  {
    key: 'vendor_payables',
    icon: Wallet,
    titleKey: 'module.vendor_payables',
    descKey: 'dashboard.vendors.description',
    route: '#',
    color: 'vendor',
    status: 'planned',
    actionKey: 'common.coming_soon',
  },
  {
    key: 'reimbursement',
    icon: Coin,
    titleKey: 'module.reimbursement',
    descKey: 'dashboard.reimbursement_desc',
    route: '#',
    color: 'reimbursement',
    status: 'planned',
    actionKey: 'common.coming_soon',
  },
  {
    key: 'interview_ready',
    icon: ChatDotRound,
    titleKey: 'module.interview_ready',
    descKey: 'dashboard.interview_ready_desc',
    route: '#',
    color: 'interview',
    status: 'planned',
    actionKey: 'common.coming_soon',
  },
]

const userPerms = computed<string[]>(() => auth.user?.permissions || [])
const userRoles = computed<string[]>(() => auth.user?.roles || [])

const visibleModules = computed<DashboardModule[]>(() => {
  const isSysAdmin = userRoles.value.includes('system_admin')
  if (isSysAdmin) return allModules
  return allModules.filter(
    (m) => !m.permission || userPerms.value.includes(m.permission)
  )
})
</script>

<template>
  <div class="dashboard-shell">
    <!-- ═══════ Top Bar ═══════ -->
    <header class="dashboard-topbar">
      <div class="topbar-left">
        <h1 class="app-title">{{ t('app.title') }}</h1>
      </div>
      <div class="topbar-right">
        <!-- Language switcher -->
        <div class="lang-switcher">
          <el-button
            v-for="lang in languages"
            :key="lang.code"
            :type="i18nStore.locale === lang.code ? 'primary' : 'default'"
            size="small"
            text
            @click="i18nStore.setLocale(lang.code)"
          >{{ lang.label }}</el-button>
        </div>

        <!-- Entity -->
        <el-tag v-if="currentEntityLabel" type="info" size="small">{{ currentEntityLabel }}</el-tag>

        <!-- User info -->
        <el-dropdown v-if="auth.user" trigger="click">
          <span class="user-chip">
            <el-icon><Avatar /></el-icon>
            <span>{{ auth.user.display_name || auth.user.username }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <small>{{ auth.user.email }}</small>
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                {{ t('nav.logout') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- ═══════ Main Content ═══════ -->
    <main class="dashboard-main">
      <div class="dashboard-hero">
        <h2>{{ t('dashboard.welcome') }}</h2>
        <p>{{ t('dashboard.description') }}</p>
      </div>

      <!-- Empty state -->
      <div v-if="visibleModules.length === 0" class="empty-state">
        <p>{{ t('dashboard.empty') }}</p>
      </div>

      <!-- Module Cards Grid -->
      <div v-else class="module-cards">
        <ModuleCard
          v-for="mod in visibleModules"
          :key="mod.key"
          :module="mod"
        />
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard-shell {
  min-height: 100vh;
  background: var(--el-bg-color-page, #f5f7fa);
}

.dashboard-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 60px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.topbar-left .app-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--el-color-primary);
  margin: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lang-switcher {
  display: flex;
  gap: 4px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
}
.user-chip:hover {
  background: var(--el-fill-color-light);
}

/* ── Main ── */
.dashboard-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 48px 24px;
}

.dashboard-hero {
  text-align: center;
  margin-bottom: 48px;
}
.dashboard-hero h2 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}
.dashboard-hero p {
  color: var(--el-text-color-secondary);
  font-size: 1rem;
  max-width: 600px;
  margin: 0 auto;
}

/* ── Grid ── */
.module-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, 280px);
  gap: 24px;
  justify-content: center;
}

/* ── Empty state ── */
.empty-state {
  text-align: center;
  padding: 64px 24px;
  color: var(--el-text-color-secondary);
  font-size: 1rem;
}

/* ── Responsive: single column on narrow screens ── */
@media (max-width: 640px) {
  .dashboard-main {
    padding: 32px 16px;
  }
  .module-cards {
    grid-template-columns: 1fr;
    justify-items: center;
  }
}
</style>
