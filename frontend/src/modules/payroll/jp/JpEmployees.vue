<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const loading = ref(false)
const allRecords = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)

const itemDefs = ref<any[]>([])
const editableItemCodes = [10, 11, 12, 13, 15, 18, 19]

const searchText = ref('')
const filterEntity = ref('')
const filterSalaryType = ref('')
const filterStatus = ref('all')
const filterDepartment = ref('')

const drawerVisible = ref(false)
const drawerRecord = ref<any>(null)
const drawerForm = ref<Record<string, any>>({})
const drawerSaving = ref(false)

const importDialog = ref(false)
const importableEmployees = ref<any[]>([])
const selectedImportIds = ref<string[]>([])
const importing = ref(false)
const importFilterEntity = ref('')
const importFilterDept = ref('')
const importSearch = ref('')

const toggleDialog = ref(false)
const toggleId = ref('')
const toggleName = ref('')
const toggleActive = ref(false)
const toggleReason = ref('')

const entities = ref<any[]>([])
const departments = ref<any[]>([])
const teams = ref<any[]>([])

const salaryTypes = [
  { value: 'monthly', label: 'payroll.jp.salary_type_monthly' },
  { value: 'hourly', label: 'payroll.jp.salary_type_hourly' },
  { value: 'daily', label: 'payroll.jp.salary_type_daily' },
  { value: 'monthly_fixed_ot', label: 'payroll.jp.salary_type_monthly_fixed_ot' },
  { value: 'monthly_hour', label: 'payroll.jp.salary_type_monthly_hour' },
]
const bankAccountTypes = ['普通預金', '当座預金', '定期預金']
const prefectureCodes = Array.from({ length: 47 }, (_, i) => String(i + 1).padStart(2, '0'))

function getItemLabel(item: any): string {
  try { const labels = typeof item.labels === 'string' ? JSON.parse(item.labels) : item.labels; return labels?.ja || labels?.en || item.code || '' } catch { return item.code || '' }
}
const editableItems = computed(() => itemDefs.value.filter((i: any) => editableItemCodes.includes(i.display_order)))

const filteredRecords = computed(() => {
  let result = allRecords.value
  if (searchText.value) { const q = searchText.value.toLowerCase(); result = result.filter((r: any) => (r.employee_number || '').toLowerCase().includes(q) || (r.employee_name || '').toLowerCase().includes(q)) }
  if (filterEntity.value) result = result.filter((r: any) => r.entity_id === filterEntity.value)
  if (filterSalaryType.value) result = result.filter((r: any) => r.salary_type === filterSalaryType.value)
  if (filterDepartment.value) result = result.filter((r: any) => r.department_label === filterDepartment.value)
  if (filterStatus.value === 'active') result = result.filter((r: any) => r.active)
  if (filterStatus.value === 'inactive') result = result.filter((r: any) => !r.active)
  return result
})
const pagedRecords = computed(() => { const s = (page.value - 1) * pageSize.value; return filteredRecords.value.slice(s, s + pageSize.value) })
const departmentOptions = computed(() => [...new Set(allRecords.value.map((r: any) => r.department_label).filter(Boolean))])

async function load() { loading.value = true; try { const res = await payrollJpApi.employees(); allRecords.value = res.data.data?.items || res.data.data || [] } catch (e: any) { ElMessage.error(e.message) } finally { loading.value = false } }
async function loadItemDefs() { try { const res = await payrollJpApi.itemDefinitions(); itemDefs.value = res.data.data?.items || res.data.data || [] } catch (_) {} }
async function loadDropdowns() { try { const [er, dr, tr] = await Promise.all([fetch('/api/masterdata/entities').then(r => r.json()), fetch('/api/masterdata/departments').then(r => r.json()), fetch('/api/masterdata/teams').then(r => r.json())]); entities.value = er.data || []; departments.value = dr.data || []; teams.value = tr.data || [] } catch (_) {} }
function entityLabel(e: any) { if (!e) return ''; const code = e.entity_code || ''; const name = e.entity_name || ''; const country = e.country || ''; return code ? `${code} - ${name} (${country})` : e.entity_id || '' }
function entityLabelById(id: string) { const f = entities.value.find((e: any) => e.entity_id === id); return f ? entityLabel(f) : id }
function salaryTypeLabel(st: string): string { const f = salaryTypes.find(s => s.value === st); return f ? t(f.label) : st }

