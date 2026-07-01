<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { useI18n } from 'vue-i18n'
import type { SupportedLang } from '@/types'
import { UserFilled, Avatar } from '@element-plus/icons-vue'

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

      <!-- Module Cards -->
      <el-row :gutter="24" class="module-cards">
        <!-- Employee Management -->
        <el-col :xs="24" :sm="12">
          <el-card class="module-card" shadow="hover" @click="router.push('/employees')">
            <div class="card-icon employee-icon">
              <el-icon :size="48"><UserFilled /></el-icon>
            </div>
            <h3>{{ t('nav.employees') }}</h3>
            <p>{{ t('dashboard.employee_desc') }}</p>
            <el-button type="primary" size="large" @click.stop="router.push('/employees')">
              {{ t('action.manage_employees') }}
            </el-button>
          </el-card>
        </el-col>

        <!-- User Management -->
        <el-col :xs="24" :sm="12">
          <el-card class="module-card" shadow="hover" @click="router.push('/users')">
            <div class="card-icon user-icon">
              <el-icon :size="48"><Avatar /></el-icon>
            </div>
            <h3>{{ t('nav.users') }}</h3>
            <p>{{ t('dashboard.user_desc') }}</p>
            <el-button type="primary" size="large" @click.stop="router.push('/users')">
              {{ t('action.open') }}
            </el-button>
          </el-card>
        </el-col>
      </el-row>
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

.dashboard-main {
  max-width: 960px;
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

.module-cards {
  justify-content: center;
}

.module-card {
  text-align: center;
  padding: 32px 16px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border-radius: 12px;
}
.module-card:hover {
  transform: translateY(-4px);
}

.card-icon {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.employee-icon {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.user-icon {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.module-card h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--el-text-color-primary);
}
.module-card p {
  color: var(--el-text-color-secondary);
  margin: 0 0 20px;
  line-height: 1.5;
}
</style>
