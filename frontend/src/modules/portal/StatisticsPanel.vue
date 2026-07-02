<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { dashboardApi } from '@/api/client'
import { UserFilled, Clock, WarningFilled } from '@element-plus/icons-vue'

const { t } = useI18n()
const auth = useAuthStore()

interface DashboardStats {
  total_users?: number
  active_users?: number
  locked_users?: number
  active_sessions?: number
}

const stats = ref<DashboardStats | null>(null)

const isAdmin = computed(() => {
  const roles = auth.user?.roles || []
  const perms = auth.user?.permissions || []
  return roles.includes('system_admin') || perms.includes('user_management.audit.view')
})

async function loadStats() {
  if (!isAdmin.value) return
  try {
    const { data } = await dashboardApi.stats()
    stats.value = data
  } catch {
    stats.value = null
  }
}

onMounted(() => {
  loadStats()
})
</script>

<template>
  <div v-if="isAdmin && stats" class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-icon" style="background:var(--el-color-primary-light-9);color:var(--el-color-primary)">
        <el-icon :size="18"><UserFilled /></el-icon>
      </div>
      <div class="kpi-info">
        <span class="kpi-value">{{ stats.total_users ?? '—' }}</span>
        <span class="kpi-label">{{ t('dashboard.stats_total_users') }}</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon" style="background:var(--el-color-success-light-9);color:var(--el-color-success)">
        <el-icon :size="18"><UserFilled /></el-icon>
      </div>
      <div class="kpi-info">
        <span class="kpi-value">{{ stats.active_users ?? '—' }}</span>
        <span class="kpi-label">{{ t('dashboard.active_users') }}</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon" style="background:var(--el-color-danger-light-9);color:var(--el-color-danger)">
        <el-icon :size="18"><WarningFilled /></el-icon>
      </div>
      <div class="kpi-info">
        <span class="kpi-value">{{ stats.locked_users ?? '—' }}</span>
        <span class="kpi-label">{{ t('dashboard.locked_users') }}</span>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon" style="background:var(--el-color-warning-light-9);color:var(--el-color-warning)">
        <el-icon :size="18"><Clock /></el-icon>
      </div>
      <div class="kpi-info">
        <span class="kpi-value">{{ stats.active_sessions ?? '—' }}</span>
        <span class="kpi-label">{{ t('dashboard.active_sessions') }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 280px);
  gap: 24px;
  justify-content: center;
  margin-bottom: 32px;
}
.kpi-card {
  width: 280px;
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  box-sizing: border-box;
}
.kpi-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kpi-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.kpi-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.3;
}
.kpi-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  line-height: 1.3;
}
</style>
