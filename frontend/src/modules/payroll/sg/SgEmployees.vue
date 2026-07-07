<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollSgApi } from '@/api/client'
import { useDictOptions } from '@/composables/useDictOptions'
import { ElMessage } from 'element-plus'
import { usePayrollSgConstants } from '@/composables/usePayrollSgConstants'

const { t } = useI18n()
const { cpfAgeRanges, salaryTypes, init: initConstants } = usePayrollSgConstants()
const CAT = { SALARY_TYPE: 'salary_type', BANK_ACCOUNT: 'bank_account_type', CURRENCY: 'currency' }
const { loadOptions, getOptions, getValues } = useDictOptions()
const ddOptions = getOptions
const ddValues = getValues
const loading = ref(false)
const allRecords = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const searchText = ref('')
const filterEntity = ref('')
const filterSalaryType = ref('')
const filterStatus = ref('all')

// Edit drawer
const drawerVisible = ref(false)
const drawerRecord = ref<any>(null)
const drawerForm = ref<Record<string, any>>({})
const drawerSaving = ref(false)

// Import dialog
const importDialog = ref(false)
const importableEmployees = ref<any[]>([])
const selectedImportIds = ref<string[]>([])
const importing = ref(false)

// Toggle active/inactive
const toggleDialog = ref(false)
const toggleId = ref('')
const toggleName = ref('')
const toggleActive = ref(false)
const toggleReason = ref('')

// Dropdowns
const entities = ref<any[]>([])

// ── Load ──
async function load() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (searchText.value.trim()) params.search = searchText.value.trim()
    if (filterEntity.value) params.entity_id = filterEntity.value
    if (filterSalaryType.value) params.salary_type = filterSalaryType.value
    if (filterStatus.value !== 'all') params.status = filterStatus.value
    const res = await payrollSgApi.employees(params)
    allRecords.value = (res.data?.data || res.data || []) as any[]
    total.value = res.data?.pagination?.total || allRecords.value.length
  } catch (e: any) { ElMessage.error(e.message) } finally { loading.value = false }
}
function applyFilter() { page.value = 1; load() }
function handlePageChange(p: number) { page.value = p; load() }
function handleSizeChange(s: number) { pageSize.value = s; page.value = 1; load() }

async function loadDropdowns() {
  try {
    const er = await payrollSgApi.entities()
    entities.value = (er.data?.data || er.data || []) as any[]
  } catch (_) {}
}

function entityLabelById(id: string) {
  const f = entities.value.find((e: any) => e.entity_id === id || e.entity_code === id)
  return f ? `${f.entity_code || id} - ${f.entity_name_en || f.entity_name || ''}` : id
}

function salaryTypeLabel(st: string): string {
  const f = ddOptions(CAT.SALARY_TYPE).value.find((o: any) => o.value === st)
  return f ? f.label : (st || '—')
}

// ── Edit Drawer ──
function openDetail(row: any) {
  drawerRecord.value = row
  drawerForm.value = { ...row }
  drawerVisible.value = true
}
async function saveDrawer() {
  drawerSaving.value = true
  try {
    await payrollSgApi.saveEmployee(drawerForm.value)
    drawerVisible.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) } finally { drawerSaving.value = false }
}

// ── Import ──
async function openImport() {
  importDialog.value = true
  selectedImportIds.value = []
  try {
    const res = await payrollSgApi.importableEmployees()
    importableEmployees.value = (res.data?.data || res.data || []) as any[]
  } catch (e: any) { ElMessage.error('Failed to load importable employees') }
}
async function doImport() {
  if (selectedImportIds.value.length === 0) return
  importing.value = true
  try {
    const res = await payrollSgApi.importEmployees({ employee_ids: selectedImportIds.value })
    ElMessage.success(t('payroll.sg.imported', { count: (res.data || res).imported }))
    importDialog.value = false; load()
  } catch (e: any) { ElMessage.error(e.message) } finally { importing.value = false }
}

