<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { employeeApi } from '@/api/client'

interface Employee {
  employee_id: string
  employee_number: string
  profile: Record<string, any>
  employment: Record<string, any>
  payroll: Record<string, any>
  visa: Record<string, any>
  dispatch_compliance: Record<string, any>
  language_profile: Record<string, any>
  skills_profile: Record<string, any>
  documents: any[]
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const employeeId = route.params.id as string
const employee = ref<Employee | null>(null)
const loading = ref(true)
const error = ref('')
const activeTab = ref('profile')

const tabs = [
  { key: 'profile', label: () => t('employee.section_profile') },
  { key: 'employment', label: () => t('employee.section_employment') },
  { key: 'payroll', label: () => t('employee.section_payroll') || 'Payroll' },
  { key: 'visa', label: () => t('employee.section_visa') || 'Visa' },
  { key: 'language_profile', label: () => t('employee.section_language') || 'Language' },
  { key: 'skills_profile', label: () => t('employee.section_skills') || 'Skills' },
]

onMounted(async () => {
  loading.value = true
  try {
    const response = await employeeApi.get(employeeId)
    employee.value = response.data?.employee as Employee
  } catch (e: any) {
    error.value = e?.message || 'Employee not found'
  } finally {
    loading.value = false
  }
})

function fieldLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface FieldEntry { key: string; value: any }

function tabFields(tabKey: string): FieldEntry[] {
  if (!employee.value) return []
  const section = (employee.value as any)[tabKey]
  if (!section || typeof section !== 'object' || Array.isArray(section)) return []
  return Object.entries(section as Record<string, any>)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([key, value]) => ({ key, value }))
}

const employeeName = () => {
  const e = employee.value
  if (!e) return employeeId
  const name = e.profile?.name
  if (typeof name === 'object' && name?.display_name) return name.display_name
  if (typeof name === 'string') return name
  return e.employee_number || employeeId
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>{{ employeeName() }}</h1>
        <p class="subtitle" v-if="employee">
          {{ employee.employee_number }}
          <template v-if="employee.employment?.department_name">&middot; {{ employee.employment.department_name }}</template>
        </p>
      </div>
      <el-button @click="router.push('/employees')">{{ t('action.back') }}</el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" style="text-align: center; padding: 60px">
      <el-icon class="is-loading" :size="32"><span /></el-icon>
    </div>

    <!-- Error -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon style="margin-bottom: 16px" />

    <!-- Employee Detail -->
    <template v-else-if="employee">
      <el-tabs v-model="activeTab" type="card">
        <el-tab-pane v-for="tab in tabs" :key="tab.key" :label="tab.label()" :name="tab.key">
          <el-card shadow="never">
            <template v-if="tabFields(tab.key).length > 0">
              <el-descriptions :column="2" border>
                <el-descriptions-item
                  v-for="field in tabFields(tab.key)"
                  :key="field.key"
                  :label="fieldLabel(field.key)"
                >
                  {{ formatValue(field.value) }}
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty v-else :description="t('common.no_records')" />
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <!-- Record info -->
      <el-card shadow="never" style="margin-top: 16px" v-if="activeTab === 'profile'">
        <template #header>Record Info</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Employee ID">
            <code>{{ employee.employee_id }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="Created At">
            {{ employee.created_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="Updated At">
            {{ employee.updated_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="employee.metadata?.deleted" label="Deleted">
            <el-tag type="danger" size="small">Yes</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
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
</style>