function openDetail(row: any) { drawerRecord.value = row; drawerForm.value = { ...row }; drawerVisible.value = true }
async function saveDrawer() { drawerSaving.value = true; try { await payrollJpApi.saveEmployee(drawerForm.value); drawerVisible.value = false; ElMessage.success(t('action.saved')); await load() } catch (e: any) { ElMessage.error(e.message) } finally { drawerSaving.value = false } }

async function openImport() { importDialog.value = true; selectedImportIds.value = []; importFilterEntity.value = ''; importFilterDept.value = ''; importSearch.value = ''; try { const res = await payrollJpApi.importableEmployees(); importableEmployees.value = res.data.data?.items || res.data.data || [] } catch { try { const res = await fetch('/api/employees').then(r => r.json()); importableEmployees.value = (res.data?.items || res.data || []).filter((e: any) => e.country_code === 'JP' || !e.country_code) } catch { importableEmployees.value = [] } } }
const filteredImportable = computed(() => { let result = importableEmployees.value; if (importFilterEntity.value) result = result.filter((e: any) => e.entity_id === importFilterEntity.value); if (importFilterDept.value) result = result.filter((e: any) => (e.department_name || e.department || '') === importFilterDept.value); if (importSearch.value) { const q = importSearch.value.toLowerCase(); result = result.filter((e: any) => (e.employee_number || e.employee_no || '').toLowerCase().includes(q) || (e.employee_name || '').toLowerCase().includes(q)) } return result })
async function importSelected() { if (!selectedImportIds.value.length) return; importing.value = true; try { await payrollJpApi.importEmployees({ employee_ids: selectedImportIds.value }); importDialog.value = false; ElMessage.success(t('payroll.jp.import_success', { count: selectedImportIds.value.length })); await load() } catch (e: any) { ElMessage.error(e.message) } finally { importing.value = false } }

