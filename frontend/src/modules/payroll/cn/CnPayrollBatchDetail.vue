<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { payrollCnApi } from '@/api/client'
import { CN_STATUS_CONFIG, CN_STATUS_WORKFLOW, cnStatusIndex, cnActionLabel } from '@/constants/payrollCn'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const batchId = computed(() => route.params.id as string)

// ── State ──
const loading = ref(false)
const batch = ref<Record<string, any>>({})
const records = ref<any[]>([])
const entities = ref<any[]>([])

// Dialogs
const editDialogVisible = ref(false)
const editForm = ref<Record<string, any>>({})
const editingRecordId = ref('')
const rollbackDialogVisible = ref(false)
const rollbackReason = ref('')
const auditLogDialogVisible = ref(false)
const auditLogs = ref<any[]>([])

// ── Computed ──
const statusConfig = computed(() => CN_STATUS_CONFIG[batch.value.status] || { type: '', label: '' })
const currentStep = computed(() => cnStatusIndex(batch.value.status))

const canCalculate = computed(() => batch.value.status === 'draft')
const canConfirm = computed(() => batch.value.status === 'calculated')
const canRollback = computed(() => batch.value.status === 'confirmed')
const canEditRecords = computed(() => ['draft', 'calculated'].includes(batch.value.status))
const canVoid = computed(() => batch.value.status !== 'voided' && batch.value.status !== 'confirmed')

const grossTotal = computed(() => records.value.reduce((s, r) => s + Number(r.gross_pay || 0), 0))
const deductionTotal = computed(() => records.value.reduce((s, r) => s + Number(r.deduction_total || 0), 0))
const netTotal = computed(() => records.value.reduce((s, r) => s + Number(r.net_pay || 0), 0))
const employerCostTotal = computed(() => records.value.reduce((s, r) => s + Number(r.employer_cost_total || 0), 0))

// ── Edit field groups ──
const editFieldGroups = [
  {
    title: '出勤 / Attendance',
    fields: [
      { key: 'full_attendance_days', label: '满勤天数', min: 0, precision: 1 },
      { key: 'actual_attendance_days', label: '出勤天数', min: 0, precision: 1 },
      { key: 'personal_leave_days', label: '事假', min: 0, precision: 2 },
      { key: 'annual_leave_days', label: '年假', min: 0, precision: 2 },
      { key: 'sick_leave_days', label: '病假', min: 0, precision: 2 },
      { key: 'other_leave_days', label: '其他假', min: 0, precision: 2 },
    ],
  },
  {
    title: '收入 / Earnings',
    fields: [
      { key: 'other_additions', label: '其他加项', min: 0, precision: 2 },
      { key: 'full_attendance_bonus', label: '全勤奖', min: 0, precision: 2 },
    ],
  },
  {
    title: '扣除 / Deductions',
    fields: [
      { key: 'other_deductions', label: '其他扣款', min: 0, precision: 2 },
    ],
  },
]

// ── Auto-compute totals in edit form ──
watch(() => editForm.value, () => {
  const ef = editForm.value
  const basic = Number(ef.basic_salary || 0)
  const position = Number(ef.position_allowance || 0)
  const fullDays = Number(ef.full_attendance_days || 22)
  const actualDays = Number(ef.actual_attendance_days || fullDays)
  const sickDays = Number(ef.sick_leave_days || 0)

  if (fullDays > 0) {
    ef.attendance_pay = Math.round(((basic + position) / fullDays * actualDays) * 100) / 100
    ef.sick_leave_pay = Math.round(((basic + position) / fullDays * sickDays * 0.6) * 100) / 100
  }
  const bonus = Number(ef.full_attendance_bonus || 0)
  const additions = Number(ef.other_additions || 0)
  ef.gross_pay = Math.round((Number(ef.attendance_pay || 0) + Number(ef.sick_leave_pay || 0) + bonus + additions) * 100) / 100

  const si = Number(ef.social_insurance || 0)
  const hf = Number(ef.housing_fund || 0)
  const iit = Number(ef.iit || 0)
  const otherDed = Number(ef.other_deductions || 0)
  ef.deduction_total = Math.round((si + hf + iit + otherDed) * 100) / 100
  ef.net_pay = Math.round((ef.gross_pay - ef.deduction_total) * 100) / 100
}, { deep: true })

// ── API ──
async function loadBatch() {
  loading.value = true
  try {
    const res = await payrollCnApi.getBatch(batchId.value)
    batch.value = res.data.data || {}
    records.value = batch.value.records || []
    delete batch.value.records
  } catch (e: any) {
    ElMessage.error('Failed to load batch')
    router.push('/payroll/cn/batches')
  } finally { loading.value = false }
}

