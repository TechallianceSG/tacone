<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useI18nStore } from '@/stores/i18n'
import { employeeApi, masterdataApi } from '@/api/client'
import { Plus, Upload, Search, RefreshLeft } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

// ── i18n ──
const { t, locale } = useI18n()
const i18nStore = useI18nStore()

// ── Lang-aware labels ──
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

interface Employee {
  employee_id: string; employee_number: string
  profile: { name: { display_name: string }; email: string }
  employment: {
    entity_id: string; entity_code: string; entity_name: string
    department_id: string; department: string; department_code: string; department_name: string
    team_id: string; team: string; team_code: string; team_name: string
    position: string; employment_type: string; status: string
  }
  language_profile: { japanese_level: string; english_level: string }
  skills_profile: { primary_skill: string }
}

const router = useRouter()
const loading = ref(false)
const error = ref('')
const employees = ref<Employee[]>([])
const page = ref(1); const pageSize = ref(20)
const total = ref(0); const totalAll = ref(0); const filtered = ref(false)

const filters = reactive({ q: '', entity_id: '', country_code: '', department_id: '', team_id: '', status: '', show_resigned: false, employment_type: '', japanese_level: '', english_level: '', skill: '' })
const filtersVisible = ref(false)
const entityOptions = ref<{ entity_id: string; entity_code: string; entity_name_en: string }[]>([])
const deptOptions = ref<{ department_id: string; department_code: string; department_name_en: string }[]>([])
const teamOptions = ref<{ team_id: string; team_code: string; team_name_en: string }[]>([])
const STATUS_OPTS = ['active', 'probation', 'resigned', 'suspended', 'inactive']
const TYPE_OPTS = ['employee', 'contractor', 'dispatch', 'part_time', 'intern']
const TYPE_OPTS_CREATE = ['employee', 'contractor', 'dispatch', 'part_time', 'intern']
const BIZ_LINES = ['recruitment', 'rpo', 'haken', 'payroll', 'internal', 'ai_platform']
const JP_OPTS = ['native', 'business', 'daily_conversation', 'beginner', 'none']
const EN_OPTS = ['native', 'business', 'daily_conversation', 'beginner', 'none']

// ── Create Employee Dialog ──
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const formErrors = ref<string[]>([])
const createForm = reactive({
  'profile.name.display_name': '', 'profile.email': '', 'profile.phone': '',
  'employment.entity_id': '', 'employment.department_id': '', 'employment.position': '',
  'employment.employment_type': 'employee', 'employment.status': 'active', 'employment.join_date': '',
  'employment.country_code': 'JP', 'employment.work_country': 'JP', 'employment.business_line': 'rpo',
})
const dialogRules: FormRules = {
  'profile.name.display_name': [{ required: true, message: 'Name required', trigger: 'blur' }],
  'profile.email': [{ required: true, message: 'Email required', trigger: 'blur' }, { type: 'email', message: 'Invalid email', trigger: 'blur' }],
  'employment.entity_id': [{ required: true, message: 'Entity required', trigger: 'change' }],
  'employment.department_id': [{ required: true, message: 'Department required', trigger: 'change' }],
  'employment.country_code': [{ required: true, message: 'Country required', trigger: 'change' }],
  'employment.join_date': [{ required: true, message: 'Join date required', trigger: 'change' }],
}
function openCreateDialog() {
  createForm['profile.name.display_name'] = ''; createForm['profile.email'] = ''; createForm['profile.phone'] = ''
  createForm['employment.entity_id'] = ''; createForm['employment.department_id'] = ''; createForm['employment.position'] = ''
  createForm['employment.employment_type'] = 'employee'; createForm['employment.status'] = 'active'; createForm['employment.join_date'] = ''
  createForm['employment.country_code'] = 'JP'; createForm['employment.work_country'] = 'JP'; createForm['employment.business_line'] = 'rpo'
  formErrors.value = []; dialogVisible.value = true
}
async function handleCreate() {
  if (!formRef.value) return
  try { await formRef.value.validate() } catch { return }
  submitting.value = true; formErrors.value = []
  try {
    const payload: Record<string, any> = {}
    for (const [key, val] of Object.entries(createForm)) { if (val) payload[key] = val }
    const { data } = await (employeeApi as any).create(payload)
    if (data?.success) { dialogVisible.value = false; loadEmployees() }
    else { formErrors.value = data?.errors || ['Failed'] }
  } catch (e: any) { formErrors.value = e?.response?.data?.errors || [e?.message || 'Failed'] }
  finally { submitting.value = false }
}

