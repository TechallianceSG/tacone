<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { employeeApi, masterdataApi } from '@/api/client'
import { ElMessage } from 'element-plus'

// Import locale messages directly — bypass vue-i18n dot-path resolution
import enMessages from '@/i18n/en.json'
import jaMessages from '@/i18n/ja.json'
import zhMessages from '@/i18n/zh.json'

const MSG: Record<string, Record<string, string>> = {
  en: enMessages as any, ja: jaMessages as any, zh: zhMessages as any,
}

interface Employee {
  employee_id: string; employee_number: string
  profile: Record<string, any>; employment: Record<string, any>
  payroll: Record<string, any>; visa: Record<string, any>
  dispatch_compliance: Record<string, any>; language_profile: Record<string, any>
  skills_profile: Record<string, any>; documents: any[]; metadata: Record<string, any>
  created_at: string; updated_at: string
}

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

const isEdit = computed(() => route.path.endsWith('/edit'))
const employeeId = route.params.id as string
const employee = ref<Employee | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const activeTab = ref('profile')

// ── Edit mode: flat form data ──
const flatForm = ref<Record<string, any>>({})

// ── Dropdown options for edit mode ──
const entityOptions = ref<{ entity_id: string; entity_code: string; entity_name_en: string }[]>([])
const deptOptions = ref<{ department_id: string; department_code: string; department_name_en: string }[]>([])
const teamOptions = ref<{ team_id: string; team_code: string; team_name_en: string }[]>([])

const tabs = [
  { key: 'profile', label: () => t('employee.section_profile') },
  { key: 'employment', label: () => t('employee.section_employment') },
  { key: 'payroll', label: () => t('employee.section_payroll') || 'Payroll' },
  { key: 'visa', label: () => t('employee.section_visa') || 'Visa' },
  { key: 'language_profile', label: () => t('employee.section_language') || 'Language' },
  { key: 'skills_profile', label: () => t('employee.section_skills') || 'Skills' },
]

// ── i18n helpers ──
const FIELD_ALIASES: Record<string, string> = {
  firstname: 'name__given_name', lastname: 'name__family_name',
  first_name_kana: 'name__given_name_kana', last_name_kana: 'name__family_name_kana',
  given_name: 'name__given_name', family_name: 'name__family_name',
  given_name_kana: 'name__given_name_kana', family_name_kana: 'name__family_name_kana',
  display_name: 'name__display_name', romaji_name: 'name__romaji_name',
  birthday: 'date_of_birth', contract_type: 'employment_type', joined_at: 'join_date',
  picture_url: 'picture_url',
}

function _msg(key: string): string | null {
  const cur = MSG[locale.value] || MSG.en || {}
  return cur[key] || MSG.en[key] || null
}

function fieldLabel(tabKey: string, fieldKey: string): string {
  const flatFieldKey = fieldKey.replace(/\./g, '__')
  const alias = FIELD_ALIASES[flatFieldKey]
  const effectiveKey = alias || flatFieldKey
  const fullKey = `field.${tabKey}__${effectiveKey}`
  const v = _msg(fullKey)
  if (v) return v
  const shortKey = `field.${effectiveKey}`
  const v2 = _msg(shortKey)
  if (v2) return v2
  const lastPart = fieldKey.split('.').pop() || fieldKey
  return lastPart.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ── Flatten / unflatten helpers ──
function flattenObject(obj: Record<string, any>, prefix = ''): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (value !== null && value !== undefined && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value, fullKey))
    } else {
      result[fullKey] = value
    }
  }
  return result
}

function unflattenObject(flat: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split('.')
    let current = result
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || typeof current[parts[i]] !== 'object') current[parts[i]] = {}
      current = current[parts[i]]
    }
    current[parts[parts.length - 1]] = value
  }
  return result
}