async function loadEntities() {
  try {
    const res = await payrollCnApi.entities()
    entities.value = res.data.data || []
  } catch (_) {}
}

async function doCalculate() {
  try {
    await ElMessageBox.confirm('计算将覆盖所有当前数据，确定继续？', '确认计算', { type: 'warning' })
    loading.value = true
    await payrollCnApi.calculateBatch(batchId.value)
    ElMessage.success('计算完成')
    loadBatch()
  } catch (_) { } finally { loading.value = false }
}

async function doConfirm() {
  try {
    await ElMessageBox.confirm('定稿后将生成工资单，确定继续？', '确认定稿', { type: 'warning' })
    await payrollCnApi.confirmBatch(batchId.value)
    ElMessage.success('已定稿')
    loadBatch()
  } catch (_) {}
}

async function doRollback() {
  if (!rollbackReason.value.trim()) { ElMessage.warning('请输入回退原因'); return }
  try {
    await payrollCnApi.rollbackBatch(batchId.value, { reason: rollbackReason.value })
    ElMessage.success('已回退')
    rollbackDialogVisible.value = false
    rollbackReason.value = ''
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Rollback failed') }
}

async function doVoid() {
  try {
    const { value: reason } = await ElMessageBox.prompt('请输入作废原因', '确认作废', { type: 'warning' })
    await payrollCnApi.voidBatch(batchId.value, { reason })
    ElMessage.success('已作废')
    loadBatch()
  } catch (_) {}
}

async function doDelete() {
  try {
    await ElMessageBox.confirm('确定删除此批次吗？此操作不可撤销。', '确认删除', { type: 'warning' })
    await payrollCnApi.deleteBatch(batchId.value)
    ElMessage.success('已删除')
    router.push('/payroll/cn/batches')
  } catch (_) {}
}

// ── Record editing ──
function openEditRecord(row: any) {
  editingRecordId.value = row.record_id
  editForm.value = { ...row }
  editDialogVisible.value = true
}

async function saveEditRecord() {
  try {
    await payrollCnApi.editRecord(batchId.value, editingRecordId.value, editForm.value)
    ElMessage.success('记录已更新')
    editDialogVisible.value = false
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Edit failed') }
}

async function recalculateRecord(row: any) {
  try {
    await payrollCnApi.recalculateSingleRecord(batchId.value, row.record_id)
    ElMessage.success('已重新计算')
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Recalculate failed') }
}

// ── Audit ──
async function openAuditLogs() {
  try {
    const res = await payrollCnApi.getBatchAuditLogs(batchId.value)
    auditLogs.value = res.data.data || []
    auditLogDialogVisible.value = true
  } catch (_) {}
}

// ── Helpers ──
function entityLabel(eid: string) {
  const e = entities.value.find((x: any) => x.id === eid || x.entity_id === eid)
  return e ? `${e.entity_code || e.id} - ${e.name}` : eid
}

function fmtCurrency(v: number) {
  if (!v && v !== 0) return '-'
  return `¥${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtInt(v: number) {
  if (!v && v !== 0) return '-'
  return `¥${Number(v).toLocaleString()}`
}

// ── Lifecycle ──
onMounted(() => { loadEntities(); loadBatch() })
</script>

<template>
  <div class="fiori-page" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <el-button link @click="router.push('/payroll/cn/batches')">
          ← {{ t('payroll.cn.batches') }}
        </el-button>
        <h2>{{ t('payroll.cn.batch_detail') }}</h2>
        <el-tag :type="statusConfig.type || 'info'" size="small">{{ t(statusConfig.label) }}</el-tag>
        <span class="helper-text">{{ batch.batch_id }}</span>
      </div>
      <div class="header-actions">
        <el-button v-if="canCalculate" type="primary" @click="doCalculate">🧮 计算</el-button>
        <el-button v-if="canConfirm" type="success" @click="doConfirm">✅ 定稿</el-button>
        <el-button v-if="canRollback" type="warning" @click="rollbackDialogVisible = true">↩️ 回退</el-button>
        <el-button v-if="canVoid" type="danger" plain @click="doVoid">🚫 作废</el-button>
        <el-button @click="openAuditLogs">📋 审计日志</el-button>
        <el-button v-if="canVoid" type="danger" link @click="doDelete">🗑️ 删除</el-button>
      </div>
    </div>

    <!-- Workflow Steps -->
    <div class="workflow-bar">
      <div v-for="(step, i) in CN_STATUS_WORKFLOW" :key="step"
        class="wf-step" :class="{ active: i <= currentStep, current: i === currentStep }">
        <span class="wf-dot">{{ i + 1 }}</span>
        <span class="wf-label">{{ t(`payroll.cn.status_${step}`) }}</span>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="summary-row">
      <div class="summary-card">
        <div class="sc-label">员工数</div>
        <div class="sc-value">{{ batch.employee_count || 0 }}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">应发合计</div>
        <div class="sc-value">{{ fmtInt(grossTotal) }}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">扣除合计</div>
        <div class="sc-value" style="color:#dc2626">{{ fmtInt(deductionTotal) }}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">实发合计</div>
        <div class="sc-value" style="color:#059669">{{ fmtInt(netTotal) }}</div>
      </div>
      <div class="summary-card">
        <div class="sc-label">雇主成本</div>
        <div class="sc-value" style="color:#e65100">{{ fmtInt(employerCostTotal) }}</div>
      </div>
    </div>

    <!-- Info -->
    <div class="info-row">
      <el-descriptions :column="4" size="small" border>
        <el-descriptions-item label="工资月份">{{ batch.payroll_month }}</el-descriptions-item>
        <el-descriptions-item label="法人实体">{{ entityLabel(batch.entity_id) }}</el-descriptions-item>
        <el-descriptions-item label="标准工作天数">{{ batch.working_days_in_month || 22 }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ batch.created_by }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- Records Table -->
    <div class="fiori-card" style="margin-top:16px">
      <el-table :data="records" border stripe size="small" style="width:100%">
        <el-table-column type="index" width="40" fixed="left" />
        <el-table-column prop="employee_name" label="姓名" min-width="100" fixed="left" />
        <el-table-column prop="employee_number" label="编号" min-width="90" />

        <!-- Attendance -->
        <el-table-column label="满勤天数" min-width="80" align="center">
          <template #default="{ row }">{{ row.full_attendance_days }}</template>
        </el-table-column>
        <el-table-column label="出勤天数" min-width="80" align="center">
          <template #default="{ row }">{{ row.actual_attendance_days }}</template>
        </el-table-column>
        <el-table-column label="事假" min-width="60" align="center">
          <template #default="{ row }">{{ row.personal_leave_days || 0 }}</template>
        </el-table-column>
        <el-table-column label="年假" min-width="60" align="center">
          <template #default="{ row }">{{ row.annual_leave_days || 0 }}</template>
        </el-table-column>
        <el-table-column label="病假" min-width="60" align="center">
          <template #default="{ row }">{{ row.sick_leave_days || 0 }}</template>
        </el-table-column>

        <!-- Earnings -->
        <el-table-column label="基本工资" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.basic_salary) }}</template>
        </el-table-column>
        <el-table-column label="职位津贴" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.position_allowance) }}</template>
        </el-table-column>
        <el-table-column label="出勤工资" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.attendance_pay) }}</template>
        </el-table-column>
        <el-table-column label="病假工资" min-width="100" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.sick_leave_pay) }}</template>
        </el-table-column>
        <el-table-column label="全勤奖" min-width="80" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.full_attendance_bonus) }}</template>
        </el-table-column>
        <el-table-column label="其他加项" min-width="100" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.other_additions) }}</template>
        </el-table-column>

        <!-- Deductions -->
        <el-table-column label="社保(个人)" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.social_insurance) }}</template>
        </el-table-column>
        <el-table-column label="公积金(个人)" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.housing_fund) }}</template>
        </el-table-column>
        <el-table-column label="个税" min-width="90" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.iit) }}</template>
        </el-table-column>
        <el-table-column label="其他扣款" min-width="100" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.other_deductions) }}</template>
        </el-table-column>

        <!-- Totals -->
        <el-table-column label="应发合计" min-width="110" align="right">
          <template #default="{ row }">
            <strong>{{ fmtCurrency(row.gross_pay) }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="扣除合计" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.deduction_total) }}</template>
        </el-table-column>
        <el-table-column label="实发工资" min-width="120" align="right" fixed="right">
          <template #default="{ row }">
            <el-tag :type="Number(row.net_pay) >= 0 ? 'success' : 'danger'" size="small">
              {{ fmtCurrency(row.net_pay) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- Employer -->
        <el-table-column label="社保(单位)" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.employer_social_insurance) }}</template>
        </el-table-column>
        <el-table-column label="公积金(单位)" min-width="110" align="right">
          <template #default="{ row }">{{ fmtCurrency(row.employer_housing_fund) }}</template>
        </el-table-column>

        <!-- Manual edit indicator -->
        <el-table-column label="" width="30" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.manually_edited" content="已手动编辑" placement="top">
              <span style="color:#e65100">✏️</span>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- Actions -->
        <el-table-column label="操作" min-width="130" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="canEditRecords" link type="primary" size="small" @click="openEditRecord(row)">编辑</el-button>
            <el-button link type="success" size="small" @click="recalculateRecord(row)">重算</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div class="helper-text" style="margin-top:8px">{{ records.length }} record(s) total</div>

    <!-- Edit Record Dialog -->
    <el-dialog v-model="editDialogVisible" :title="`编辑记录 — ${editForm.employee_name}`" width="700px">
      <div v-for="group in editFieldGroups" :key="group.title" style="margin-bottom:16px">
        <h4 style="margin:0 0 8px;color:#1d2a3a;font-size:.95rem">{{ group.title }}</h4>
        <el-row :gutter="12">
          <el-col :span="12" v-for="field in group.fields" :key="field.key" style="margin-bottom:8px">
            <el-form-item :label="field.label" label-width="100px" size="small">
              <el-input-number v-model="editForm[field.key]" :min="field.min" :precision="field.precision" style="width:100%" size="small" />
            </el-form-item>
          </el-col>
        </el-row>
      </div>
      <!-- Totals (read-only) -->
      <div style="background:#f9fafb;padding:12px 16px;border-radius:8px;margin-top:8px">
        <el-row :gutter="12">
          <el-col :span="8"><span style="color:#6b7280;font-size:.85rem">应发合计:</span> <strong>{{ fmtCurrency(editForm.gross_pay) }}</strong></el-col>
          <el-col :span="8"><span style="color:#6b7280;font-size:.85rem">扣除合计:</span> <strong style="color:#dc2626">{{ fmtCurrency(editForm.deduction_total) }}</strong></el-col>
          <el-col :span="8"><span style="color:#6b7280;font-size:.85rem">实发工资:</span> <strong style="color:#059669">{{ fmtCurrency(editForm.net_pay) }}</strong></el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEditRecord">保存</el-button>
      </template>
    </el-dialog>

    <!-- Rollback Dialog -->
    <el-dialog v-model="rollbackDialogVisible" title="回退批次" width="450px">
      <el-input v-model="rollbackReason" type="textarea" :rows="3" placeholder="请输入回退原因..." />
      <template #footer>
        <el-button @click="rollbackDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="doRollback" :disabled="!rollbackReason.trim()">确认回退</el-button>
      </template>
    </el-dialog>

    <!-- Audit Log Dialog -->
    <el-dialog v-model="auditLogDialogVisible" title="审计日志" width="650px">
      <div v-if="!auditLogs.length" class="helper-text">暂无审计记录</div>
      <el-timeline v-else>
        <el-timeline-item
          v-for="log in auditLogs" :key="log.id"
          :timestamp="log.timestamp"
          placement="top"
          :color="cnActionLabel(log.action).color"
        >
          <div>
            <strong>{{ cnActionLabel(log.action).icon }} {{ cnActionLabel(log.action).label }}</strong>
            <span class="helper-text" style="margin-left:8px">by {{ log.user }}</span>
          </div>
          <div v-if="log.after_value" style="font-size:.82rem;color:#6b7280;margin-top:4px">
            {{ typeof log.after_value === 'string' ? log.after_value.substring(0, 200) : JSON.stringify(log.after_value).substring(0, 200) }}
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1600px; margin: 0 auto; padding: 24px; font-size: 15px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.header-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.header-left h2 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #1d2a3a; }
.header-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.helper-text { color: #6b7280; font-size: .85rem; }

/* Workflow */
.workflow-bar { display: flex; gap: 0; margin-bottom: 20px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
.wf-step { flex: 1; text-align: center; padding: 14px 8px; position: relative; background: #f9fafb; color: #9ca3af; }
.wf-step.active { background: #eff6ff; color: #1B6CB2; }
.wf-step.current { background: #1B6CB2; color: #fff; }
.wf-step + .wf-step { border-left: 1px solid #e5e7eb; }
.wf-dot { display: inline-block; width: 22px; height: 22px; border-radius: 50%; background: #d1d5db; color: #fff; line-height: 22px; font-size: .75rem; font-weight: 700; margin-right: 6px; }
.wf-step.active .wf-dot { background: #1B6CB2; }
.wf-step.current .wf-dot { background: #fff; color: #1B6CB2; }
.wf-label { font-size: .82rem; font-weight: 600; }

/* Summary */
.summary-row { display: flex; gap: 14px; margin-bottom: 16px; flex-wrap: wrap; }
.summary-card { flex: 1; min-width: 120px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 18px; text-align: center; }
.sc-label { font-size: .78rem; color: #6b7280; margin-bottom: 4px; }
.sc-value { font-size: 1.2rem; font-weight: 700; color: #1d2a3a; }

.info-row { margin-bottom: 8px; }

.fiori-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
</style>