// ── Data loading ──
async function loadFilterOptions() {
  try {
    const [er, dr, tr] = await Promise.all([masterdataApi.entities(), masterdataApi.departments(), masterdataApi.teams()])
    entityOptions.value = er.data?.entities || []; deptOptions.value = dr.data?.departments || []; teamOptions.value = tr.data?.teams || []
  } catch { /* ignore */ }
}
async function loadEmployees() {
  loading.value = true; error.value = ''
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (filters.q.trim()) params.q = filters.q.trim()
    if (filters.entity_id) params.entity_id = filters.entity_id
    if (filters.country_code) params.country_code = filters.country_code
    if (filters.department_id) params.department_id = filters.department_id
    if (filters.team_id) params.team_id = filters.team_id
    if (filters.status) params.status = filters.status
    if (filters.show_resigned) params.show_resigned = '1'
    if (filters.employment_type) params.employment_type = filters.employment_type
    if (filters.japanese_level) params.japanese_level = filters.japanese_level
    if (filters.english_level) params.english_level = filters.english_level
    if (filters.skill.trim()) params.skill = filters.skill.trim()
    const { data } = await employeeApi.list(params)
    employees.value = data?.employees || []; total.value = data?.total || 0; totalAll.value = data?.total_all || 0; filtered.value = data?.filtered || false
  } catch (e: any) { error.value = e?.response?.data?.error || e?.message || 'Failed' }
  finally { loading.value = false }
}
function handlePageChange(p: number) { page.value = p; loadEmployees() }
function handleSizeChange(s: number) { pageSize.value = s; page.value = 1; loadEmployees() }
function applyFilter() { page.value = 1; loadEmployees() }
function clearFilter() { Object.assign(filters, { q: '', entity_id: '', country_code: '', department_id: '', team_id: '', status: '', show_resigned: false, employment_type: '', japanese_level: '', english_level: '', skill: '' }); page.value = 1; loadEmployees() }
function viewEmployee(id: string) { router.push(`/employees/${id}`) }
function importPage() { router.push('/employees/import') }
function getName(e: Employee) { return e.profile?.name?.display_name || '-' }
function getEmail(e: Employee) { return e.profile?.email || '-' }
function entityDisp(e: Employee) { return [e.employment?.entity_code, e.employment?.entity_name].filter(Boolean).join(' - ') || '-' }
function deptDisp(e: Employee) { return e.employment?.department_name || e.employment?.department || '-' }
function teamDisp(e: Employee) { return e.employment?.team_name || e.employment?.team || '-' }

const countLabel = computed(() => filtered.value ? t('employee.showing_filtered', { shown: total.value, total: totalAll.value }) : t('employee.total_count', { count: total.value }))