// ── Toggle ──
function openToggle(row: any) {
  toggleId.value = row.employee_id
  toggleName.value = row.employee_name || row.employee_number || ''
  toggleActive.value = row.active !== false && row.active !== 'false' && row.active !== 0 && row.active !== '0'
  toggleReason.value = ''
  toggleDialog.value = true
}
async function confirmToggle() {
  try {
    if (toggleActive.value) {
      await payrollSgApi.activateEmployee(toggleId.value)
      ElMessage.success(t('action.activated'))
    } else {
      await payrollSgApi.deactivateEmployee(toggleId.value, { deactivation_reason: toggleReason.value })
      ElMessage.success(t('action.deactivated'))
    }
    toggleDialog.value = false; await load()
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(() => { initConstants(); load(); loadDropdowns(); loadOptions([CAT.SALARY_TYPE, CAT.BANK_ACCOUNT, CAT.CURRENCY]) })

const fmt = (v: number) => v ? `SGD ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '-'
</script>

<template>
  <div class="fiori-page">
    <!-- Toolbar -->
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.sg.salary_master') }}</h2>
      </div>
      <el-button @click="openImport" size="default">{{ t('payroll.sg.import_employeeadmin') }}</el-button>
    </div>

    <!-- Filters -->
    <div class="fiori-filters">
      <el-input v-model="searchText" placeholder="搜索员工编号、姓名…" clearable style="width:220px" @keyup.enter="applyFilter" @clear="applyFilter" />
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:260px" @change="applyFilter">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabelById(e.entity_id)" :value="e.entity_id" />
      </el-select>
      <el-select v-model="filterSalaryType" :placeholder="t('field.salary_type_label')" clearable style="width:180px" @change="applyFilter">
        <el-option v-for="o in ddOptions(CAT.SALARY_TYPE).value" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="filterStatus" style="width:120px" @change="applyFilter">
        <el-option :label="'All'" value="all" />
        <el-option :label="t('entity.status.active')" value="active" />
        <el-option :label="t('entity.status.inactive')" value="inactive" />
      </el-select>
    </div>

    <!-- Table -->
    <div class="fiori-card">
      <el-table :data="allRecords" v-loading="loading" border stripe size="small" class="fiori-table">
        <el-table-column type="index" min-width="45" fixed="left" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="120" fixed="left">
          <template #default="{row}"><span class="emp-num">{{ row.employee_number || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="140" fixed="left" show-overflow-tooltip>
          <template #default="{row}"><span class="emp-name">{{ row.employee_name || '-' }}</span></template>
        </el-table-column>
        <!-- Info -->
        <el-table-column :label="t('field.entity_id')" min-width="230" show-overflow-tooltip>
          <template #default="{row}">{{ entityLabelById(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column prop="department_label" :label="t('field.department')" min-width="120" show-overflow-tooltip />
        <el-table-column prop="email" :label="t('field.email')" min-width="200" show-overflow-tooltip />
        <el-table-column :label="t('field.active')" min-width="70" align="center">
          <template #default="{row}"><span class="dot" :class="row.active ? 'dot-on' : 'dot-off'" /></template>
        </el-table-column>
        <!-- Salary -->
        <el-table-column :label="t('field.salary_type_label')" min-width="120">
          <template #default="{row}"><el-tag size="small">{{ salaryTypeLabel(row.salary_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('field.salary_type_label')" min-width="140" align="right">
          <template #default="{row}">
            {{ fmt(row.salary_type === 'daily' ? row.daily_rate : row.basic_salary) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('field.fixed_allowance')" min-width="130" align="right">
          <template #default="{row}">{{ fmt(row.fixed_allowance) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.performance_bonus')" min-width="130" align="right">
          <template #default="{row}">{{ fmt(row.performance_bonus) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.other_allowance')" min-width="130" align="right">
          <template #default="{row}">{{ fmt(row.other_allowance) }}</template>
        </el-table-column>
        <!-- CPF -->
        <el-table-column :label="'CPF'" min-width="60" align="center">
          <template #default="{row}"><span class="dot" :class="row.cpf_applicable !== false ? 'dot-on' : 'dot-off'" /></template>
        </el-table-column>
        <el-table-column prop="employee_age_range" :label="t('field.cpf_age_range')" min-width="90" align="center" />
        <el-table-column :label="t('field.standard_work_days')" min-width="100" align="right">
          <template #default="{row}">{{ row.standard_work_days != null ? row.standard_work_days : '-' }}</template>
        </el-table-column>
        <!-- Bank -->
        <el-table-column :label="t('field.bank_name')" min-width="140" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_name || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.bank_account_number')" min-width="130" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_account_number || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.notes')" min-width="150" show-overflow-tooltip>
          <template #default="{row}">{{ row.notes || '-' }}</template>
        </el-table-column>
        <!-- Actions -->
        <el-table-column :label="t('field.actions')" min-width="160" fixed="right" align="center">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="openDetail(row)">{{ t('action.edit') }}</el-button>
            <el-button size="small" text :type="row.active ? 'danger' : 'success'" @click="openToggle(row)">
              {{ row.active ? t('action.deactivate') : t('action.activate') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
        <span class="helper-text">{{ total }} {{ t('action.records_total') }}</span>
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
    </div>

    <!-- Edit Drawer -->
    <el-drawer v-model="drawerVisible" :title="t('action.edit')" size="600px">
      <div class="drawer-header" v-if="drawerRecord">
        <div class="drawer-name">{{ drawerRecord?.employee_name }}</div>
        <div class="drawer-meta">{{ drawerRecord?.employee_number }} · {{ entityLabelById(drawerRecord?.entity_id) }}</div>
      </div>
      <el-form :model="drawerForm" label-width="150px" size="small" class="drawer-form">
        <h4>Basic Info / 基本信息</h4>
        <el-form-item :label="t('field.employee_id')"><el-input v-model="drawerForm.employee_id" disabled /></el-form-item>
        <el-form-item :label="t('field.employee_number')"><el-input v-model="drawerForm.employee_number" /></el-form-item>
        <el-form-item :label="t('field.employee_name')"><el-input v-model="drawerForm.employee_name" /></el-form-item>
        <el-form-item :label="t('field.email')"><el-input v-model="drawerForm.email" /></el-form-item>
        <el-form-item :label="t('field.entity')"><el-input v-model="drawerForm.entity_id" /></el-form-item>
        <el-form-item :label="t('field.department')"><el-input v-model="drawerForm.department_label" /></el-form-item>

        <h4>Salary / 工资</h4>
        <el-form-item :label="t('field.salary_type')">
          <el-select v-model="drawerForm.salary_type">
            <el-option v-for="o in ddOptions(CAT.SALARY_TYPE).value" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="drawerForm.salary_type === 'monthly'" :label="t('field.basic_salary')">
          <el-input-number v-model="drawerForm.basic_salary" :min="0" :step="100" style="width:200px" />
        </el-form-item>
        <el-form-item v-if="drawerForm.salary_type === 'daily'" :label="t('field.daily_rate')">
          <el-input-number v-model="drawerForm.daily_rate" :min="0" :step="10" style="width:200px" />
        </el-form-item>
        <el-form-item :label="t('field.standard_work_days')">
          <el-input-number v-model="drawerForm.standard_work_days" :min="1" :max="31" style="width:150px" />
        </el-form-item>

        <h4>Allowances / 津贴</h4>
        <el-form-item label="Fixed Allowance"><el-input-number v-model="drawerForm.fixed_allowance" :min="0" style="width:200px" /></el-form-item>
        <el-form-item label="Performance Bonus"><el-input-number v-model="drawerForm.performance_bonus" :min="0" style="width:200px" /></el-form-item>
        <el-form-item label="Other Allowance"><el-input-number v-model="drawerForm.other_allowance" :min="0" style="width:200px" /></el-form-item>

        <h4>CPF Settings / CPF设置</h4>
        <el-form-item label="CPF Applicable"><el-switch v-model="drawerForm.cpf_applicable" /></el-form-item>
        <el-form-item label="CPF Mode">
          <el-radio-group v-model="drawerForm.cpf_input_mode">
            <el-radio value="auto">Auto</el-radio>
            <el-radio value="manual">Manual</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="drawerForm.cpf_input_mode === 'manual'">
          <el-form-item label="CPF EE (Manual)"><el-input-number v-model="drawerForm.cpf_employee_manual" :min="0" style="width:200px" /></el-form-item>
          <el-form-item label="CPF ER (Manual)"><el-input-number v-model="drawerForm.cpf_employer_manual" :min="0" style="width:200px" /></el-form-item>
        </template>
        <el-form-item label="Age Range">
          <el-select v-model="drawerForm.employee_age_range">
            <el-option v-for="r in cpfAgeRanges" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>

        <h4>Bank Info / 银行信息</h4>
        <el-form-item :label="t('field.bank_name')"><el-input v-model="drawerForm.bank_name" /></el-form-item>
        <el-form-item :label="t('field.bank_branch_name')"><el-input v-model="drawerForm.bank_branch_name" /></el-form-item>
        <el-form-item :label="t('field.bank_account_type')"><el-input v-model="drawerForm.bank_account_type" /></el-form-item>
        <el-form-item :label="t('field.bank_account_name')"><el-input v-model="drawerForm.bank_account_name" /></el-form-item>
        <el-form-item :label="t('field.bank_account_number')"><el-input v-model="drawerForm.bank_account_number" /></el-form-item>
        <el-form-item :label="t('field.notes')"><el-input v-model="drawerForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveDrawer" :loading="drawerSaving">{{ t('common.save') }}</el-button>
      </template>
    </el-drawer>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialog" :title="t('payroll.sg.import_employeeadmin')" width="720px">
      <div class="fiori-filters" style="margin-bottom:12px">
        <el-input v-model="searchText" placeholder="搜索员工编号、姓名…" clearable style="width:200px" />
      </div>
      <el-table :data="importableEmployees" max-height="420" size="small" @selection-change="(rows: any[]) => selectedImportIds = rows.map((r: any) => r.employee_id)">
        <el-table-column type="selection" min-width="45" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="130" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="160" />
        <el-table-column :label="t('field.entity_id')" min-width="220">
          <template #default="{row}">{{ entityLabelById(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.department')" min-width="140">
          <template #default="{row}">{{ row.department_name || row.department || '-' }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="importDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="doImport" :loading="importing" :disabled="selectedImportIds.length === 0">
          {{ t('action.import') }} ({{ selectedImportIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- Toggle (Deactivate/Activate) Dialog -->
    <el-dialog v-model="toggleDialog" :title="toggleActive ? t('action.deactivate') : t('action.activate')" width="420px">
      <p style="margin-bottom:12px">{{ toggleName }}</p>
      <el-form-item v-if="!toggleActive" :label="t('action.deactivate_reason')">
        <el-input v-model="toggleReason" type="textarea" :rows="2" />
      </el-form-item>
      <template #footer>
        <el-button @click="toggleDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmToggle">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1600px; margin: 0 auto; padding: 24px; font-size: 15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.fiori-toolbar h2 { margin:0; font-size:1.25rem; font-weight:700; color:#1d2a3a; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.fiori-table { width:100% !important; }
.fiori-table :deep(.el-table__body-wrapper) { overflow-x:auto !important; }
.emp-num { font-weight:700; color:#1d2a3a; }
.emp-name { font-weight:650; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%; }
.dot-on { background:#10b981; }
.dot-off { background:#d1d5db; }
.helper-text { color:#6b7280; font-size:.85rem; }
.drawer-header { margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid #e5e7eb; }
.drawer-name { font-weight:700; font-size:1.05rem; }
.drawer-meta { font-size:.82rem; color:#6b7280; }
.drawer-form h4 { margin:16px 0 8px; padding-bottom:4px; border-bottom:1px solid #e5e7eb; font-size:.9rem; color:#1d2a3a; font-weight:700; }
</style>