function initFlatForm(emp: Employee) {
  const flat: Record<string, any> = {}

  // First: initialize ALL schema fields with empty defaults
  for (const section of tabs.map(t => t.key)) {
    const schema = FIELD_SCHEMA[section]
    if (schema) {
      for (const fieldKey of schema) {
        flat[`${section}.${fieldKey}`] = ''
      }
    }
  }
  if (emp.employee_number) flat['employee_number'] = emp.employee_number

  // Then: overlay actual employee data (preserves non-empty values)
  for (const section of tabs.map(t => t.key)) {
    const sectionData = (emp as any)[section]
    if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      const existing = flattenObject(sectionData, section)
      for (const [key, val] of Object.entries(existing)) {
        if (val !== null && val !== undefined && val !== '') {
          flat[key] = val
        }
      }
    }
  }

  flatForm.value = flat
}

// ── View-mode helpers ──
function formatValue(value: any): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string' && value.trim() === '') return '-'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.length > 0 ? value.map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(', ') : '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatDateTime(isoStr: string | undefined): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr.substring(0, 16)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return isoStr.substring(0, 16) }
}

interface FieldEntry { key: string; value: any }

// ── Complete field schema — ensures ALL employees show the same fields ──
// Flat key paths relative to the section, e.g. "name.display_name" for profile.name.display_name
const FIELD_SCHEMA: Record<string, string[]> = {
  profile: [
    'name.display_name', 'name.given_name', 'name.family_name', 'name.romaji_name',
    'name.given_name_kana', 'name.family_name_kana',
    'email', 'email_p', 'phone', 'gender', 'date_of_birth', 'nationality', 'photo_path',
    'address.building', 'address.street', 'address.city', 'address.prefecture',
    'address.postal_code', 'address.country',
    'emergency_contact.name', 'emergency_contact.phone', 'emergency_contact.email', 'emergency_contact.relationship',
  ],
  employment: [
    'entity_id', 'department_id', 'team_id', 'position', 'employment_type', 'status',
    'join_date', 'probation_end_date', 'country_code', 'work_country', 'business_line',
    'assignment', 'manager_employee_id', 'office_location', 'legal_entity',
    'contract.start_date', 'contract.end_date',
    'resignation.resignation_date', 'resignation.last_working_date', 'resignation.reason',
  ],
  payroll: [
    'salary_type', 'monthly_base_salary', 'hourly_wage', 'daily_wage',
    'salary_amount_yen', 'transportation_allowance_yen', 'payroll_currency',
    'bank.bank_name', 'bank.branch_name', 'bank.account_type',
    'bank.account_number', 'bank.account_holder', 'bank.swift_code',
    'social_insurance_enrolled', 'employment_insurance_enrolled', 'pension_enrolled',
    'bonus_eligible', 'notes',
  ],
  visa: [
    'visa_type', 'residence_status', 'residence_card_number',
    'passport_number', 'passport_expiry_date', 'expiry_date',
    'renewal_reminder_enabled', 'renewal_reminder_date', 'notes',
  ],
  dispatch_compliance: [
    'client_name', 'contract_type', 'dispatch_start_date', 'dispatch_end_date',
    'assignment_location', 'work_description',
    'supervisor.name', 'supervisor.title', 'supervisor.email', 'supervisor.phone',
    'notes',
  ],
  language_profile: [
    'japanese_level', 'english_level', 'native_languages', 'additional_languages', 'notes',
  ],
  skills_profile: [
    'primary_skill', 'secondary_skill', 'years_of_experience',
    'it_skills', 'engineering_skills', 'certifications', 'industry_experience', 'notes',
  ],
}

// Resolve a flat dotted path like "name.display_name" from a nested object
function getNestedValue(obj: Record<string, any>, path: string): any {
  const parts = path.split('.')
  let cur: any = obj
  for (const p of parts) {
    if (cur === null || cur === undefined || typeof cur !== 'object') return undefined
    cur = cur[p]
  }
  return cur
}

function tabFields(tabKey: string): FieldEntry[] {
  if (!employee.value) return []
  const section = (employee.value as any)[tabKey]
  const schema = FIELD_SCHEMA[tabKey]
  if (!schema) return []
  const sectionData = (section && typeof section === 'object' && !Array.isArray(section))
    ? section as Record<string, any>
    : {}
  return schema.map(key => ({
    key,
    value: getNestedValue(sectionData, key),
  }))
}

