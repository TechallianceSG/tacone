<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { useI18n } from 'vue-i18n'
import type { SupportedLang } from '@/types'
import { Avatar } from '@element-plus/icons-vue'

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

interface BreadcrumbItem {
  label: string
  path: string
}

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = []

  // Always start with Dashboard
  items.push({ label: t('nav.dashboard'), path: '/dashboard' })

  // Walk up from current route via meta.parent to build ancestor chain
  const chain: Array<{ name: string | symbol | undefined; meta: any; params: any }> = []
  let current: any = route

  while (current) {
    chain.unshift({ name: current.name, meta: current.meta, params: current.params })
    const parentName = (current.meta as any)?.parent as string | undefined
    if (parentName) {
      try {
        current = router.resolve({ name: parentName })
      } catch {
        break
      }
    } else {
      break
    }
  }

  // Add all chain items (last one = current page, rendered as non-clickable)
  for (const r of chain) {
    const meta = r.meta as any
    const label = meta.titleKey ? t(meta.titleKey) : (meta.title || String(r.name || ''))
    let path = '#'
    try {
      path = router.resolve({ name: r.name as string, params: r.params }).path
    } catch {
      path = '/dashboard'
    }
    items.push({ label, path })
  }

  return items
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
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <template v-for="(item, index) in breadcrumbs" :key="index">
            <span v-if="index > 0" class="breadcrumb-sep">›</span>
            <router-link
              v-if="index < breadcrumbs.length - 1"
              :to="item.path"
              class="breadcrumb-link"
            >
              {{ item.label }}
            </router-link>
            <span v-else class="breadcrumb-current">{{ item.label }}</span>
          </template>
        </nav>
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

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.92rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.breadcrumb-sep {
  color: #9ca3af;
  font-size: 1rem;
  user-select: none;
}

.breadcrumb-link {
  color: #1B6CB2;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s;
}
.breadcrumb-link:hover {
  color: #0f5090;
  text-decoration: underline;
}

.breadcrumb-current {
  font-weight: 700;
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
  min-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 20px;
}
</style>
