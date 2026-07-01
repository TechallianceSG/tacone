<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usersApi } from '@/api/client'
import type { UserInfo } from '@/types'
import { ElMessageBox } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const userId = route.params.id as string
const user = ref<UserInfo | null>(null)
const roles = ref<string[]>([])
const loading = ref(true)
const error = ref('')
const deactivating = ref(false)

const statusTagType = (status?: string): 'success' | 'info' | 'danger' | 'warning' | '' => {
  const map: Record<string, 'success' | 'info' | 'danger' | 'warning'> = {
    active: 'success',
    inactive: 'info',
    locked: 'danger',
    suspended: 'warning',
  }
  return map[status || ''] || 'info'
}

onMounted(async () => {
  loading.value = true
  try {
    const response = await usersApi.get(userId)
    user.value = response.data?.user as UserInfo
    roles.value = (response.data?.roles || []) as string[]
  } catch (e: any) {
    error.value = e?.message || 'User not found'
  } finally {
    loading.value = false
  }
})

async function handleDeactivate() {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate_entity'),
      t('confirm.title'),
      { confirmButtonText: t('confirm.ok'), cancelButtonText: t('confirm.cancel'), type: 'warning' }
    )
  } catch {
    return
  }

  deactivating.value = true
  try {
    await usersApi.deactivate(userId)
    router.push('/users')
  } catch (e: any) {
    error.value = e?.message || 'Failed to deactivate'
  } finally {
    deactivating.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>{{ user?.display_name || user?.username || userId }}</h1>
        <p class="subtitle">{{ user?.email }}</p>
      </div>
      <el-button @click="router.push('/users')">{{ t('action.back') }}</el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" style="text-align: center; padding: 60px">
      <el-icon class="is-loading" :size="32"><span /></el-icon>
    </div>

    <!-- Error -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon style="margin-bottom: 16px" />

    <!-- User Detail -->
    <template v-else-if="user">
      <el-card shadow="never" style="margin-bottom: 20px">
        <template #header>
          <span>{{ t('users.detail') }}</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('field.user_id')">
            <code>{{ user.user_id }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.username')">
            {{ user.username }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.display_name')">
            {{ user.display_name }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.email')">
            {{ user.email }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.user_type')">
            {{ user.user_type }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.status')">
            <el-tag :type="statusTagType(user.status)" size="small">{{ user.status || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.roles')" :span="2">
            {{ roles.join(', ') || '-' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.linked_employee')">
            {{ user.employee_name || user.employee_no || '-' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.department')">
            {{ user.department_name || user.department || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Actions -->
      <div v-if="user.status === 'active'" class="actions">
        <el-button type="danger" :loading="deactivating" @click="handleDeactivate">
          {{ t('action.deactivate') }}
        </el-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}
.subtitle {
  color: var(--el-text-color-secondary);
  margin: 4px 0 0;
}
.actions {
  display: flex;
  gap: 12px;
}
</style>