// ── Edit-mode field helpers ──
function editFields(tabKey: string): { key: string; fullKey: string; value: any; inputType: string }[] {
  const prefix = `${tabKey}.`
  const fields: { key: string; fullKey: string; value: any; inputType: string }[] = []
  for (const [fullKey, value] of Object.entries(flatForm.value)) {
    if (fullKey.startsWith(prefix)) {
      const key = fullKey.slice(prefix.length)
      fields.push({ key, fullKey, value, inputType: fieldInputType(tabKey, key, value) })
    }
  }
  // Sort: put required/common fields first
  return fields
}

function fieldInputType(tabKey: string, fieldKey: string, value: any): string {
  if (typeof value === 'boolean') return 'switch'
  const lastPart = fieldKey.split('.').pop() || ''
  if (lastPart.endsWith('_date') || lastPart === 'date_of_birth' || lastPart === 'joined_at') return 'date'
  if (lastPart === 'entity_id') return 'entity_select'
  if (lastPart === 'department_id') return 'dept_select'
  if (lastPart === 'team_id') return 'team_select'
  if (lastPart === 'gender') return 'gender_select'
  if (lastPart === 'status') return 'status_select'
  if (lastPart === 'employment_type' || lastPart === 'contract_type') return 'emp_type_select'
  if (lastPart === 'business_line') return 'biz_line_select'
  if (lastPart === 'country_code' || lastPart === 'work_country') return 'country_select'
  if (lastPart === 'japanese_level') return 'jp_select'
  if (lastPart === 'english_level') return 'en_select'
  return 'text'
}

const GENDER_OPTS = ['male', 'female', 'other']
const STATUS_OPTS = ['active', 'probation', 'resigned', 'suspended', 'inactive']
const TYPE_OPTS = ['employee', 'contractor', 'dispatch', 'part_time', 'intern']
const BIZ_LINES = ['recruitment', 'rpo', 'haken', 'payroll', 'internal', 'ai_platform']
const JP_OPTS = ['native', 'business', 'daily_conversation', 'beginner', 'none']
const EN_OPTS = ['native', 'business', 'daily_conversation', 'beginner', 'none']
const COUNTRY_OPTS = ['JP', 'CN', 'SG']

// ── Label lookup for enum values (edit mode selects) ──
const L = {
  japanese_level: { native: () => t('enum.japanese.native'), business: () => t('enum.japanese.business'), daily_conversation: () => t('enum.japanese.daily'), beginner: () => t('enum.japanese.beginner'), none: () => t('enum.japanese.none') },
  english_level: { native: () => t('enum.english.native'), business: () => t('enum.english.business'), daily_conversation: () => t('enum.english.daily'), beginner: () => t('enum.english.beginner'), none: () => t('enum.english.none') },
  status: { active: () => t('enum.status.active'), probation: () => t('enum.status.probation'), resigned: () => t('enum.status.resigned'), suspended: () => t('enum.status.suspended'), inactive: () => t('enum.status.inactive') },
  employment_type: { employee: () => t('enum.employment_type.seishain'), contractor: () => t('enum.employment_type.keiyaku'), dispatch: () => t('enum.employment_type.haken'), part_time: () => t('enum.employment_type.part_time'), intern: () => t('enum.employment_type.intern') },
}
function Lbl(cat: string, val: string): string {
  const m = (L as any)[cat]
  if (m && m[val] && typeof m[val] === 'function') return m[val]()
  return val || '-'
}

// ── Data loading ──
onMounted(async () => {
  loading.value = true; error.value = ''
  try {
    const [empRes, er, dr, tr] = await Promise.all([
      employeeApi.get(employeeId),
      masterdataApi.entities(),
      masterdataApi.departments(),
      masterdataApi.teams(),
    ])
    employee.value = empRes.data?.employee as Employee
    entityOptions.value = er.data?.entities || []
    deptOptions.value = dr.data?.departments || []
    teamOptions.value = tr.data?.teams || []

    if (isEdit.value && employee.value) {
      initFlatForm(employee.value)
    }
  } catch (e: any) {
    error.value = e?.message || 'Employee not found'
  } finally { loading.value = false }
})