function openToggle(row: any) { toggleId.value = row.employee_id; toggleName.value = row.employee_name || row.employee_number || ''; toggleActive.value = !row.active; toggleReason.value = ''; toggleDialog.value = true }
async function confirmToggle() {
  try {
    if (toggleActive.value) {
      await payrollJpApi.activateEmployee(toggleId.value)
      ElMessage.success(t('action.activated'))
    } else {
      await payrollJpApi.deactivateEmployee(toggleId.value, { deactivation_reason: toggleReason.value })
      ElMessage.success(t('action.deactivated'))
    }
    toggleDialog.value = false; await load()
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(() => { load(); loadItemDefs(); loadDropdowns() })
</script>

<template>
  <div class="fiori-page">
    <!-- Toolbar -->
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.employees') }}</h2>
      </div>
      <el-button @click="openImport" size="default">{{ t('payroll.jp.import_employeeadmin') }}</el-button>
    </div>

    <!-- Filters -->
    <div class="fiori-filters">
      <el-input v-model="searchText" :placeholder="t('action.search')" clearable style="width:200px" @input="page=1" />
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:260px" @change="page=1">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e)" :value="e.entity_id" />
      </el-select>
      <el-select v-model="filterDepartment" :placeholder="t('field.department')" clearable style="width:150px" @change="page=1">
        <el-option v-for="d in departmentOptions" :key="d" :label="d" :value="d" />
      </el-select>
      <el-select v-model="filterSalaryType" :placeholder="t('field.salary_type_label')" clearable style="width:180px" @change="page=1">
        <el-option v-for="st in salaryTypes" :key="st.value" :label="t(st.label)" :value="st.value" />
      </el-select>
      <el-select v-model="filterStatus" style="width:120px" @change="page=1">
        <el-option :label="t('status.all')" value="all" />
        <el-option :label="t('status.active')" value="active" />
        <el-option :label="t('status.inactive')" value="inactive" />
      </el-select>
    </div>

    <!-- Table -->
    <div class="fiori-card">
      <el-table :data="pagedRecords" v-loading="loading" border stripe size="small" class="fiori-table">
        <el-table-column type="index" min-width="45" fixed="left" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="120" fixed="left">
          <template #default="{row}"><span class="emp-num">{{ row.employee_number || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="140" fixed="left" show-overflow-tooltip>
          <template #default="{row}"><span class="emp-name">{{ row.employee_name || '-' }}</span></template>
        </el-table-column>
        <!-- Basic Info -->
        <el-table-column :label="t('field.entity_id')" min-width="230" show-overflow-tooltip>
          <template #default="{row}">{{ entityLabelById(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column prop="department_label" :label="t('field.department')" min-width="120" show-overflow-tooltip />
        <el-table-column prop="team_label" :label="t('field.team')" min-width="120" show-overflow-tooltip />
        <el-table-column prop="email" :label="t('field.email')" min-width="200" show-overflow-tooltip />
        <el-table-column prop="payroll_currency" :label="t('field.payroll_currency')" min-width="80" align="center" />
        <el-table-column :label="t('field.active')" min-width="70" align="center">
          <template #default="{row}"><span class="dot" :class="row.active?'dot-on':'dot-off'" /></template>
        </el-table-column>
        <!-- Salary Settings -->
        <el-table-column :label="t('field.salary_type_label')" min-width="130">
          <template #default="{row}"><el-tag size="small">{{ salaryTypeLabel(row.salary_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('field.standard_work_hours')" min-width="100" align="right">
          <template #default="{row}">{{ row.standard_work_hours != null ? row.standard_work_hours : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.standard_monthly_hours')" min-width="100" align="right">
          <template #default="{row}">{{ row.standard_monthly_hours != null ? row.standard_monthly_hours : '-' }}</template>
        </el-table-column>
        <!-- Item Components -->
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 10) || {}) || t('field.basic_salary')" min-width="120" align="right">
          <template #default="{row}">{{ row.basic_salary ? '¥' + Number(row.basic_salary).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 11) || {}) || t('field.hourly_rate')" min-width="110" align="right">
          <template #default="{row}">{{ row.hourly_rate ? '¥' + Number(row.hourly_rate).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 12) || {}) || t('field.daily_rate')" min-width="110" align="right">
          <template #default="{row}">{{ row.daily_rate ? '¥' + Number(row.daily_rate).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 13) || {}) || t('field.transport_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.transport_allowance ? '¥' + Number(row.transport_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 15) || {}) || t('field.overtime_hourly_rate')" min-width="110" align="right">
          <template #default="{row}">{{ row.overtime_hourly_rate ? '¥' + Number(row.overtime_hourly_rate).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 18) || {}) || t('field.performance_bonus')" min-width="110" align="right">
          <template #default="{row}">{{ row.performance_bonus ? '¥' + Number(row.performance_bonus).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="getItemLabel(editableItems.find((i:any) => i.display_order === 19) || {}) || t('field.recurring_deductions')" min-width="110" align="right">
          <template #default="{row}">{{ row.recurring_deductions ? '¥' + Number(row.recurring_deductions).toLocaleString() : '-' }}</template>
        </el-table-column>
        <!-- Allowances -->
        <el-table-column :label="t('field.commute_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.commute_allowance ? '¥' + Number(row.commute_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.housing_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.housing_allowance ? '¥' + Number(row.housing_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.family_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.family_allowance ? '¥' + Number(row.family_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.position_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.position_allowance ? '¥' + Number(row.position_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.fixed_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.fixed_allowance ? '¥' + Number(row.fixed_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.fixed_overtime_amount')" min-width="110" align="right">
          <template #default="{row}">{{ row.fixed_overtime_amount ? '¥' + Number(row.fixed_overtime_amount).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.phone_allowance')" min-width="110" align="right">
          <template #default="{row}">{{ row.phone_allowance ? '¥' + Number(row.phone_allowance).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.project_bonus')" min-width="110" align="right">
          <template #default="{row}">{{ row.project_bonus ? '¥' + Number(row.project_bonus).toLocaleString() : '-' }}</template>
        </el-table-column>
        <!-- Insurance & Tax -->
        <el-table-column :label="t('field.social_insurance')" min-width="70" align="center">
          <template #default="{row}"><span class="dot" :class="row.social_insurance_eligible?'dot-on':'dot-off'" /></template>
        </el-table-column>
        <el-table-column :label="t('field.employment_insurance')" min-width="70" align="center">
          <template #default="{row}"><span class="dot" :class="row.employment_insurance_eligible?'dot-on':'dot-off'" /></template>
        </el-table-column>
        <el-table-column :label="t('field.dependents_count')" min-width="80" align="right">
          <template #default="{row}">{{ row.dependents_count != null ? row.dependents_count : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.prefecture_code')" min-width="85" align="center">
          <template #default="{row}">{{ row.prefecture_code || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.monthly_resident_tax')" min-width="120" align="right">
          <template #default="{row}">{{ row.monthly_resident_tax ? '¥' + Number(row.monthly_resident_tax).toLocaleString() : '-' }}</template>
        </el-table-column>
        <!-- Bank Info -->
        <el-table-column :label="t('field.bank_name')" min-width="150" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_name || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.bank_branch_name')" min-width="130" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_branch_name || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.bank_account_type')" min-width="100" align="center">
          <template #default="{row}">{{ row.bank_account_type || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.bank_account_name')" min-width="150" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_account_name || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.bank_account_number')" min-width="130" show-overflow-tooltip>
          <template #default="{row}">{{ row.bank_account_number || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.notes')" min-width="160" show-overflow-tooltip>
          <template #default="{row}">{{ row.notes || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="160" fixed="right" align="center">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="openDetail(row)">{{ t('action.edit') }}</el-button>
            <el-button size="small" text :type="row.active ? 'danger' : 'success'" @click="openToggle(row)">{{ row.active ? t('action.deactivate') : t('action.activate') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
        <span class="helper-text">{{ filteredRecords.length }} {{ t('action.records_total') }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredRecords.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
          small
          @size-change="(s:number)=>{pageSize=s;page=1}"
        />
      </div>
    </div>

    <!-- Detail Drawer -->
    <el-drawer v-model="drawerVisible" direction="rtl" size="600px" :close-on-click-modal="false">
      <template #header>
        <div class="drawer-head">
          <div class="drawer-avatar">{{ (drawerRecord?.employee_name||'?').charAt(0) }}</div>
          <div><div class="drawer-name">{{ drawerRecord?.employee_name }}</div><div class="drawer-meta">{{ drawerRecord?.employee_number }} · {{ entityLabelById(drawerRecord?.entity_id) }}</div></div>
        </div>
      </template>
      <div class="drawer-body" v-if="drawerRecord">
        <!-- Card 1: Basic -->
        <div class="fi-card"><div class="fi-card-head"><span>📋</span> {{ t('payroll.jp.tab_basic') }}</div>
          <el-row :gutter="16">
            <el-col :span="12"><label>{{ t('field.email') }}</label><el-input v-model="drawerForm.email" size="small" /></el-col>
            <el-col :span="12"><label>{{ t('field.payroll_currency') }}</label><el-select v-model="drawerForm.payroll_currency" size="small" style="width:100%"><el-option label="JPY" value="JPY" /><el-option label="USD" value="USD" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.department') }}</label><el-select v-model="drawerForm.department_label" size="small" style="width:100%" allow-create filterable clearable><el-option v-for="d in departments" :key="d.department_id" :label="d.department_name_en||d.department_name_ja" :value="d.department_name_en||d.department_name_ja" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.team') }}</label><el-select v-model="drawerForm.team_label" size="small" style="width:100%" allow-create filterable clearable><el-option v-for="tm in teams" :key="tm.team_id" :label="tm.team_name_en||tm.team_name_ja" :value="tm.team_name_en||tm.team_name_ja" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.active') }}</label><div><el-switch v-model="drawerForm.active" size="small" /></div></el-col>
          </el-row>
        </div>
        <!-- Card 2: Salary -->
        <div class="fi-card"><div class="fi-card-head"><span>💰</span> {{ t('payroll.jp.tab_salary') }}</div>
          <el-row :gutter="16">
            <el-col :span="12"><label>{{ t('field.salary_type_label') }}</label><el-select v-model="drawerForm.salary_type" size="small" style="width:100%"><el-option v-for="st in salaryTypes" :key="st.value" :label="t(st.label)" :value="st.value" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.standard_work_hours') }}</label><el-input-number v-model="drawerForm.standard_work_hours" :min="0" :precision="1" size="small" style="width:100%" /></el-col>
            <el-col :span="12"><label>{{ t('field.standard_monthly_hours') }}</label><el-input-number v-model="drawerForm.standard_monthly_hours" :min="0" :precision="1" size="small" style="width:100%" /></el-col>
          </el-row>
        </div>
        <!-- Card 3: Item Components -->
        <div class="fi-card"><div class="fi-card-head"><span>🧾</span> {{ t('payroll.jp.item_definitions') }}</div>
          <el-row :gutter="16">
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===10)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===10)) }}</label><el-input-number v-model="drawerForm.basic_salary" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===11)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===11)) }}</label><el-input-number v-model="drawerForm.hourly_rate" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===12)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===12)) }}</label><el-input-number v-model="drawerForm.daily_rate" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===13)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===13)) }}</label><el-input-number v-model="drawerForm.transport_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===15)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===15)) }}</label><el-input-number v-model="drawerForm.overtime_hourly_rate" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===18)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===18)) }}</label><el-input-number v-model="drawerForm.performance_bonus" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8" v-if="editableItems.find((i:any)=>i.display_order===19)"><label>{{ getItemLabel(editableItems.find((i:any)=>i.display_order===19)) }}</label><el-input-number v-model="drawerForm.recurring_deductions" :min="0" size="small" style="width:100%" /></el-col>
          </el-row>
        </div>
        <!-- Card 4: Allowances -->
        <div class="fi-card"><div class="fi-card-head"><span>🎁</span> {{ t('payroll.jp.tab_allowances') }}</div>
          <el-row :gutter="16">
            <el-col :span="8"><label>{{ t('field.commute_allowance') }}</label><el-input-number v-model="drawerForm.commute_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.housing_allowance') }}</label><el-input-number v-model="drawerForm.housing_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.family_allowance') }}</label><el-input-number v-model="drawerForm.family_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.position_allowance') }}</label><el-input-number v-model="drawerForm.position_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.fixed_allowance') }}</label><el-input-number v-model="drawerForm.fixed_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.fixed_overtime_amount') }}</label><el-input-number v-model="drawerForm.fixed_overtime_amount" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.phone_allowance') }}</label><el-input-number v-model="drawerForm.phone_allowance" :min="0" size="small" style="width:100%" /></el-col>
            <el-col :span="8"><label>{{ t('field.project_bonus') }}</label><el-input-number v-model="drawerForm.project_bonus" :min="0" size="small" style="width:100%" /></el-col>
          </el-row>
        </div>
        <!-- Card 5: Insurance -->
        <div class="fi-card"><div class="fi-card-head"><span>🏥</span> {{ t('payroll.jp.tab_insurance') }}</div>
          <el-row :gutter="16">
            <el-col :span="8"><label>{{ t('field.social_insurance') }}</label><div><el-switch v-model="drawerForm.social_insurance_eligible" size="small" /></div></el-col>
            <el-col :span="8"><label>{{ t('field.employment_insurance') }}</label><div><el-switch v-model="drawerForm.employment_insurance_eligible" size="small" /></div></el-col>
            <el-col :span="8"><label>{{ t('field.dependents_count') }}</label><el-input-number v-model="drawerForm.dependents_count" :min="0" :max="20" size="small" style="width:100%" /></el-col>
            <el-col :span="12"><label>{{ t('field.prefecture_code') }}</label><el-select v-model="drawerForm.prefecture_code" size="small" style="width:100%" filterable><el-option v-for="code in prefectureCodes" :key="code" :label="code" :value="code" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.monthly_resident_tax') }}</label><el-input-number v-model="drawerForm.monthly_resident_tax" :min="0" size="small" style="width:100%" /></el-col>
          </el-row>
        </div>
        <!-- Card 6: Bank -->
        <div class="fi-card"><div class="fi-card-head"><span>🏦</span> {{ t('payroll.jp.tab_bank') }}</div>
          <el-row :gutter="16">
            <el-col :span="12"><label>{{ t('field.bank_name') }}</label><el-input v-model="drawerForm.bank_name" size="small" /></el-col>
            <el-col :span="12"><label>{{ t('field.bank_branch_name') }}</label><el-input v-model="drawerForm.bank_branch_name" size="small" /></el-col>
            <el-col :span="12"><label>{{ t('field.bank_account_type') }}</label><el-select v-model="drawerForm.bank_account_type" size="small" style="width:100%"><el-option v-for="bt in bankAccountTypes" :key="bt" :label="bt" :value="bt" /></el-select></el-col>
            <el-col :span="12"><label>{{ t('field.bank_account_name') }}</label><el-input v-model="drawerForm.bank_account_name" size="small" /></el-col>
            <el-col :span="12"><label>{{ t('field.bank_account_number') }}</label><el-input v-model="drawerForm.bank_account_number" size="small" /></el-col>
          </el-row>
          <div style="margin-top:10px"><label>{{ t('field.notes') }}</label><el-input v-model="drawerForm.notes" type="textarea" :rows="2" size="small" /></div>
        </div>
      </div>
      <template #footer><el-button @click="drawerVisible=false">{{ t('action.cancel') }}</el-button><el-button type="primary" :loading="drawerSaving" @click="saveDrawer">{{ t('action.save') }}</el-button></template>
    </el-drawer>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialog" :title="t('payroll.jp.import_employeeadmin')" width="750px" top="2vh">
      <div class="fiori-filters" style="margin-bottom:12px">
        <el-input v-model="importSearch" :placeholder="t('action.search')" clearable style="width:180px" />
        <el-select v-model="importFilterEntity" :placeholder="t('field.entity_id')" clearable style="width:220px"><el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e)" :value="e.entity_id" /></el-select>
        <el-select v-model="importFilterDept" :placeholder="t('field.department')" clearable style="width:160px"><el-option v-for="d in departments" :key="d.department_id" :label="d.department_name_en||d.department_name_ja" :value="d.department_name_en||d.department_name_ja" /></el-select>
      </div>
      <el-table :data="filteredImportable" max-height="400" @selection-change="(rows:any[])=>selectedImportIds=rows.map((r:any)=>r.employee_id)" border stripe size="small">
        <el-table-column type="selection" min-width="45" /><el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="130" /><el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="160" /><el-table-column :label="t('field.entity_id')" min-width="220"><template #default="{row}">{{ entityLabelById(row.entity_id) }}</template></el-table-column><el-table-column :label="t('field.department')" min-width="140"><template #default="{row}">{{ row.department_name||row.department||'-' }}</template></el-table-column>
      </el-table>
      <div class="helper-text" style="margin-top:8px">{{ filteredImportable.length }} {{ t('action.records_total') }}</div>
      <template #footer><el-button @click="importDialog=false">{{ t('action.cancel') }}</el-button><el-button type="primary" :loading="importing" :disabled="!selectedImportIds.length" @click="importSelected">{{ t('action.import') }} ({{ selectedImportIds.length }})</el-button></template>
    </el-dialog>

    <!-- Activate / Deactivate Dialog -->
    <el-dialog v-model="toggleDialog" :title="toggleActive ? t('action.activate') : t('action.deactivate')" width="420px">
      <p>{{ toggleActive ? t('action.confirm_activate', { record: toggleName }) : t('action.deactivate_confirm') }}</p>
      <el-input v-if="!toggleActive" v-model="toggleReason" :placeholder="t('field.deactivation_reason')" type="textarea" :rows="2" />
      <template #footer><el-button @click="toggleDialog=false">{{ t('action.cancel') }}</el-button><el-button :type="toggleActive ? 'success' : 'danger'" @click="confirmToggle">{{ toggleActive ? t('action.activate') : t('action.deactivate') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1600px; margin: 0 auto; padding: 24px; font-size: 15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.count-chip { background:#e8f0fe; color:#1B6CB2; padding:2px 12px; border-radius:12px; font-size:.82rem; font-weight:600; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.fiori-table { width:100% !important; }
