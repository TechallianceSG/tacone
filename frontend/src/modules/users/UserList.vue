<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usersApi } from '@/api/client'
import { Plus, Search } from '@element-plus/icons-vue'

interface User {
  user_id: string
  username: string
  display_name: string
  email: string
  user_type: string
  status: string
  last_login: string
  linked_employee_no: string
  linked_employee_name: string
  linked_entity_code: string
}

const { t } = useI18n()
const router = useRouter()

const users = ref<User[]>([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const statusFilter = ref('')

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const statusTagType = (status: string): 'success' | 'info' | 'danger' | 'warning' | '' => {
  const map: Record<string, 'success' | 'info' | 'danger' | 'warning'> = {
    active: 'success',
    inactive: 'info',
    locked: 'danger',
    suspended: 'warning',
  }
  return map[status] || 'info'
}

async function loadUsers() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (searchQuery.value.trim()) params.q = searchQuery.value.trim()
    if (statusFilter.value) params.status = statusFilter.value
    const response = await usersApi.list(params)
    const data = response.data
    users.value = (data?.users || []) as User[]
    total.value = data?.pagination?.total || data?.users?.length || 0
  } catch (e: any) {
    error.value = e?.message || 'Failed to load users'
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadUsers()
}

function handlePageChange(p: number) {
  page.value = p
  loadUsers()
}

function handleSizeChange(s: number) {
  pageSize.value = s
  page.value = 1
  loadUsers()
}

function viewUser(id: string) {
  router.push(`/users/${id}`)
}

function createUser() {
  router.push('/users/new')
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div class="page">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1>{{ t('users.title') }}</h1>
      </div>
      <el-button type="primary" @click="createUser">
        <el-icon><Plus /></el-icon>{{ t('users.create') }}
      </el-button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        :placeholder="t('action.search') + '...'"
        clearable
        style="width: 240px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select v-model="statusFilter" clearable :placeholder="t('field.status')" style="width: 140px" @change="handleSearch">
        <el-option :label="t('status.active')" value="active" />
        <el-option :label="t('status.inactive')" value="inactive" />
        <el-option :label="t('status.locked')" value="locked" />
        <el-option :label="t('status.suspended')" value="suspended" />
      </el-select>
    </div>

    <!-- Error -->
    <el-alert v-if="error" :title="error" type="error" show-icon closable @close="error = ''" style="margin-bottom: 16px" />

    <!-- Table -->
    <el-card shadow="never">
      <el-table :data="users" v-loading="loading" stripe border style="width: 100%" @row-click="(row: User) => viewUser(row.user_id)">
        <el-table-column prop="user_id" :label="t('field.user_id')" width="150" />
        <el-table-column prop="username" :label="t('field.username')" min-width="140" />
        <el-table-column prop="display_name" :label="t('field.display_name')" min-width="140" />
        <el-table-column prop="email" :label="t('field.email')" min-width="200" />
        <el-table-column prop="user_type" :label="t('field.user_type')" width="110" />
        <el-table-column :label="t('field.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" :label="t('field.last_login')" min-width="160">
          <template #default="{ row }">{{ row.last_login || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewUser(row.user_id)">{{ t('action.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 16px">
        <span class="muted">{{ total }} {{ t('common.records_total', { total }) }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          small
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  max-width: 100%;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
</style>
