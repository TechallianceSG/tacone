<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { payrollCnApi } from '@/api/client'
import EmployeeImportDialog from '@/modules/payroll/EmployeeImportDialog.vue'

const { t } = useI18n()

// ── State ──
const loading = ref(false)
const employees = ref<any[]>([])
const itemDefs = ref<any[]>([])
const entities = ref<any[]>([])
const departments = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Filters
const search = ref('')
const filterEntity = ref('')
const filterSalaryType = ref('')
const filterStatus = ref('')

// Drawer
const drawerVisible = ref(false)
const editForm = ref<Record<string, any>>({})
const isNew = ref(false)

// Import
const importDialogVisible = ref(false)

// ── Computed ──
const salaryTypes = computed(() => [
  { value: 'monthly', label: t('payroll.cn.salary_type_monthly') },
  { value: 'hourly', label: t('payroll.cn.salary_type_hourly') },
  { value: 'daily', label: t('payroll.cn.salary_type_daily') },
])

// ── API Calls ──
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (search.value) params.search = search.value
    if (filterEntity.value) params.entity_id = filterEntity.value
    if (filterSalaryType.value) params.salary_type = filterSalaryType.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await payrollCnApi.employees(params)
    employees.value = res.data.data || []
    total.value = res.data.pagination?.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Failed to load employees')
  } finally { loading.value = false }
}

async function loadDropdowns() {
  try {
    const [eRes, dRes] = await Promise.all([
      payrollCnApi.entities(),
      payrollCnApi.departments(),
    ])
    entities.value = eRes.data.data || []
    departments.value = dRes.data.data || []
  } catch (_) {}
}

async function loadItemDefs() {
  try {
    const res = await payrollCnApi.itemDefinitions()
    itemDefs.value = res.data.data || []
  } catch (_) {}
}

// ── Actions ──
function openCreate() {
  isNew.value = true
  editForm.value = { salary_type: 'monthly', status: 'active', city_code: '320100', housing_fund_city_code: '320100', basic_salary: 0, position_allowance: 0, transport_allowance: 0, bonus: 0, social_insurance_base: 0, housing_fund_base: 0, full_attendance_bonus: 200 }
  drawerVisible.value = true
}

function openEdit(row: any) {
  isNew.value = false
  editForm.value = { ...row }
  drawerVisible.value = true
}

async function saveEmployee() {
  try {
    await payrollCnApi.saveEmployee(editForm.value)
    ElMessage.success(isNew.value ? t('payroll.cn.employee_created') : t('payroll.cn.employee_updated'))
    drawerVisible.value = false
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Save failed')
  }
}

async function deactivateEmployee(row: any) {
  try {
    await ElMessageBox.confirm(t('payroll.cn.deactivate_confirm', { name: row.employee_name }), t('payroll.cn.confirm_deactivate'), { type: 'warning' })
    await payrollCnApi.deactivateEmployee(row.id || row.employee_id, { reason: 'Manual deactivation' })
    ElMessage.success(t('payroll.cn.employee_deactivated'))
    loadData()
  } catch (_) {}
}

async function activateEmployee(row: any) {
  try {
    await payrollCnApi.activateEmployee(row.id || row.employee_id)
    ElMessage.success(t('payroll.cn.employee_activated'))
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Activation failed')
  }
}

function onImported() { loadData() }

// ── Helpers ──
function entityLabel(eid: string) {
  const e = entities.value.find((x: any) => x.entity_id === eid || x.entity_code === eid)
  if (!e) return eid
  return `${e.entity_code || eid} - ${e.entity_name_zh || e.entity_name_en || eid}`
}

function fmtCurrency(v: number) {
  if (!v && v !== 0) return '-'
  return `¥${Number(v).toLocaleString()}`
}

// ── Lifecycle ──
onMounted(() => { loadDropdowns(); loadItemDefs(); loadData() })
</script>

