<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

// ── State ──
const loading = ref(false)
const allRecords = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Filters
const searchText = ref('')
const filterEntity = ref('')
const filterSalaryType = ref('')
const filterStatus = ref('all')

// Dialog
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const activeTab = ref('basic')
const form = ref<Record<string, any>>({})
const saving = ref(false)

// Import dialog
const importDialog = ref(false)
const importableEmployees = ref<any[]>([])
const selectedImportIds = ref<string[]>([])
const importing = ref(false)

// Deactivate dialog
const deactivateDialog = ref(false)
const deactivateId = ref('')
const deactivateReason = ref('')

// Calc preview dialog
const calcPreviewDialog = ref(false)
const calcPreviewData = ref<any>(null)
const calcPreviewResult = ref<any>(null)

// Dropdown data
const entities = ref<any[]>([])
const departments = ref<any[]>([])
const teams = ref<any[]>([])

const salaryTypes = ['monthly', 'hourly', 'daily', 'monthly_fixed_ot', 'monthly_hour']
const bankAccountTypes = ['普通預金', '当座預金', '定期預金']
const prefectureCodes = [
  '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
  '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
  '21', '22', '23', '24', '25', '26', '27', '28', '29', '30',
  '31', '32', '33', '34', '35', '36', '37', '38', '39', '40',
  '41', '42', '43', '44', '45', '46', '47'
]

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
  if (filterSalaryType.value) result = result.filter(r => r.salary_type === filterSalaryType.value)
  if (filterStatus.value === 'active') result = result.filter(r => r.active)
  if (filterStatus.value === 'inactive') result = result.filter(r => !r.active)
  return result
})

const pagedRecords = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.employees()
    allRecords.value = res.data.data?.items || []
    total.value = allRecords.value.length
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

async function loadDropdowns() {
  try {
    const [entRes, deptRes, teamRes] = await Promise.all([
      fetch('/api/masterdata/entities').then(r => r.json()),
      fetch('/api/masterdata/departments').then(r => r.json()),
      fetch('/api/masterdata/teams').then(r => r.json()),
    ])
    entities.value = entRes.data || []
    departments.value = deptRes.data || []
    teams.value = teamRes.data || []
  } catch (_) {}
}

function openCreate() {
  dialogMode.value = 'create'
  form.value = {
    salary_type: 'monthly',
    payroll_currency: 'JPY',
    active: true,
    social_insurance_eligible: true,
    employment_insurance_eligible: true,
    dependents_count: 0,
    bank_account_type: '普通預金',
  }
  activeTab.value = 'basic'
  dialogVisible.value = true
}