// Re-init flat form when switching to edit mode (same component, no remount)
watch(isEdit, (editing) => {
  if (editing && employee.value) {
    initFlatForm(employee.value)
  }
})

// ── Save (edit mode) ──
async function handleSave() {
  saving.value = true
  try {
    // Group flat form by section
    const grouped: Record<string, any> = {}
    for (const [fullKey, value] of Object.entries(flatForm.value)) {
      const dotIdx = fullKey.indexOf('.')
      if (dotIdx === -1) continue
      const section = fullKey.slice(0, dotIdx)
      const fieldKey = fullKey.slice(dotIdx + 1)
      if (!grouped[section]) grouped[section] = {}
      grouped[section][fieldKey] = value
    }
    // Unflatten each section
    const payload: Record<string, any> = {}
    for (const [section, flat] of Object.entries(grouped)) {
      payload[section] = unflattenObject(flat)
    }
    // Also include employee_number
    if (flatForm.value['employee_number']) {
      payload['employee_number'] = flatForm.value['employee_number']
    }

    const { data } = await (employeeApi as any).update(employeeId, payload)
    if (data?.employee) {
      ElMessage.success(t('employee.update_success') || 'Updated')
      // Refresh view data and switch to view mode
      employee.value = data.employee as Employee
      router.replace(`/employees/${employeeId}`)
    } else {
      ElMessage.error(data?.error || 'Update failed')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.message || 'Update failed')
  } finally { saving.value = false }
}