onMounted(() => { loadFilterOptions(); loadEmployees() })
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div>
        <p class="eyebrow">{{ t('employee.module_title') }}</p>
        <h1>{{ t('employee.list_title') }}</h1>
      </div>
      <div class="topbar-actions">
        <el-button type="primary" @click="openCreateDialog"><el-icon><Plus /></el-icon>{{ t('employee.create') }}</el-button>
        <el-button @click="importPage"><el-icon><Upload /></el-icon>{{ t('employee.import_csv') }}</el-button>
      </div>
    </div>

    <!-- Filters -->
    <el-collapse v-model="filtersVisible" style="margin-bottom:16px">
      <template #title>
        <el-icon><Search /></el-icon>&nbsp;{{ t('action.filter') }}
        <el-tag v-if="filtered" type="warning" size="small" style="margin-left:8px">{{ total }} / {{ totalAll }}</el-tag>
      </template>
      <el-form :model="filters" label-position="top" inline>
        <el-form-item :label="t('action.search')"><el-input v-model="filters.q" :placeholder="t('employee.search_placeholder')" clearable style="width:180px" @keyup.enter="applyFilter" /></el-form-item>
        <el-form-item :label="t('field.entity')">
          <el-select v-model="filters.entity_id" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="e in entityOptions" :key="e.entity_id" :label="`${e.entity_code} - ${e.entity_name_en}`" :value="e.entity_id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.country')">
          <el-select v-model="filters.country_code" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option :label="t('country.jp')" value="JP" /><el-option :label="t('country.cn')" value="CN" /><el-option :label="t('country.sg')" value="SG" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.department')">
          <el-select v-model="filters.department_id" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="d in deptOptions" :key="d.department_id" :label="`${d.department_code} - ${d.department_name_en}`" :value="d.department_id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.team')">
          <el-select v-model="filters.team_id" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="tm in teamOptions" :key="tm.team_id" :label="`${tm.team_code} - ${tm.team_name_en}`" :value="tm.team_id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.status')">
          <el-select v-model="filters.status" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="s in STATUS_OPTS" :key="s" :label="Lbl('status', s)" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('employee.show_resigned')"><el-switch v-model="filters.show_resigned" /></el-form-item>
        <el-form-item :label="t('field.employment_type')">
          <el-select v-model="filters.employment_type" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="tp in TYPE_OPTS" :key="tp" :label="Lbl('employment_type', tp)" :value="tp" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.japanese_level')">
          <el-select v-model="filters.japanese_level" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="l in JP_OPTS" :key="l" :label="Lbl('japanese_level', l)" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.english_level')">
          <el-select v-model="filters.english_level" clearable :placeholder="t('filter.all')" style="width:180px">
            <el-option v-for="l in EN_OPTS" :key="l" :label="Lbl('english_level', l)" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.skill')"><el-input v-model="filters.skill" :placeholder="t('employee.skill_placeholder')" clearable style="width:180px" @keyup.enter="applyFilter" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilter"><el-icon><Search /></el-icon>{{ t('action.filter') }}</el-button>
          <el-button @click="clearFilter"><el-icon><RefreshLeft /></el-icon>{{ t('action.clear') }}</el-button>
        </el-form-item>
      </el-form>
    </el-collapse>

    <el-alert v-if="error" :title="error" type="error" show-icon closable @close="error=''" style="margin-bottom:16px" />

    <!-- Table -->
    <el-card shadow="never">
      <el-table :data="employees" v-loading="loading" stripe border style="width:100%" @row-click="(row: Employee) => viewEmployee(row.employee_id)">
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="140" sortable="custom" />
        <el-table-column :label="t('field.employee_name')" min-width="160">
          <template #default="{ row }"><strong>{{ getName(row) }}</strong></template>
        </el-table-column>
        <el-table-column :label="t('field.email')" min-width="180">
          <template #default="{ row }">{{ getEmail(row) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.entity')" min-width="140">
          <template #default="{ row }">{{ entityDisp(row) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.department')" min-width="120">
          <template #default="{ row }">{{ deptDisp(row) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.team')" min-width="120">
          <template #default="{ row }">{{ teamDisp(row) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.position')" prop="employment.position" min-width="120" />
        <el-table-column :label="t('field.employment_type')" width="120">
          <template #default="{ row }">{{ Lbl('employment_type', row.employment?.employment_type) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.employment?.status === 'active' ? 'success' : row.employment?.status === 'probation' ? 'warning' : row.employment?.status === 'resigned' ? 'info' : 'danger'" size="small">{{ Lbl('status', row.employment?.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.japanese_level')" width="100">
          <template #default="{ row }">{{ Lbl('japanese_level', row.language_profile?.japanese_level) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.english_level')" width="100">
          <template #default="{ row }">{{ Lbl('english_level', row.language_profile?.english_level) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.skill')" prop="skills_profile.primary_skill" min-width="120" />
        <el-table-column :label="t('field.actions')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewEmployee(row.employee_id)">{{ t('action.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px">
        <span class="muted">{{ countLabel }}</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]" :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background small
          @current-change="handlePageChange" @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- ═══════ Create Employee Dialog ═══════ -->
    <el-dialog v-model="dialogVisible" :title="t('employee.create_title')" width="640px" destroy-on-close>
      <el-alert v-if="formErrors.length" type="error" show-icon style="margin-bottom:16px">
        <li v-for="(e, i) in formErrors" :key="i">{{ e }}</li>
      </el-alert>
      <el-form ref="formRef" :model="createForm" :rules="dialogRules" label-position="top">
        <el-divider content-position="left">{{ t('employee.section_profile') }}</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.employee_name')" prop="profile.name.display_name">
              <el-input v-model="createForm['profile.name.display_name']" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.email')" prop="profile.email">
              <el-input v-model="createForm['profile.email']" type="email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.phone')">
              <el-input v-model="createForm['profile.phone']" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">{{ t('employee.section_employment') }}</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.entity')" prop="employment.entity_id">
              <el-select v-model="createForm['employment.entity_id']" :placeholder="t('action.select')" style="width:100%">
                <el-option v-for="e in entityOptions" :key="e.entity_id" :label="`${e.entity_code} - ${e.entity_name_en}`" :value="e.entity_id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.department')" prop="employment.department_id">
              <el-select v-model="createForm['employment.department_id']" :placeholder="t('action.select')" style="width:100%">
                <el-option v-for="d in deptOptions" :key="d.department_id" :label="`${d.department_code} - ${d.department_name_en}`" :value="d.department_id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item :label="t('field.country')" prop="employment.country_code">
              <el-select v-model="createForm['employment.country_code']" style="width:100%">
                <el-option :label="t('country.jp')" value="JP" /><el-option :label="t('country.cn')" value="CN" /><el-option :label="t('country.sg')" value="SG" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('field.work_country')" prop="employment.work_country">
              <el-select v-model="createForm['employment.work_country']" style="width:100%">
                <el-option :label="t('country.jp')" value="JP" /><el-option :label="t('country.cn')" value="CN" /><el-option :label="t('country.sg')" value="SG" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('field.business_line')" prop="employment.business_line">
              <el-select v-model="createForm['employment.business_line']" style="width:100%">
                <el-option label="RPO" value="rpo" /><el-option label="Haken" value="haken" /><el-option label="Recruitment" value="recruitment" /><el-option label="Payroll" value="payroll" /><el-option label="Internal" value="internal" /><el-option label="AI Platform" value="ai_platform" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item :label="t('field.position')">
              <el-input v-model="createForm['employment.position']" :placeholder="t('employee.position_placeholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('field.employment_type')">
              <el-select v-model="createForm['employment.employment_type']" style="width:100%">
                <el-option v-for="tp in TYPE_OPTS" :key="tp" :label="Lbl('employment_type', tp)" :value="tp" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('field.status')">
              <el-select v-model="createForm['employment.status']" style="width:100%">
                <el-option label="Active" value="active" /><el-option label="Probation" value="probation" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.join_date')" prop="employment.join_date">
              <el-date-picker v-model="createForm['employment.join_date']" type="date" :placeholder="t('action.select')" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" @click="handleCreate" :loading="submitting">{{ t('employee.create') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.el-collapse { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 8px 16px; }
</style>
