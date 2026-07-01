<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { useI18n } from 'vue-i18n'
import type { SupportedLang } from '@/types'
import { ArrowLeft, Avatar } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const i18nStore = useI18nStore()
const { t } = useI18n()

const languages: { code: SupportedLang; label: string }[] = [
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
]

const pageTitle = computed(() => {
  const meta = route.meta as { titleKey?: string; title?: string }
  if (meta.titleKey) return t(meta.titleKey)
  if (meta.title) return meta.title
  return String(route.name || '')
})

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <!-- ═══════ Unified Top Navigation Bar ═══════ -->
    <header class="unified-topbar">
      <div class="unified-topbar-left">
        <el-button text @click="router.push('/dashboard')">
          <el-icon><ArrowLeft /></el-icon>
          {{ t('back_dashboard') }}
        </el-button>
        <el-divider direction="vertical" />
        <span class="page-title">{{ pageTitle }}</span>
      </div>

      <div class="unified-topbar-right">
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

        <!-- User area -->
        <el-dropdown v-if="auth.user" trigger="click">
          <span class="user-area">
            <el-icon><Avatar /></el-icon>
            <span class="user-name">{{ auth.user.display_name || auth.user.username }}</span>
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

    <!-- ═══════ Page Content ═══════ -->
    <div class="unified-content">
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: var(--el-bg-color-page, #f5f7fa);
}

.unified-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  position: sticky;
  top: 0;
  z-index: 100;
}

.unified-topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.unified-topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lang-switcher {
  display: flex;
  gap: 2px;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
  transition: background 0.2s;
}
.user-area:hover {
  background: var(--el-fill-color-light);
}
.user-name {
  font-size: 0.9rem;
  font-weight: 500;
}

.unified-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}
</style>