function handleCancel() {
  router.push(`/employees/${employeeId}`)
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
      <div style="display:flex;gap:8px">
        <el-button v-if="!isEdit" type="primary" @click="router.push(`/employees/${employeeId}/edit`)">{{ t('action.edit') }}</el-button>
        <el-button v-if="isEdit" type="primary" @click="handleSave" :loading="saving">{{ t('common.save') }}</el-button>
        <el-button v-if="isEdit" @click="handleCancel">{{ t('action.cancel') }}</el-button>
        <el-button v-else @click="router.push('/employees')">{{ t('action.back') }}</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" style="text-align: center; padding: 60px">
      <el-icon class="is-loading" :size="32"><span /></el-icon>
    </div>

    <!-- Error -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon style="margin-bottom: 16px" />

    <!-- Content -->
    <div class="detail-content" v-if="employee">
      <el-tabs v-model="activeTab" type="card">
        <el-tab-pane v-for="tab in tabs" :key="tab.key" :label="tab.label()" :name="tab.key">
          <el-card shadow="never">
            <!-- View mode -->
            <template v-if="!isEdit">
              <el-descriptions v-if="tabFields(tab.key).length > 0" :column="2" border>
                <el-descriptions-item
                  v-for="field in tabFields(tab.key)"
                  :key="field.key"
                  :label="fieldLabel(tab.key, field.key)"
                >
                  {{ formatValue(field.value) }}
                </el-descriptions-item>
              </el-descriptions>
              <el-empty v-else :description="t('common.no_records')" />
            </template>

            <!-- Edit mode -->
            <template v-else>
              <el-form v-if="editFields(tab.key).length > 0" label-position="top">
                <el-row :gutter="16">
                  <el-col :span="12" v-for="f in editFields(tab.key)" :key="f.fullKey">
                    <el-form-item :label="fieldLabel(tab.key, f.key)">

                      <!-- Text input -->
                      <el-input
                        v-if="f.inputType === 'text'"
                        v-model="flatForm[f.fullKey]"
                      />

                      <!-- Date picker -->
                      <el-date-picker
                        v-else-if="f.inputType === 'date'"
                        v-model="flatForm[f.fullKey]"
                        type="date"
                        value-format="YYYY-MM-DD"
                        style="width:100%"
                      />

                      <!-- Boolean switch -->
                      <el-switch
                        v-else-if="f.inputType === 'switch'"
                        v-model="flatForm[f.fullKey]"
                      />

                      <!-- Entity select -->
                      <el-select
                        v-else-if="f.inputType === 'entity_select'"
                        v-model="flatForm[f.fullKey]"
                        style="width:100%"
                      >
                        <el-option v-for="e in entityOptions" :key="e.entity_id" :label="`${e.entity_code} - ${e.entity_name_en}`" :value="e.entity_id" />
                      </el-select>

                      <!-- Department select -->
                      <el-select
                        v-else-if="f.inputType === 'dept_select'"
                        v-model="flatForm[f.fullKey]"
                        clearable style="width:100%"
                      >
                        <el-option v-for="d in deptOptions" :key="d.department_id" :label="`${d.department_code} - ${d.department_name_en}`" :value="d.department_id" />
                      </el-select>

                      <!-- Team select -->
                      <el-select
                        v-else-if="f.inputType === 'team_select'"
                        v-model="flatForm[f.fullKey]"
                        clearable style="width:100%"
                      >
                        <el-option v-for="tm in teamOptions" :key="tm.team_id" :label="`${tm.team_code} - ${tm.team_name_en}`" :value="tm.team_id" />
                      </el-select>

                      <!-- Gender select -->
                      <el-select v-else-if="f.inputType === 'gender_select'" v-model="flatForm[f.fullKey]" clearable style="width:100%">
                        <el-option v-for="g in GENDER_OPTS" :key="g" :label="g" :value="g" />
                      </el-select>

                      <!-- Status select -->
                      <el-select v-else-if="f.inputType === 'status_select'" v-model="flatForm[f.fullKey]" style="width:100%">
                        <el-option v-for="s in STATUS_OPTS" :key="s" :label="Lbl('status', s)" :value="s" />
                      </el-select>

                      <!-- Employment type select -->
                      <el-select v-else-if="f.inputType === 'emp_type_select'" v-model="flatForm[f.fullKey]" style="width:100%">
                        <el-option v-for="tp in TYPE_OPTS" :key="tp" :label="Lbl('employment_type', tp)" :value="tp" />
                      </el-select>

                      <!-- Business line select -->
                      <el-select v-else-if="f.inputType === 'biz_line_select'" v-model="flatForm[f.fullKey]" clearable style="width:100%">
                        <el-option v-for="b in BIZ_LINES" :key="b" :label="b" :value="b" />
                      </el-select>

                      <!-- Country select -->
                      <el-select v-else-if="f.inputType === 'country_select'" v-model="flatForm[f.fullKey]" clearable style="width:100%">
                        <el-option v-for="c in COUNTRY_OPTS" :key="c" :label="t('country.' + c.toLowerCase())" :value="c" />
                      </el-select>

                      <!-- Japanese level -->
                      <el-select v-else-if="f.inputType === 'jp_select'" v-model="flatForm[f.fullKey]" clearable style="width:100%">
                        <el-option v-for="l in JP_OPTS" :key="l" :label="Lbl('japanese_level', l)" :value="l" />
                      </el-select>

                      <!-- English level -->
                      <el-select v-else-if="f.inputType === 'en_select'" v-model="flatForm[f.fullKey]" clearable style="width:100%">
                        <el-option v-for="l in EN_OPTS" :key="l" :label="Lbl('english_level', l)" :value="l" />
                      </el-select>

                    </el-form-item>
                  </el-col>
                </el-row>
              </el-form>
              <el-empty v-else :description="t('common.no_records')" />
            </template>
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <!-- Record info -->
      <el-card shadow="never" style="margin-top: 16px">
        <template #header>{{ t('employee.record_info') }}</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('field.employee_id')">
            <code>{{ employee.employee_id }}</code>
          </el-descriptions-item>
          <el-descriptions-item :label="t('common.created_at')">
            {{ formatDateTime(employee.metadata?.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('common.updated_at')">
            {{ formatDateTime(employee.metadata?.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="employee.metadata?.deleted" :label="t('common.deleted')">
            <el-tag type="danger" size="small">Yes</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
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
.detail-content {
  width: 100%;
}
.detail-content :deep(.el-descriptions) {
  table-layout: fixed;
  width: 100%;
}
/* column="2" → 4 cells per row → each 25% */
.detail-content :deep(.el-descriptions__cell) {
  width: 25% !important;
}
.detail-content :deep(.el-descriptions__label) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
