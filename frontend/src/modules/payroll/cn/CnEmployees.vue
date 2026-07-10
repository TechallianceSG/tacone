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
const salaryTypes = [
  { value: 'monthly', label: '月薪制' },
  { value: 'hourly', label: '时薪制' },
  { value: 'daily', label: '日薪制' },
]

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
  editForm.value = { salary_type: 'monthly', status: 'active', city_code: '320100', housing_fund_city_code: '320100', basic_salary: 0, position_allowance: 0, social_insurance_base: 0, housing_fund_base: 0, standard_work_days: 22, full_attendance_bonus: 200 }
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
    ElMessage.success(isNew.value ? '员工已创建' : '员工已更新')
    drawerVisible.value = false
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Save failed')
  }
}

async function deactivateEmployee(row: any) {
  try {
    await ElMessageBox.confirm(`确定要停用 ${row.employee_name} 吗？`, '确认停用', { type: 'warning' })
    await payrollCnApi.deactivateEmployee(row.id || row.employee_id, { reason: 'Manual deactivation' })
    ElMessage.success('员工已停用')
    loadData()
  } catch (_) {}
}

async function activateEmployee(row: any) {
  try {
    await payrollCnApi.activateEmployee(row.id || row.employee_id)
    ElMessage.success('员工已激活')
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'Activation failed')
  }
}

function onImported() { loadData() }

