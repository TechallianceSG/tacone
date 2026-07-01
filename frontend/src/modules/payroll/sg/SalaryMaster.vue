<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollSgApi, masterdataApi } from '@/api/client'
import client from '@/api/client'
import { ElMessage } from 'element-plus'
import { Plus, Download, Upload, Search } from '@element-plus/icons-vue'

const { t } = useI18n()

// ── Types ──
interface SalaryMasterRecord {
  salary_master_id?: string
  employee_id: string
  employee_number: string
  employee_name: string
  email?: string
  country_code?: string
  entity_id: string
  department_id?: string
  department_label?: string
  team_id?: string
  team_label?: string
  employment_status?: string
  employeeadmin_status?: string
  employeeadmin_payroll_ready?: boolean
  employeeadmin_readiness_percent?: number
  salary_type: string
  basic_salary?: number
  hourly_rate?: number
  daily_rate?: number
  standard_work_days?: number
  standard_work_hours?: number
  standard_monthly_hours?: number
  overtime_hourly_rate?: number
  fixed_allowance?: number
  performance_bonus?: number
  recurring_deductions?: number
  cpf_applicable?: boolean
  cpf_input_mode?: string
  cpf_employee_manual?: number
  cpf_employer_manual?: number
  skill_development_levy?: number
  foreign_worker_levy?: number
  bank_name?: string
  bank_branch_name?: string
  bank_swift_code?: string
  bank_account_type?: string
  bank_account_name?: string
  bank_account_number?: string
  payroll_currency?: string
  notes?: string
  active?: boolean
  source?: string
  employeeadmin_bank_snapshot?: Record<string, any>
  created_at?: string
  updated_at?: string
  deactivated_at?: string
  deactivated_by?: string
  deactivation_reason?: string
}

interface EntityOption {
  entity_id: string
  entity_code: string
  entity_name_en: string
  entity_name_zh: string
  entity_name_ja: string
  country: string
}

// ── State ──
const loading = ref(false)
const records = ref<SalaryMasterRecord[]>([])
const allRecords = ref<SalaryMasterRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Filters
const searchText = ref('')
const filterEntity = ref('')
const filterDepartment = ref('')
const filterTeam = ref('')
const filterSalaryType = ref('')
const filterStatus = ref('')

// Masterdata options
const entityOptions = ref<EntityOption[]>([])
const departmentOptions = ref<string[]>([])
const teamOptions = ref<string[]>([])

const SALARY_TYPES = ['monthly', 'hourly', 'daily', 'monthly_hour']
const CPF_MODES = ['manual', 'parameter_assisted']
const CURRENCIES = ['SGD', 'USD', 'CNY', 'JPY']
const BANK_ACCOUNT_TYPES = ['ordinary', 'current', 'savings']

// ── Create/Edit Dialog ──
const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEditing = ref(false)
const editingEmployeeId = ref('')
const form = reactive<Record<string, any>>({
  employee_id: '',
  employee_number: '',
  employee_name: '',
  email: '',
  entity_id: 'SG',
  department_id: '',
  department_label: '',
  team_id: '',
  team_label: '',
  salary_type: 'monthly',
  basic_salary: 0,
  hourly_rate: 0,
  daily_rate: 0,
  standard_work_days: 22,
  standard_work_hours: 176,
  standard_monthly_hours: 160,
  overtime_hourly_rate: 0,
  fixed_allowance: 0,
  performance_bonus: 0,
  recurring_deductions: 0,
  cpf_applicable: true,
  cpf_input_mode: 'manual',
  cpf_employee_manual: 0,
  cpf_employer_manual: 0,
  skill_development_levy: 0,
  foreign_worker_levy: 0,
  bank_name: '',
  bank_branch_name: '',
  bank_swift_code: '',
  bank_account_type: 'ordinary',
  bank_account_name: '',
  bank_account_number: '',
  payroll_currency: 'SGD',
  notes: '',
  active: true,
  source: 'manual',
})
const saving = ref(false)
const activeTab = ref('basic')

// ── Import Dialog ──
const importDialogVisible = ref(false)
const importableEmployees = ref<any[]>([])
const selectedImportIds = ref<string[]>([])
const importLoading = ref(false)