.fiori-table :deep(.el-table__body-wrapper) { overflow-x:auto !important; }
.emp-num { font-weight:700; color:#1d2a3a; }
.emp-name { font-weight:650; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%; }
.dot-on { background:#10b981; }
.dot-off { background:#d1d5db; }
.table-footer { display:flex; justify-content:space-between; align-items:center; padding:10px 16px; border-top:1px solid #e5e7eb; }
.helper-text { color:#6b7280; font-size:.85rem; }
.drawer-head { display:flex; align-items:center; gap:12px; }
.drawer-avatar { width:42px; height:42px; border-radius:50%; background:linear-gradient(135deg,#1B6CB2,#0f2b46); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.1rem; }
.drawer-name { font-weight:700; font-size:1.05rem; }
.drawer-meta { font-size:.82rem; color:#6b7280; }
.drawer-body { padding:0 4px; }

.fi-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px; margin-bottom:14px; }
.fi-card-head { display:flex; align-items:center; gap:8px; font-weight:700; font-size:.95rem; color:#1d2a3a; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid #e5e7eb; }
.fi-card label { display:block; font-size:.75rem; font-weight:700; color:#374151; text-transform:uppercase; margin-bottom:2px; letter-spacing:.02em; }
.fi-card .el-col { margin-bottom:10px; }
</style>