// ── Helpers ──
function entityLabel(eid: string) {
  const e = entities.value.find((x: any) => x.id === eid || x.entity_id === eid)
  return e ? `${e.entity_code || e.id} - ${e.name}` : eid
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
        <el-button type="primary" @click="openCreate">+ 新增员工</el-button>
        <el-button @click="importDialogVisible = true">从员工管理导入</el-button>
      </div>
    </div>

    <!-- Filters -->
    <div class="fiori-filters">
      <el-input v-model="search" placeholder="搜索姓名/编号..." clearable style="width:200px" @change="loadData" />
      <el-select v-model="filterEntity" placeholder="法人实体" clearable style="width:240px" @change="loadData">
        <el-option v-for="e in entities" :key="e.id" :label="entityLabel(e.id)" :value="e.id" />
      </el-select>
      <el-select v-model="filterSalaryType" placeholder="工资类型" clearable style="width:130px" @change="loadData">
        <el-option v-for="st in salaryTypes" :key="st.value" :label="st.label" :value="st.value" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width:110px" @change="loadData">
        <el-option label="在职" value="active" />
        <el-option label="离职" value="inactive" />
      </el-select>
    </div>

    <!-- Table -->
    <div class="fiori-card">
      <el-table :data="employees" v-loading="loading" border stripe size="small" style="width:100%">
        <el-table-column type="index" width="50" fixed="left" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="110" fixed="left" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="120" fixed="left" />
        <el-table-column label="法人实体代码" min-width="200">
          <template #default="{ row }">{{ entityLabel(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column prop="department_label" label="部门" min-width="120" />
        <el-table-column label="工资类型" min-width="90">
          <template #default="{ row }">{{ row.salary_type === 'monthly' ? '月薪' : row.salary_type === 'hourly' ? '时薪' : row.salary_type === 'daily' ? '日薪' : row.salary_type }}</template>
        </el-table-column>
        <el-table-column label="基本工资" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.basic_salary) }}</template>
        </el-table-column>
        <el-table-column label="职位津贴" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.position_allowance) }}</template>
        </el-table-column>
        <el-table-column label="社保基数" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.social_insurance_base) }}</template>
        </el-table-column>
        <el-table-column label="公积金基数" min-width="120" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.housing_fund_base) }}</template>
        </el-table-column>
        <el-table-column label="全勤奖" min-width="90" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.full_attendance_bonus) }}</template>
        </el-table-column>
        <el-table-column label="标准工作天数" min-width="110" align="center">
          <template #default="{ row }">{{ row.standard_work_days || 22 }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '在职' : '离职' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'active'" link type="warning" size="small" @click="deactivateEmployee(row)">停用</el-button>
            <el-button v-else link type="success" size="small" @click="activateEmployee(row)">激活</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div class="helper-text" style="margin-top:8px">{{ total }} record(s) total</div>

    <!-- Edit Drawer -->
    <el-drawer v-model="drawerVisible" :title="isNew ? '新增员工工资配置' : '编辑员工工资配置'" direction="rtl" size="560px">
      <div class="drawer-body">
        <!-- Basic Info -->
        <div class="fi-card">
          <div class="fi-card-head">📋 基本信息</div>
          <el-form label-width="110px" size="small">
            <el-form-item label="员工姓名">
              <el-input v-model="editForm.employee_name" :disabled="!isNew" />
            </el-form-item>
            <el-form-item label="员工编号">
              <el-input v-model="editForm.employee_number" :disabled="!isNew" />
            </el-form-item>
            <el-form-item label="法人实体">
              <el-select v-model="editForm.entity_id" style="width:100%">
                <el-option v-for="e in entities" :key="e.id" :label="entityLabel(e.id)" :value="e.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="工资类型">
              <el-select v-model="editForm.salary_type" style="width:100%">
                <el-option v-for="st in salaryTypes" :key="st.value" :label="st.label" :value="st.value" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <!-- Salary Structure -->
        <div class="fi-card">
          <div class="fi-card-head">💰 工资结构</div>
          <el-form label-width="110px" size="small">
            <el-form-item label="基本工资">
              <el-input-number v-model="editForm.basic_salary" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="职位津贴">
              <el-input-number v-model="editForm.position_allowance" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="全勤奖">
              <el-input-number v-model="editForm.full_attendance_bonus" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="标准工作天数">
              <el-input-number v-model="editForm.standard_work_days" :min="1" :max="31" style="width:100%" />
            </el-form-item>
          </el-form>
        </div>

        <!-- Social Insurance & Housing Fund -->
        <div class="fi-card">
          <div class="fi-card-head">🏦 社保与公积金</div>
          <el-form label-width="110px" size="small">
            <el-form-item label="社保基数">
              <el-input-number v-model="editForm.social_insurance_base" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="公积金基数">
              <el-input-number v-model="editForm.housing_fund_base" :min="0" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="参保城市">
              <el-select v-model="editForm.city_code" style="width:100%">
                <el-option label="南京 (320100)" value="320100" />
                <el-option label="长春 (220100)" value="220100" />
                <el-option label="北京 (110000)" value="110000" />
                <el-option label="上海 (310000)" value="310000" />
              </el-select>
            </el-form-item>
            <el-form-item label="公积金城市">
              <el-select v-model="editForm.housing_fund_city_code" style="width:100%">
                <el-option label="南京 (320100)" value="320100" />
                <el-option label="长春 (220100)" value="220100" />
                <el-option label="北京 (110000)" value="110000" />
                <el-option label="上海 (310000)" value="310000" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <!-- Bank Info -->
        <div class="fi-card">
          <div class="fi-card-head">🏧 银行信息</div>
          <el-form label-width="110px" size="small">
            <el-form-item label="银行名称">
              <el-input v-model="editForm.bank_name" />
            </el-form-item>
            <el-form-item label="支行名称">
              <el-input v-model="editForm.bank_branch_name" />
            </el-form-item>
            <el-form-item label="账户类型">
              <el-select v-model="editForm.bank_account_type" style="width:100%">
                <el-option label="储蓄账户" value="savings" />
                <el-option label="支票账户" value="checking" />
              </el-select>
            </el-form-item>
            <el-form-item label="账户名">
              <el-input v-model="editForm.bank_account_name" />
            </el-form-item>
            <el-form-item label="账号">
              <el-input v-model="editForm.bank_account_number" />
            </el-form-item>
          </el-form>
        </div>

        <!-- Notes -->
        <div class="fi-card">
          <div class="fi-card-head">📝 备注</div>
          <el-form label-width="110px" size="small">
            <el-form-item label="备注">
              <el-input v-model="editForm.notes" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEmployee">保存</el-button>
      </template>
    </el-drawer>

    <!-- Import Dialog -->
    <EmployeeImportDialog
      v-model="importDialogVisible"
      country-code="cn"
      :api="payrollCnApi"
      :entities="entities"
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