// ── Deactivate Dialog ──
const deactivateDialogVisible = ref(false)
const deactivateTarget = ref<SalaryMasterRecord | null>(null)
const deactivateReason = ref('')
const deactivating = ref(false)

// ── Computed ──
const filteredRecords = computed(() => {
  let result = allRecords.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    result = result.filter(r =>
      (r.employee_number || '').toLowerCase().includes(q) ||
      (r.employee_name || '').toLowerCase().includes(q)
    )
  }
  if (filterEntity.value) result = result.filter(r => r.entity_id === filterEntity.value)
  if (filterDepartment.value) result = result.filter(r => (r.department_label || '') === filterDepartment.value)
  if (filterTeam.value) result = result.filter(r => (r.team_label || '') === filterTeam.value)
  if (filterSalaryType.value) result = result.filter(r => r.salary_type === filterSalaryType.value)
  if (filterStatus.value === 'active') result = result.filter(r => r.active)
  if (filterStatus.value === 'inactive') result = result.filter(r => !r.active)
  return result
})

const hasFilter = computed(() =>
  searchText.value || filterEntity.value || filterDepartment.value ||
  filterTeam.value || filterSalaryType.value || filterStatus.value
)

const pagedRecords = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})

// ── Helpers ──
function entityLabel(entityId: string): string {
  const found = entityOptions.value.find(e => e.entity_id === entityId || e.entity_code === entityId)
  if (found) {
    return `${found.entity_code} - ${found.entity_name_en} (${found.country})`
  }
  return entityId || '-'
}

function readinessPercent(row: SalaryMasterRecord): number {
  if (!row.active) return 0
  if (row.employeeadmin_readiness_percent != null && row.employeeadmin_readiness_percent > 0) {
    return Math.min(Math.round(row.employeeadmin_readiness_percent), 100)
  }
  const checks: { key: keyof SalaryMasterRecord; condition?: () => boolean }[] = [
    { key: 'employee_id' },
    { key: 'employee_number' },
    { key: 'employee_name' },
    { key: 'entity_id' },
    { key: 'bank_name' },
    { key: 'bank_account_name' },
    { key: 'bank_account_number' },
    { key: 'bank_account_type' },
  ]
  if (row.salary_type === 'monthly' || row.salary_type === 'monthly_hour') {
    checks.push({ key: 'basic_salary' })
  }
  if (row.salary_type === 'hourly' || row.salary_type === 'monthly_hour') {
    checks.push({ key: 'hourly_rate' })
  }
  if (row.salary_type === 'daily') {
    checks.push({ key: 'daily_rate' })
  }
  if (row.cpf_applicable && row.cpf_input_mode === 'manual') {
    checks.push({ key: 'cpf_employee_manual' })
  }
  const passed = checks.filter(c => {
    const val = row[c.key]
    return val != null && val !== '' && val !== 0
  }).length
  return Math.round((passed / checks.length) * 100)
}

function readinessType(row: SalaryMasterRecord): 'success' | 'warning' | 'danger' | 'exception' {
  if (!row.active) return 'exception'
  const pct = readinessPercent(row)
  if (pct >= 100) return 'success'
  if (pct >= 50) return 'warning'
  return 'exception'
}

function readinessLabel(row: SalaryMasterRecord): string {
  if (!row.active) return t('status.inactive')
  const pct = readinessPercent(row)
  if (pct >= 100) return t('payroll_readiness.ready')
  if (pct >= 50) return `${pct}%`
  return t('payroll_readiness.blocked')
}

function salaryTypeLabel(val: string): string {
  const key = `salary_type.${val}`
  const translated = t(key)
  return translated !== key ? translated : val
}

function currencyLabel(val: string): string {
  const key = `currency.${val}`
  const translated = t(key)
  return translated !== key ? translated : val
}

function bankAccountTypeLabel(val: string): string {
  const key = `bank_account_type.${val}`
  const translated = t(key)
  return translated !== key ? translated : val
}