<template>
  <div class="fiori-page">
    <!-- Toolbar -->
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.cn.employees') }}</h2>
        <span class="count-chip">{{ total }}</span>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" @click="openCreate">+ {{ t('payroll.cn.create_employee') }}</el-button>
        <el-button @click="importDialogVisible = true">{{ t('payroll.cn.import_from_employees') }}</el-button>
      </div>
    </div>

    <!-- Filters -->
    <div class="fiori-filters">
      <el-input v-model="search" :placeholder="t('payroll.cn.search_placeholder')" clearable style="width:200px" @change="loadData" />
      <el-select v-model="filterEntity" :placeholder="t('field.entity')" clearable style="width:240px" @change="loadData">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
      </el-select>
      <el-select v-model="filterSalaryType" :placeholder="t('payroll.cn.salary_type')" clearable style="width:130px" @change="loadData">
        <el-option v-for="st in salaryTypes" :key="st.value" :label="st.label" :value="st.value" />
      </el-select>
      <el-select v-model="filterStatus" :placeholder="t('payroll.cn.status_label')" clearable style="width:110px" @change="loadData">
        <el-option :label="t('payroll.cn.active')" value="active" />
        <el-option :label="t('payroll.cn.inactive')" value="inactive" />
      </el-select>
    </div>

    <!-- Table -->
    <div class="fiori-card">
      <el-table :data="employees" v-loading="loading" border stripe size="small" style="width:100%">
        <el-table-column type="index" width="50" fixed="left" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="110" fixed="left" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="120" fixed="left" />
        <el-table-column :label="t('payroll.cn.entity_code')" min-width="200">
          <template #default="{ row }">{{ entityLabel(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column prop="department_label" :label="t('payroll.cn.department')" min-width="120" />
        <el-table-column :label="t('payroll.cn.salary_type')" min-width="90">
          <template #default="{ row }">{{ row.salary_type === 'monthly' ? t('payroll.cn.monthly_salary') : row.salary_type === 'hourly' ? t('payroll.cn.hourly_salary') : row.salary_type === 'daily' ? t('payroll.cn.daily_salary') : row.salary_type }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.basic_salary')" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.basic_salary) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.position_allowance')" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.position_allowance) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.social_insurance_base')" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.social_insurance_base) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.housing_fund_base')" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.housing_fund_base) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.full_attendance_bonus')" min-width="90" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.full_attendance_bonus) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.transport_allowance')" min-width="100" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.transport_allowance) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.bonus')" min-width="100" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.bonus) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.status_label')" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? t('payroll.cn.active') : t('payroll.cn.inactive') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('payroll.cn.edit') }}</el-button>
            <el-button v-if="row.status === 'active'" link type="warning" size="small" @click="deactivateEmployee(row)">{{ t('action.deactivate') }}</el-button>
            <el-button v-else link type="success" size="small" @click="activateEmployee(row)">{{ t('action.activate') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div class="helper-text" style="margin-top:8px">{{ total }} record(s) total</div>

    <!-- Edit Drawer -->
    <el-drawer v-model="drawerVisible" :title="isNew ? t('payroll.cn.new_employee_config') : t('payroll.cn.edit_employee_config')" direction="rtl" size="560px">
      <div class="drawer-body">
        <!-- Basic Info -->
        <div class="fi-card">
          <div class="fi-card-head">{{ t('payroll.cn.section_basic_info') }}</div>
          <el-form label-width="110px" size="small">
            <el-form-item :label="t('payroll.cn.employee_name')">
              <el-input v-model="editForm.employee_name" :disabled="!isNew" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.employee_number')">
              <el-input v-model="editForm.employee_number" :disabled="!isNew" />
            </el-form-item>
            <el-form-item :label="t('field.entity')">
              <el-select v-model="editForm.entity_id" style="width:100%">
                <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('payroll.cn.salary_type')">
              <el-select v-model="editForm.salary_type" style="width:100%">
                <el-option v-for="st in salaryTypes" :key="st.value" :label="st.label" :value="st.value" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <!-- Salary Structure -->
        <div class="fi-card">
          <div class="fi-card-head">{{ t('payroll.cn.section_salary_structure') }}</div>
          <el-form label-width="110px" size="small">
            <el-form-item :label="t('payroll.cn.basic_salary')">
              <el-input-number v-model="editForm.basic_salary" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.position_allowance')">
              <el-input-number v-model="editForm.position_allowance" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.full_attendance_bonus')">
              <el-input-number v-model="editForm.full_attendance_bonus" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.transport_allowance')">
              <el-input-number v-model="editForm.transport_allowance" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.bonus')">
              <el-input-number v-model="editForm.bonus" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
          </el-form>
        </div>

        <!-- Social Insurance & Housing Fund -->
        <div class="fi-card">
          <div class="fi-card-head">{{ t('payroll.cn.section_social_insurance') }}</div>
          <el-form label-width="110px" size="small">
            <el-form-item :label="t('payroll.cn.social_insurance_base')">
              <el-input-number v-model="editForm.social_insurance_base" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.housing_fund_base')">
              <el-input-number v-model="editForm.housing_fund_base" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.insurance_city')">
              <el-select v-model="editForm.city_code" style="width:100%">
                <el-option :label="t('payroll.cn.nanjing')" value="320100" />
                <el-option :label="t('payroll.cn.changchun')" value="220100" />
                <el-option :label="t('payroll.cn.beijing')" value="110000" />
                <el-option :label="t('payroll.cn.shanghai')" value="310000" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('payroll.cn.housing_fund_city')">
              <el-select v-model="editForm.housing_fund_city_code" style="width:100%">
                <el-option :label="t('payroll.cn.nanjing')" value="320100" />
                <el-option :label="t('payroll.cn.changchun')" value="220100" />
                <el-option :label="t('payroll.cn.beijing')" value="110000" />
                <el-option :label="t('payroll.cn.shanghai')" value="310000" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <!-- Bank Info -->
        <div class="fi-card">
          <div class="fi-card-head">{{ t('payroll.cn.section_bank') }}</div>
          <el-form label-width="110px" size="small">
            <el-form-item :label="t('payroll.cn.bank_name')">
              <el-input v-model="editForm.bank_name" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.branch_name')">
              <el-input v-model="editForm.bank_branch_name" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.account_type')">
              <el-select v-model="editForm.bank_account_type" style="width:100%">
                <el-option :label="t('payroll.cn.savings_account')" value="savings" />
                <el-option :label="t('payroll.cn.checking_account')" value="checking" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('payroll.cn.account_name')">
              <el-input v-model="editForm.bank_account_name" />
            </el-form-item>
            <el-form-item :label="t('payroll.cn.account_number')">
              <el-input v-model="editForm.bank_account_number" />
            </el-form-item>
          </el-form>
        </div>

        <!-- Notes -->
        <div class="fi-card">
          <div class="fi-card-head">{{ t('payroll.cn.section_notes') }}</div>
          <el-form label-width="110px" size="small">
            <el-form-item :label="t('field.notes')">
              <el-input v-model="editForm.notes" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="drawerVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveEmployee">{{ t('common.save') }}</el-button>
      </template>
    </el-drawer>

    <!-- Import Dialog -->
    <EmployeeImportDialog
      v-model="importDialogVisible"
      country-code="cn"
      :api="payrollCnApi"
      :entities="entities"
      :departments="departments"
      :entity-resolver="entityLabel"
      @imported="onImported"
    />
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1400px; margin: 0 auto; padding: 24px; font-size: 15px; }
.fiori-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.toolbar-left h2 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #1d2a3a; }
.count-chip { background: #eff6ff; color: #1B6CB2; padding: 2px 10px; border-radius: 10px; font-size: .8rem; font-weight: 600; }
.fiori-filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.fiori-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
.helper-text { color: #6b7280; font-size: .85rem; }
/* Drawer */
.drawer-body { padding: 0 4px; display: flex; flex-direction: column; gap: 16px; }
.fi-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; }
.fi-card-head { font-weight: 700; color: #1d2a3a; margin-bottom: 12px; font-size: .95rem; }
</style>