function openEdit(row: any) {
  dialogMode.value = 'edit'
  form.value = { ...row }
  activeTab.value = 'basic'
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    await payrollJpApi.saveEmployee(form.value)
    dialogVisible.value = false
    ElMessage.success(t('action.saved'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { saving.value = false }
}

function openDeactivate(id: string) {
  deactivateId.value = id
  deactivateReason.value = ''
  deactivateDialog.value = true
}

async function confirmDeactivate() {
  try {
    await payrollJpApi.saveEmployee({
      employee_id: deactivateId.value,
      active: false,
      deactivation_reason: deactivateReason.value
    })
    deactivateDialog.value = false
    ElMessage.success(t('action.deactivated'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function openImport() {
  importDialog.value = true
  selectedImportIds.value = []
  try {
    const res = await fetch('/api/employees').then(r => r.json())
    importableEmployees.value = (res.data?.items || []).filter(
      (e: any) => e.country_code === 'JP' || !e.country_code
    )
  } catch (_) { importableEmployees.value = [] }
}

async function importSelected() {
  importing.value = true
  try {
    const toImport = importableEmployees.value.filter(
      (e: any) => selectedImportIds.value.includes(e.employee_id)
    )
    for (const emp of toImport) {
      await payrollJpApi.saveEmployee({
        employee_id: emp.employee_id,
        employee_number: emp.employee_number || emp.employee_no,
        employee_name: emp.employee_name,
        email: emp.email,
        entity_id: emp.entity_id,
        department_label: emp.department_name || emp.department,
        team_label: emp.team_name || emp.team,
        salary_type: 'monthly',
        payroll_currency: 'JPY',
        social_insurance_eligible: true,
        employment_insurance_eligible: true,
        dependents_count: 0,
        active: true,
        source: 'EmployeeAdmin'
      })
    }
    importDialog.value = false
    ElMessage.success(t('payroll.jp.imported', { count: toImport.length }))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { importing.value = false }
}

function entityLabel(e: any) {
  if (!e) return ''
  return `${e.entity_code || ''} - ${e.entity_name || ''} (${e.country || ''})`
}

function openCalcPreview(row: any) {
  calcPreviewData.value = row
  const b = Number(row.basic_salary) || 0
  const ca = Number(row.commute_allowance) || 0
  const ha = Number(row.housing_allowance) || 0
  const fa = Number(row.family_allowance) || 0
  const pa = Number(row.position_allowance) || 0
  const fxa = Number(row.fixed_allowance) || 0
  const pb = Number(row.performance_bonus) || 0
  const ta = Number(row.transport_allowance) || 0
  const pha = Number(row.phone_allowance) || 0
  const prjb = Number(row.project_bonus) || 0
  const foAmt = Number(row.fixed_overtime_amount) || 0

  const grossPay = b + ca + ha + fa + pa + fxa + pb + ta + pha + prjb + foAmt

  // Simulated JP deductions for preview (placeholder rates)
  const healthIns = row.social_insurance_eligible !== false ? Math.round(grossPay * 0.05) : 0
  const pension = row.social_insurance_eligible !== false ? Math.round(grossPay * 0.0915) : 0
  const employIns = row.employment_insurance_eligible !== false ? Math.round(grossPay * 0.006) : 0
  const careIns = row.social_insurance_eligible !== false ? Math.round(grossPay * 0.006) : 0
  const incomeTax = Math.round(grossPay * 0.05)
  const residentTax = Number(row.monthly_resident_tax) || 0
  const deductionTotal = healthIns + pension + employIns + careIns + incomeTax + residentTax
  const netPay = grossPay - deductionTotal
  const employerCost = Math.round(grossPay * 0.15)

  calcPreviewResult.value = {
    basic_salary: b,
    commute_allowance: ca,
    housing_allowance: ha,
    family_allowance: fa,
    position_allowance: pa,
    fixed_allowance: fxa,
    performance_bonus: pb,
    transport_allowance: ta,
    phone_allowance: pha,
    project_bonus: prjb,
    fixed_overtime_amount: foAmt,
    fixed_overtime_hours: row.fixed_overtime_hours || 0,
    gross_pay: grossPay,
    health_insurance_employee: healthIns,
    pension_employee: pension,
    employment_insurance_employee: employIns,
    care_insurance_employee: careIns,
    income_tax: incomeTax,
    monthly_resident_tax: residentTax,
    deduction_total: deductionTotal,
    net_pay: netPay,
    employer_cost_total: employerCost,
  }
  calcPreviewDialog.value = true
}

onMounted(() => { load(); loadDropdowns() })
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <div class="page-header">
      <h3>{{ t('payroll.jp.employees') }}</h3>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <el-button @click="openImport">{{ t('payroll.jp.import_employeeadmin') }}</el-button>
        <el-button type="primary" @click="openCreate">{{ t('action.create') }}</el-button>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <el-input v-model="searchText" :placeholder="t('action.search') + ' No/Name'" clearable style="width:200px" @input="page=1" />
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:220px" @change="page=1">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e)" :value="e.entity_id" />
      </el-select>
      <el-select v-model="filterSalaryType" :placeholder="t('field.salary_type')" clearable style="width:150px" @change="page=1">
        <el-option v-for="st in salaryTypes" :key="st" :label="st" :value="st" />
      </el-select>
      <el-select v-model="filterStatus" style="width:110px" @change="page=1">
        <el-option :label="t('status.all')" value="all" />
        <el-option :label="t('status.active')" value="active" />
        <el-option :label="t('status.inactive')" value="inactive" />
      </el-select>
    </div>

    <!-- Table -->
    <el-table :data="pagedRecords" v-loading="loading" border stripe size="small">
      <el-table-column prop="employee_number" :label="t('field.employee_number')" width="130" />
      <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="140" />
      <el-table-column prop="email" :label="t('field.email')" min-width="180" show-overflow-tooltip />
      <el-table-column prop="department_label" :label="t('field.department')" width="120" />
      <el-table-column prop="salary_type" :label="t('field.salary_type')" width="130" />
      <el-table-column prop="basic_salary" :label="t('field.basic_salary')" width="120" align="right">
        <template #default="{row}">{{ row.basic_salary ? Number(row.basic_salary).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="social_insurance_eligible" :label="t('field.social_insurance')" width="80" align="center">
        <template #default="{row}">
          <el-tag :type="row.social_insurance_eligible ? 'warning' : 'info'" size="small">
            {{ row.social_insurance_eligible ? t('field.yes') : t('field.no') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="employment_insurance_eligible" :label="t('field.employment_insurance')" width="80" align="center">
        <template #default="{row}">
          <el-tag :type="row.employment_insurance_eligible ? 'warning' : 'info'" size="small">
            {{ row.employment_insurance_eligible ? t('field.yes') : t('field.no') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="active" :label="t('field.active')" width="80" align="center">
        <template #default="{row}">
          <el-tag :type="row.active ? 'success' : 'danger'" size="small">
            {{ row.active ? t('status.active') : t('status.inactive') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="200" fixed="right">
        <template #default="{row}">
          <el-button size="small" text @click="openCalcPreview(row)">{{ t('payroll.jp.calc_preview') }}</el-button>
          <el-button size="small" text @click="openEdit(row)">{{ t('action.edit') }}</el-button>
          <el-button v-if="row.active" size="small" text type="danger" @click="openDeactivate(row.employee_id)">{{ t('action.deactivate') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination & Count -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
      <div class="helper-text">{{ t('action.showing_records', { shown: pagedRecords.length, total: filteredRecords.length }) }}</div>
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="filteredRecords.length" layout="prev, pager, next" small />
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? t('action.create') : t('action.edit')" width="780px" top="2vh">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('payroll.jp.tab_basic')" name="basic">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="t('field.employee_id')"><el-input v-model="form.employee_id" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.employee_number')"><el-input v-model="form.employee_number" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.employee_name')"><el-input v-model="form.employee_name" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.email')"><el-input v-model="form.email" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.entity_id')">
                <el-select v-model="form.entity_id" style="width:100%">
                  <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e)" :value="e.entity_id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.department')">
                <el-select v-model="form.department_label" style="width:100%" allow-create filterable>
                  <el-option v-for="d in departments" :key="d.department_id" :label="d.department_name_en || d.department_name_ja" :value="d.department_name_en || d.department_name_ja" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.team')">
                <el-select v-model="form.team_label" style="width:100%" allow-create filterable>
                  <el-option v-for="t in teams" :key="t.team_id" :label="t.team_name_en || t.team_name_ja" :value="t.team_name_en || t.team_name_ja" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.payroll_currency')">
                <el-select v-model="form.payroll_currency" style="width:100%">
                  <el-option label="JPY" value="JPY" />
                  <el-option label="USD" value="USD" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('payroll.jp.tab_salary')" name="salary">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="t('field.salary_type')">
                <el-select v-model="form.salary_type" style="width:100%">
                  <el-option v-for="st in salaryTypes" :key="st" :label="st" :value="st" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.basic_salary')">
                <el-input-number v-model="form.basic_salary" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.hourly_rate')">
                <el-input-number v-model="form.hourly_rate" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.daily_rate')">
                <el-input-number v-model="form.daily_rate" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.standard_work_days')">
                <el-input-number v-model="form.standard_work_days" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.standard_work_hours')">
                <el-input-number v-model="form.standard_work_hours" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.standard_monthly_hours')">
                <el-input-number v-model="form.standard_monthly_hours" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.fixed_overtime_hours')">
                <el-input-number v-model="form.fixed_overtime_hours" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.fixed_overtime_amount')">
                <el-input-number v-model="form.fixed_overtime_amount" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('payroll.jp.tab_allowances')" name="allowances">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="t('field.commute_allowance')">
                <el-input-number v-model="form.commute_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.housing_allowance')">
                <el-input-number v-model="form.housing_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.family_allowance')">
                <el-input-number v-model="form.family_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.position_allowance')">
                <el-input-number v-model="form.position_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.fixed_allowance')">
                <el-input-number v-model="form.fixed_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.transport_allowance')">
                <el-input-number v-model="form.transport_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.phone_allowance')">
                <el-input-number v-model="form.phone_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.performance_bonus')">
                <el-input-number v-model="form.performance_bonus" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.project_bonus')">
                <el-input-number v-model="form.project_bonus" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('payroll.jp.tab_insurance')" name="insurance">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="t('field.social_insurance')">
                <el-switch v-model="form.social_insurance_eligible" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.employment_insurance')">
                <el-switch v-model="form.employment_insurance_eligible" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('field.dependents_count')">
                <el-input-number v-model="form.dependents_count" :min="0" :max="20" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.prefecture_code')">
                <el-select v-model="form.prefecture_code" style="width:100%" filterable>
                  <el-option v-for="code in prefectureCodes" :key="code" :label="code" :value="code" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.monthly_resident_tax')">
                <el-input-number v-model="form.monthly_resident_tax" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane :label="t('payroll.jp.tab_bank')" name="bank">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="t('field.bank_name')"><el-input v-model="form.bank_name" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.bank_branch_name')"><el-input v-model="form.bank_branch_name" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.bank_account_type')">
                <el-select v-model="form.bank_account_type" style="width:100%">
                  <el-option v-for="bt in bankAccountTypes" :key="bt" :label="bt" :value="bt" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.bank_account_name')"><el-input v-model="form.bank_account_name" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="t('field.bank_account_number')"><el-input v-model="form.bank_account_number" /></el-form-item>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('action.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- Calc Preview Dialog -->
    <el-dialog v-model="calcPreviewDialog" :title="t('payroll.jp.calc_preview')" width="600px">
      <template v-if="calcPreviewResult">
        <h4 style="margin-top:0">{{ t('payroll.jp.earnings') }}</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('field.basic_salary')">{{ calcPreviewResult.basic_salary.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.commute_allowance')">{{ calcPreviewResult.commute_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.housing_allowance')">{{ calcPreviewResult.housing_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.family_allowance')">{{ calcPreviewResult.family_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.position_allowance')">{{ calcPreviewResult.position_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.fixed_allowance')">{{ calcPreviewResult.fixed_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.fixed_overtime_amount')">{{ calcPreviewResult.fixed_overtime_amount.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.performance_bonus')">{{ calcPreviewResult.performance_bonus.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.transport_allowance')">{{ calcPreviewResult.transport_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.phone_allowance')">{{ calcPreviewResult.phone_allowance.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.project_bonus')">{{ calcPreviewResult.project_bonus.toLocaleString() }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <h4>{{ t('payroll.jp.deductions') }}</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('field.health_insurance')">{{ calcPreviewResult.health_insurance_employee.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.pension')">{{ calcPreviewResult.pension_employee.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.employment_insurance')">{{ calcPreviewResult.employment_insurance_employee.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.care_insurance')">{{ calcPreviewResult.care_insurance_employee.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.income_tax')">{{ calcPreviewResult.income_tax.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item :label="t('field.monthly_resident_tax')">{{ calcPreviewResult.monthly_resident_tax.toLocaleString() }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('field.gross_pay')">
            <strong>{{ calcPreviewResult.gross_pay.toLocaleString() }}</strong>
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.deduction_total')">
            <strong>{{ calcPreviewResult.deduction_total.toLocaleString() }}</strong>
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.net_pay')">
            <strong style="color:var(--el-color-primary)">{{ calcPreviewResult.net_pay.toLocaleString() }}</strong>
          </el-descriptions-item>
          <el-descriptions-item :label="t('field.employer_cost_total')">
            <span style="color:var(--el-color-warning)">{{ calcPreviewResult.employer_cost_total.toLocaleString() }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="helper-text" style="margin-top:8px">
          {{ t('payroll.jp.calc_preview_notice') }}
        </div>
      </template>
      <template #footer>
        <el-button @click="calcPreviewDialog = false">{{ t('action.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialog" :title="t('payroll.jp.import_employeeadmin')" width="700px">
      <el-table
        :data="importableEmployees"
        max-height="400"
        @selection-change="(rows:any[]) => selectedImportIds = rows.map((r:any) => r.employee_id)"
        border stripe size="small"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="120" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" />
        <el-table-column prop="department" :label="t('field.department')" width="120" />
      </el-table>
      <template #footer>
        <el-button @click="importDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="importing" :disabled="selectedImportIds.length === 0" @click="importSelected">
          {{ t('action.import') }} ({{ selectedImportIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- Deactivate Dialog -->
    <el-dialog v-model="deactivateDialog" :title="t('action.deactivate')" width="400px">
      <p>{{ t('action.deactivate_confirm') }}</p>
      <el-input v-model="deactivateReason" :placeholder="t('action.deactivate_reason')" type="textarea" :rows="2" />
      <template #footer>
        <el-button @click="deactivateDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="danger" @click="confirmDeactivate">{{ t('action.deactivate') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
.helper-text { color: var(--el-text-color-secondary); font-size: 0.85rem; }
h4 { margin: 8px 0; font-size: 1rem; }
</style>