function moneyFmt(val: number | undefined | null): string {
  if (val == null) return '0.00'
  return Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// ── Data Loading ──
async function loadEntities() {
  try {
    const res = await masterdataApi.entities()
    const data = res.data?.data || res.data?.entities || []
    entityOptions.value = data as EntityOption[]
  } catch {
    entityOptions.value = []
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const res = await payrollSgApi.salaryMaster()
    const items: SalaryMasterRecord[] = res.data?.data?.items || res.data?.data || res.data?.items || []
    allRecords.value = items
    records.value = items
    total.value = items.length
    // Derive department and team filter options from data
    const depts = new Set<string>()
    const teams = new Set<string>()
    for (const r of items) {
      if (r.department_label) depts.add(r.department_label)
      if (r.team_label) teams.add(r.team_label)
    }
    departmentOptions.value = Array.from(depts).sort()
    teamOptions.value = Array.from(teams).sort()
  } catch (e: any) {
    ElMessage.error(e?.message || 'Failed to load salary master records')
  } finally {
    loading.value = false
  }
}

// ── Filter Handlers ──
function handleSearch() {
  page.value = 1
}

function clearFilters() {
  searchText.value = ''
  filterEntity.value = ''
  filterDepartment.value = ''
  filterTeam.value = ''
  filterSalaryType.value = ''
  filterStatus.value = ''
  page.value = 1
}

// ── Create/Edit Dialog ──
function resetForm() {
  form.employee_id = ''
  form.employee_number = ''
  form.employee_name = ''
  form.email = ''
  form.entity_id = 'SG'
  form.department_id = ''
  form.department_label = ''
  form.team_id = ''
  form.team_label = ''
  form.salary_type = 'monthly'
  form.basic_salary = 0
  form.hourly_rate = 0
  form.daily_rate = 0
  form.standard_work_days = 22
  form.standard_work_hours = 176
  form.standard_monthly_hours = 160
  form.overtime_hourly_rate = 0
  form.fixed_allowance = 0
  form.performance_bonus = 0
  form.recurring_deductions = 0
  form.cpf_applicable = true
  form.cpf_input_mode = 'manual'
  form.cpf_employee_manual = 0
  form.cpf_employer_manual = 0
  form.skill_development_levy = 0
  form.foreign_worker_levy = 0
  form.bank_name = ''
  form.bank_branch_name = ''
  form.bank_swift_code = ''
  form.bank_account_type = 'ordinary'
  form.bank_account_name = ''
  form.bank_account_number = ''
  form.payroll_currency = 'SGD'
  form.notes = ''
  form.active = true
  form.source = 'manual'
  activeTab.value = 'basic'
}

function openCreateDialog() {
  isEditing.value = false
  editingEmployeeId.value = ''
  resetForm()
  dialogTitle.value = `${t('payroll.sg.salary_master')} - ${t('action.create')}`
  dialogVisible.value = true
}

function openEditDialog(row: SalaryMasterRecord) {
  isEditing.value = true
  editingEmployeeId.value = row.employee_id
  form.employee_id = row.employee_id || ''
  form.employee_number = row.employee_number || ''
  form.employee_name = row.employee_name || ''
  form.email = row.email || ''
  form.entity_id = row.entity_id || 'SG'
  form.department_id = row.department_id || ''
  form.department_label = row.department_label || ''
  form.team_id = row.team_id || ''
  form.team_label = row.team_label || ''
  form.salary_type = row.salary_type || 'monthly'
  form.basic_salary = row.basic_salary || 0
  form.hourly_rate = row.hourly_rate || 0
  form.daily_rate = row.daily_rate || 0
  form.standard_work_days = row.standard_work_days ?? 22
  form.standard_work_hours = row.standard_work_hours ?? 176
  form.standard_monthly_hours = row.standard_monthly_hours ?? 160
  form.overtime_hourly_rate = row.overtime_hourly_rate || 0
  form.fixed_allowance = row.fixed_allowance || 0
  form.performance_bonus = row.performance_bonus || 0
  form.recurring_deductions = row.recurring_deductions || 0
  form.cpf_applicable = row.cpf_applicable ?? true
  form.cpf_input_mode = row.cpf_input_mode || 'manual'
  form.cpf_employee_manual = row.cpf_employee_manual || 0
  form.cpf_employer_manual = row.cpf_employer_manual || 0
  form.skill_development_levy = row.skill_development_levy || 0
  form.foreign_worker_levy = row.foreign_worker_levy || 0
  form.bank_name = row.bank_name || ''
  form.bank_branch_name = row.bank_branch_name || ''
  form.bank_swift_code = row.bank_swift_code || ''
  form.bank_account_type = row.bank_account_type || 'ordinary'
  form.bank_account_name = row.bank_account_name || ''
  form.bank_account_number = row.bank_account_number || ''
  form.payroll_currency = row.payroll_currency || 'SGD'
  form.notes = row.notes || ''
  form.active = row.active ?? true
  form.source = row.source || 'manual'
  activeTab.value = 'basic'
  dialogTitle.value = `${t('payroll.sg.salary_master')} - ${t('action.edit')}`
  dialogVisible.value = true
}

function buildPayload(): Record<string, any> {
  return {
    employee_id: form.employee_id,
    employee_number: form.employee_number,
    employee_name: form.employee_name,
    email: form.email,
    entity_id: form.entity_id,
    department_id: form.department_id,
    department_label: form.department_label,
    team_id: form.team_id,
    team_label: form.team_label,
    salary_type: form.salary_type,
    basic_salary: Number(form.basic_salary) || 0,
    hourly_rate: Number(form.hourly_rate) || 0,
    daily_rate: Number(form.daily_rate) || 0,
    standard_work_days: Number(form.standard_work_days) || 22,
    standard_work_hours: Number(form.standard_work_hours) || 176,
    standard_monthly_hours: Number(form.standard_monthly_hours) || 160,
    overtime_hourly_rate: Number(form.overtime_hourly_rate) || 0,
    fixed_allowance: Number(form.fixed_allowance) || 0,
    performance_bonus: Number(form.performance_bonus) || 0,
    recurring_deductions: Number(form.recurring_deductions) || 0,
    cpf_applicable: !!form.cpf_applicable,
    cpf_input_mode: form.cpf_input_mode || 'manual',
    cpf_employee_manual: Number(form.cpf_employee_manual) || 0,
    cpf_employer_manual: Number(form.cpf_employer_manual) || 0,
    skill_development_levy: Number(form.skill_development_levy) || 0,
    foreign_worker_levy: Number(form.foreign_worker_levy) || 0,
    bank_name: form.bank_name,
    bank_branch_name: form.bank_branch_name,
    bank_swift_code: form.bank_swift_code,
    bank_account_type: form.bank_account_type,
    bank_account_name: form.bank_account_name,
    bank_account_number: form.bank_account_number,
    payroll_currency: form.payroll_currency,
    notes: form.notes,
    active: !!form.active,
    source: form.source || 'manual',
  }
}

async function save() {
  saving.value = true
  try {
    await payrollSgApi.saveSalaryMaster(buildPayload())
    dialogVisible.value = false
    ElMessage.success(t('common.save') + ' - ' + (isEditing.value ? t('action.edit') : t('action.create')))
    await loadRecords()
  } catch (e: any) {
    const msg = e?.response?.data?.message || e?.message || 'Save failed'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

// ── Deactivate ──
function openDeactivateDialog(row: SalaryMasterRecord) {
  deactivateTarget.value = row
  deactivateReason.value = ''
  deactivateDialogVisible.value = true
}

async function confirmDeactivate() {
  if (!deactivateTarget.value) return
  deactivating.value = true
  try {
    await client.post('/api/payroll/sg/salary-master/deactivate', {
      employee_id: deactivateTarget.value.employee_id,
      reason: deactivateReason.value || 'Manual deactivation',
    })
    deactivateDialogVisible.value = false
    deactivateTarget.value = null
    ElMessage.success(t('action.deactivate'))
    await loadRecords()
  } catch (e: any) {
    const msg = e?.response?.data?.message || e?.message || 'Deactivate failed'
    ElMessage.error(msg)
  } finally {
    deactivating.value = false
  }
}

// ── Import from EmployeeAdmin ──
async function openImportDialog() {
  importDialogVisible.value = true
  selectedImportIds.value = []
  await loadImportableEmployees()
}

async function loadImportableEmployees() {
  importLoading.value = true
  try {
    const res = await client.get('/api/employeeadmin-employees', {
      params: { country_code: 'SG', status: 'active' },
    })
    const data = res.data
    const employees = data?.employees || data?.data || []
    importableEmployees.value = employees.map((emp: any) => ({
      employee_id: emp.employee_id || emp.employee_number || '',
      employee_number: emp.employee_number || emp.employee_no || '',
      employee_name: emp.display_name || emp.employee_name || '',
      entity_id: emp.entity_id || '',
      department_label: emp.department_label || emp.department || '',
      team_label: emp.team_label || '',
      status: emp.status || emp.employment_status || '',
      payroll_ready: !!emp.payroll_ready,
    }))
  } catch {
    importableEmployees.value = []
    ElMessage.warning('EmployeeAdmin ' + t('common.unavailable'))
  } finally {
    importLoading.value = false
  }
}

function toggleSelectAllImport(checked: boolean) {
  if (checked) {
    selectedImportIds.value = importableEmployees.value.map(e => e.employee_id)
  } else {
    selectedImportIds.value = []
  }
}

async function confirmImport() {
  if (selectedImportIds.value.length === 0) {
    ElMessage.warning(t('common.no_records'))
    return
  }
  importLoading.value = true
  try {
    await client.post('/api/payroll/sg/salary-master/create', {
      employee_id: selectedImportIds.value,
      entity_id: 'SG',
    })
    importDialogVisible.value = false
    ElMessage.success(t('msg.imported'))
    await loadRecords()
  } catch (e: any) {
    const msg = e?.response?.data?.message || e?.message || 'Import failed'
    ElMessage.error(msg)
  } finally {
    importLoading.value = false
  }
}

// ── CSV Export ──
async function exportCsv() {
  try {
    const params: Record<string, string> = {}
    if (filterEntity.value) params.entity = filterEntity.value
    if (filterDepartment.value) params.department = filterDepartment.value
    if (filterTeam.value) params.team = filterTeam.value
    if (searchText.value) params.q = searchText.value
    if (filterSalaryType.value) params.salary_type = filterSalaryType.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await client.get('/api/payroll/sg/salary-master.csv', {
      params,
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `salary_master_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success(t('action.export_csv'))
  } catch (e: any) {
    ElMessage.error(e?.message || 'CSV export failed')
  }
}

// ── Pagination ──
function handlePageChange(p: number) {
  page.value = p
}

function handleSizeChange(s: number) {
  pageSize.value = s
  page.value = 1
}

// ── Init ──
onMounted(() => {
  loadEntities()
  loadRecords()
})
</script>

<template>
  <div class="page-container">
    <!-- ── Header ── -->
    <div class="page-header">
      <h3>{{ t('payroll.sg.salary_master') }}</h3>
      <div class="header-actions">
        <el-button :icon="Upload" @click="openImportDialog">
          {{ t('action.import_sg') || 'Import from EmployeeAdmin' }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          {{ t('action.create') }}
        </el-button>
        <el-button :icon="Download" @click="exportCsv">
          {{ t('action.export_csv') }}
        </el-button>
      </div>
    </div>

    <!-- ── Summary Strip ── -->
    <div class="summary-strip">
      <span>{{ allRecords.length }} {{ t('common.records_total', { total: allRecords.length }) }}</span>
      <span class="summary-dot">{{ allRecords.filter(r => r.active).length }} {{ t('status.active') }}</span>
      <span class="summary-dot">{{ allRecords.filter(r => !r.active).length }} {{ t('status.inactive') }}</span>
    </div>

    <!-- ── Filter Bar ── -->
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        :placeholder="t('employee.search_placeholder') || 'Search by No/Name...'"
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="filterEntity"
        :placeholder="t('field.entity')"
        clearable
        style="width: 200px"
        @change="page = 1"
      >
        <el-option :label="t('filter.all')" value="" />
        <el-option
          v-for="e in entityOptions"
          :key="e.entity_id"
          :label="entityLabel(e.entity_id)"
          :value="e.entity_id"
        />
      </el-select>

      <el-select
        v-model="filterDepartment"
        :placeholder="t('field.department')"
        clearable
        style="width: 160px"
        @change="page = 1"
      >
        <el-option :label="t('filter.all')" value="" />
        <el-option
          v-for="d in departmentOptions"
          :key="d"
          :label="d"
          :value="d"
        />
      </el-select>

      <el-select
        v-model="filterTeam"
        :placeholder="t('field.team')"
        clearable
        style="width: 160px"
        @change="page = 1"
      >
        <el-option :label="t('filter.all')" value="" />
        <el-option
          v-for="tval in teamOptions"
          :key="tval"
          :label="tval"
          :value="tval"
        />
      </el-select>

      <el-select
        v-model="filterSalaryType"
        :placeholder="t('field.payroll__salary_type') || t('field.salary_type')"
        clearable
        style="width: 140px"
        @change="page = 1"
      >
        <el-option :label="t('filter.all')" value="" />
        <el-option
          v-for="st in SALARY_TYPES"
          :key="st"
          :label="salaryTypeLabel(st)"
          :value="st"
        />
      </el-select>

      <el-select
        v-model="filterStatus"
        :placeholder="t('common.status')"
        clearable
        style="width: 120px"
        @change="page = 1"
      >
        <el-option :label="t('filter.all')" value="" />
        <el-option :label="t('status.active')" value="active" />
        <el-option :label="t('status.inactive')" value="inactive" />
      </el-select>

      <el-button v-if="hasFilter" text @click="clearFilters">{{ t('action.clear') }}</el-button>
    </div>

    <!-- ── Data Table ── -->
    <el-card shadow="never">
      <el-table
        :data="pagedRecords"
        v-loading="loading"
        stripe
        border
        style="width: 100%"
        :empty-text="t('common.no_records')"
        size="small"
      >
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="130" sortable />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="150" sortable />
        <el-table-column prop="email" :label="t('field.email')" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.department')" width="130">
          <template #default="{ row }">{{ row.department_label || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.team')" width="130">
          <template #default="{ row }">{{ row.team_label || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.payroll__salary_type') || t('field.salary_type')" width="110">
          <template #default="{ row }">{{ salaryTypeLabel(row.salary_type) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.basic_salary') || 'Basic Salary'" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.salary_type === 'monthly' || row.salary_type === 'monthly_hour'">{{ moneyFmt(row.basic_salary) }}</span>
            <span v-else-if="row.salary_type === 'hourly'">{{ moneyFmt(row.hourly_rate) }}</span>
            <span v-else-if="row.salary_type === 'daily'">{{ moneyFmt(row.daily_rate) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="CPF" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.cpf_applicable ? 'warning' : 'info'" size="small">
              {{ row.cpf_applicable ? t('boolean.yes') : t('boolean.no') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.payroll__payroll_currency')" width="100">
          <template #default="{ row }">{{ currencyLabel(row.payroll_currency || 'SGD') }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll_readiness.status')" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="readinessPercent(row)"
              :stroke-width="18"
              :text-inside="true"
              :status="readinessType(row)"
              :format="() => readinessLabel(row)"
            />
          </template>
        </el-table-column>
        <el-table-column :label="t('common.status')" width="85" align="center">
          <template #default="{ row }">
            <el-tag :type="row.active ? 'success' : 'danger'" size="small">
              {{ row.active ? t('status.active') : t('status.inactive') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="170" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEditDialog(row)">
              {{ t('action.edit') }}
            </el-button>
            <el-button
              v-if="row.active"
              text
              type="danger"
              size="small"
              @click="openDeactivateDialog(row)"
            >
              {{ t('action.deactivate') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- ── Record Count + Pagination ── -->
      <div class="table-footer">
        <div class="helper-text">
          {{ t('employee.showing_filtered', { shown: pagedRecords.length, total: filteredRecords.length }) }}
          <template v-if="hasFilter">
            ({{ t('filter.filtered') || 'filtered' }})
          </template>
        </div>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredRecords.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
          small
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- ── Create / Edit Dialog ── -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      top="3vh"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-tabs v-model="activeTab" type="border-card">
        <!-- Tab: Basic Info -->
        <el-tab-pane :label="t('form.group.employment_basics') || 'Basic Info'" name="basic">
          <el-form label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Employee ID'" required>
                  <el-input v-model="form.employee_id" :disabled="isEditing" placeholder="e.g. SG-EMP-001" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('field.employee_number')" required>
                  <el-input v-model="form.employee_number" :disabled="isEditing" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('field.employee_name')" required>
                  <el-input v-model="form.employee_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('field.email')">
                  <el-input v-model="form.email" type="email" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="t('field.entity')">
              <el-select v-model="form.entity_id" style="width: 100%">
                <el-option
                  v-for="e in entityOptions"
                  :key="e.entity_id"
                  :label="entityLabel(e.entity_id)"
                  :value="e.entity_id"
                />
              </el-select>
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('field.department')">
                  <el-input v-model="form.department_label" :placeholder="t('field.department')" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('field.team')">
                  <el-input v-model="form.team_label" :placeholder="t('field.team')" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="t('field.notes')">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item :label="t('common.status')">
              <el-switch
                v-model="form.active"
                :active-text="t('status.active')"
                :inactive-text="t('status.inactive')"
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Tab: Salary & Work -->
        <el-tab-pane :label="t('detail.group.salary') || 'Salary & Work'" name="salary">
          <el-form label-position="top">
            <el-form-item :label="t('field.payroll__salary_type') || t('field.salary_type')" required>
              <el-select v-model="form.salary_type" style="width: 100%">
                <el-option
                  v-for="st in SALARY_TYPES"
                  :key="st"
                  :label="salaryTypeLabel(st)"
                  :value="st"
                />
              </el-select>
            </el-form-item>
            <el-row :gutter="16">
              <el-col
                :span="12"
                v-if="form.salary_type === 'monthly' || form.salary_type === 'monthly_hour'"
              >
                <el-form-item :label="t('field.basic_salary') || 'Basic Salary'">
                  <el-input-number v-model="form.basic_salary" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col
                :span="12"
                v-if="form.salary_type === 'hourly' || form.salary_type === 'monthly_hour'"
              >
                <el-form-item :label="t('field.payroll__hourly_wage') || 'Hourly Rate'">
                  <el-input-number v-model="form.hourly_rate" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col
                :span="12"
                v-if="form.salary_type === 'daily'"
              >
                <el-form-item :label="t('field.payroll__daily_wage') || 'Daily Rate'">
                  <el-input-number v-model="form.daily_rate" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Standard Work Days'">
                  <el-input-number v-model="form.standard_work_days" :min="0" :precision="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'Standard Work Hours'">
                  <el-input-number v-model="form.standard_work_hours" :min="0" :precision="1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col
                :span="12"
                v-if="form.salary_type === 'hourly' || form.salary_type === 'monthly_hour'"
              >
                <el-form-item :label="'Standard Monthly Hours'">
                  <el-input-number v-model="form.standard_monthly_hours" :min="0" :precision="1" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col
                :span="12"
                v-if="form.salary_type === 'hourly' || form.salary_type === 'monthly_hour'"
              >
                <el-form-item :label="'Overtime Hourly Rate'">
                  <el-input-number v-model="form.overtime_hourly_rate" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="t('field.payroll__payroll_currency')">
              <el-select v-model="form.payroll_currency" style="width: 100%">
                <el-option
                  v-for="c in CURRENCIES"
                  :key="c"
                  :label="currencyLabel(c)"
                  :value="c"
                />
              </el-select>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Tab: Allowances & CPF -->
        <el-tab-pane :label="'Allowances & CPF'" name="allowances">
          <el-form label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Fixed Allowance'">
                  <el-input-number v-model="form.fixed_allowance" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'Performance Bonus'">
                  <el-input-number v-model="form.performance_bonus" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Recurring Deductions'">
                  <el-input-number v-model="form.recurring_deductions" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="CPF Applicable">
                  <el-switch v-model="form.cpf_applicable" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider content-position="left">CPF Settings</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'CPF Input Mode'">
                  <el-select v-model="form.cpf_input_mode" style="width: 100%">
                    <el-option
                      v-for="mode in CPF_MODES"
                      :key="mode"
                      :label="mode === 'manual' ? 'Manual' : 'Parameter Assisted'"
                      :value="mode"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'CPF Employee (Manual)'">
                  <el-input-number v-model="form.cpf_employee_manual" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'CPF Employer (Manual)'">
                  <el-input-number v-model="form.cpf_employer_manual" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider content-position="left">SDL / FWL</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'SDL (Skill Development Levy)'">
                  <el-input-number v-model="form.skill_development_levy" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'FWL (Foreign Worker Levy)'">
                  <el-input-number v-model="form.foreign_worker_levy" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>

        <!-- Tab: Bank Info -->
        <el-tab-pane :label="t('form.group.payroll_bank') || 'Bank Info'" name="bank">
          <el-form label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Bank Name'">
                  <el-input v-model="form.bank_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'Branch Name'">
                  <el-input v-model="form.bank_branch_name" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'SWIFT Code'">
                  <el-input v-model="form.bank_swift_code" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'Account Type'">
                  <el-select v-model="form.bank_account_type" style="width: 100%">
                    <el-option
                      v-for="at in BANK_ACCOUNT_TYPES"
                      :key="at"
                      :label="bankAccountTypeLabel(at)"
                      :value="at"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="'Account Holder'">
                  <el-input v-model="form.bank_account_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="'Account Number'">
                  <el-input v-model="form.bank_account_number" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- ── Import Dialog ── -->
    <el-dialog
      v-model="importDialogVisible"
      :title="t('action.import_sg') || 'Import from EmployeeAdmin'"
      width="750px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="import-description">
        {{ t('msg.import_employeeadmin_confirm') || 'Select SG employees from EmployeeAdmin to create Salary Master records.' }}
      </div>
      <div
        v-if="importLoading && importableEmployees.length === 0"
        v-loading="importLoading"
        style="min-height: 100px"
      />
      <template v-else>
        <div
          v-if="importableEmployees.length === 0"
          style="padding: 24px; text-align: center; color: var(--el-text-color-secondary)"
        >
          {{ t('common.no_records') }}
        </div>
        <template v-else>
          <div class="import-toolbar">
            <el-checkbox
              :indeterminate="
                selectedImportIds.length > 0 && selectedImportIds.length < importableEmployees.length
              "
              :model-value="selectedImportIds.length === importableEmployees.length"
              @change="toggleSelectAllImport"
            >
              {{ t('action.select_all') || 'Select All' }} ({{ selectedImportIds.length }}/{{ importableEmployees.length }})
            </el-checkbox>
          </div>
          <el-table
            :data="importableEmployees"
            v-loading="importLoading"
            max-height="380"
            stripe
            border
            size="small"
            style="width: 100%"
            @selection-change="(sel: any[]) => { selectedImportIds = sel.map((s: any) => s.employee_id) }"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column prop="employee_number" :label="t('field.employee_number')" width="125" />
            <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="150" />
            <el-table-column prop="department_label" :label="t('field.department')" width="120">
              <template #default="{ row }">{{ row.department_label || '-' }}</template>
            </el-table-column>
            <el-table-column prop="team_label" :label="t('field.team')" width="120">
              <template #default="{ row }">{{ row.team_label || '-' }}</template>
            </el-table-column>
            <el-table-column :label="t('common.status')" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="'Payroll Ready'" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.payroll_ready ? 'success' : 'warning'" size="small">
                  {{ row.payroll_ready ? t('boolean.yes') : t('boolean.no') }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </template>
      <template #footer>
        <el-button @click="importDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="importLoading"
          :disabled="selectedImportIds.length === 0"
          @click="confirmImport"
        >
          {{ t('action.import_sg') || 'Import' }} ({{ selectedImportIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Deactivate Dialog ── -->
    <el-dialog
      v-model="deactivateDialogVisible"
      :title="t('action.deactivate')"
      width="450px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="deactivateTarget" style="margin-bottom: 12px">
        <p>{{ t('confirm.delete_message') }}</p>
        <p style="font-weight: 600; margin: 8px 0">
          {{ deactivateTarget.employee_number }} - {{ deactivateTarget.employee_name }}
        </p>
      </div>
      <el-input
        v-model="deactivateReason"
        :placeholder="t('governance.deactivate_reason_prompt') || 'Enter deactivation reason'"
        type="textarea"
        :rows="2"
      />
      <template #footer>
        <el-button @click="deactivateDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="danger" :loading="deactivating" @click="confirmDeactivate">
          {{ t('action.deactivate') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.page-header h3 {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 700;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-strip {
  display: flex;
  gap: 16px;
  align-items: center;
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.summary-dot::before {
  content: '\2022';
  margin-right: 4px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.helper-text {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

.import-description {
  margin-bottom: 16px;
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  padding: 8px 12px;
  background: var(--el-color-info-light-9);
  border-radius: 6px;
}

.import-toolbar {
  margin-bottom: 12px;
}
</style>
