<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { payrollCnApi } from '@/api/client'
import { CN_STATUS_CONFIG, CN_STATUS_WORKFLOW, cnStatusIndex, cnActionLabel, parseCnAuditValue } from '@/constants/payrollCn'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const batchId = computed(() => route.params.id as string)

// ── State ──
const loading = ref(false)
const calcLoading = ref(false)
const confirmLoading = ref(false)
const batch = ref<Record<string, any>>({})
const records = ref<any[]>([])
const entities = ref<any[]>([])
const recPage = ref(1)
const recPageSize = ref(20)

// Dialogs
const editDialogVisible = ref(false)
const editForm = ref<Record<string, any>>({})
const editingRecordId = ref('')
const rollbackDialogVisible = ref(false)
const rollbackReason = ref('')
const auditDialogVisible = ref(false)
const auditLogs = ref<any[]>([])
const auditLoading = ref(false)
const expandedAudit = ref<Set<number>>(new Set())

function toggleAuditDetail(idx: number) {
  if (expandedAudit.value.has(idx)) { expandedAudit.value.delete(idx) }
  else { expandedAudit.value.add(idx) }
}

// ── Computed ──
const statusConfig = computed(() => CN_STATUS_CONFIG[batch.value.status] || { type: 'info', label: '' })
const currentStep = computed(() => cnStatusIndex(batch.value.status))

const canCalculate = computed(() => batch.value.status === 'draft' || batch.value.status === 'calculated')
const canConfirm = computed(() => batch.value.status === 'calculated')
const canRollback = computed(() => batch.value.status === 'confirmed')

const pagedRecords = computed(() => {
  const start = (recPage.value - 1) * recPageSize.value
  return records.value.slice(start, start + recPageSize.value)
})

const summaryCards = computed(() => {
  const gross = records.value.reduce((s, r) => s + Number(r.gross_pay || 0), 0)
  const ded = records.value.reduce((s, r) => s + Number(r.deduction_total || 0), 0)
  const net = records.value.reduce((s, r) => s + Number(r.net_pay || 0), 0)
  const empCost = records.value.reduce((s, r) => s + Number(r.employer_cost_total || 0), 0)
  return [
    { label: t('payroll.cn.employee_count'), value: batch.value.employee_count || records.value.length, color: '' },
    { label: t('payroll.cn.gross_total'), value: '\xA5' + gross.toLocaleString(), color: '' },
    { label: t('payroll.cn.deduction_total'), value: '\xA5' + ded.toLocaleString(), color: '#dc2626' },
    { label: t('payroll.cn.net_total'), value: '\xA5' + net.toLocaleString(), color: '#059669' },
    { label: t('payroll.cn.employer_cost'), value: '\xA5' + empCost.toLocaleString(), color: '#e65100' },
  ]
})

// ── Edit field groups ──
const editFieldGroups = computed(() => [
  {
    fields: [
      { key: 'full_attendance_days', label: t('payroll.cn.full_attendance_days'), min: 0, precision: 1 },
    ],
  },
  {
    title: t('payroll.cn.total_deductions'),
    fields: [
      { key: 'absence_deduction', label: t('payroll.cn.absence_deduction'), min: 0, precision: 2 },
    ],
  },
])

// Auto-compute totals in edit form
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
  } catch {
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
  const isRecalc = batch.value.status === 'calculated'
  try {
    await ElMessageBox.confirm(
      isRecalc ? t('payroll.jp.recalculate_confirm_msg') : t('payroll.cn.calc_warning'),
      isRecalc ? t('payroll.jp.recalculate') : t('payroll.cn.confirm_calc'),
      { type: 'warning' }
    )
    calcLoading.value = true
    await payrollCnApi.calculateBatch(batchId.value)
    ElMessage.success(isRecalc ? t('payroll.jp.recalculated') : t('payroll.cn.calc_completed'))
    loadBatch()
  } catch (_) { } finally { calcLoading.value = false }
}

async function doConfirm() {
  try {
    await ElMessageBox.confirm(t('payroll.cn.finalize_warning'), t('payroll.cn.confirm_finalize'), { type: 'warning' })
    confirmLoading.value = true
    await payrollCnApi.confirmBatch(batchId.value)
    ElMessage.success(t('payroll.cn.confirmed'))
    loadBatch()
  } catch (_) { } finally { confirmLoading.value = false }
}

async function doRollback() {
  if (!rollbackReason.value.trim()) { ElMessage.warning(t('payroll.cn.rollback_reason_required')); return }
  try {
    await payrollCnApi.rollbackBatch(batchId.value, { reason: rollbackReason.value })
    ElMessage.success(t('payroll.cn.rolled_back'))
    rollbackDialogVisible.value = false
    rollbackReason.value = ''
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Rollback failed') }
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
    ElMessage.success(t('payroll.cn.record_updated'))
    editDialogVisible.value = false
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Edit failed') }
}

async function recalculateRecord(row: any) {
  try {
    await payrollCnApi.recalculateSingleRecord(batchId.value, row.record_id)
    ElMessage.success(t('payroll.cn.recalculated'))
    loadBatch()
  } catch (e: any) { ElMessage.error(e?.response?.data?.error || 'Recalculate failed') }
}

async function openAuditLogs() {
  auditDialogVisible.value = true
  auditLoading.value = true
  try {
    const res = await payrollCnApi.getBatchAuditLogs(batchId.value)
    auditLogs.value = res.data.data || []
  } catch (_) {}
  finally { auditLoading.value = false }
}

// ── Helpers ──
function entityLabel(eid: string) {
  const e = entities.value.find((x: any) => x.entity_id === eid || x.entity_code === eid)
  if (!e) return eid
  return `${e.entity_code || eid} - ${e.entity_name_zh || e.entity_name_en || eid}`
}

function fmt(v: any): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (isNaN(n)) return '-'
  return '\xA5' + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function isManuallyEdited(r: any) {
  return r.manually_edited === true || r.manually_edited === 'true' || r.manually_edited === 1
}

onMounted(() => { loadBatch(); loadEntities() })
</script>

<template>
  <div class="page-container">
    <!-- ═══ Header ═══ -->
    <div class="page-header">
      <div class="header-left">
        <el-button link @click="router.push('/payroll/cn/batches')">
          ← {{ t('payroll.cn.batches') }}
        </el-button>
        <h3>{{ t('payroll.cn.batch_detail') }}</h3>
        <el-tag v-if="batch.status" :type="(statusConfig.type || 'info') as any" size="default">
          {{ t(statusConfig.label) }}
        </el-tag>
        <span class="helper-text">{{ batch.batch_id || '-' }}</span>
        <span v-if="batch.rollback_reason" class="rollback-chip">↩ {{ batch.rollback_reason }}</span>
      </div>
      <div class="header-actions">
        <el-button v-if="canCalculate" type="primary" :loading="calcLoading" @click="doCalculate">
          {{ batch.status === 'calculated' ? t('payroll.jp.recalculate') : t('payroll.jp.calculate') }}
        </el-button>
        <el-button v-if="canConfirm" type="success" :loading="confirmLoading" @click="doConfirm">
          {{ t('payroll.jp.confirm') }}
        </el-button>
        <el-button v-if="canRollback" type="warning" plain @click="rollbackDialogVisible = true">
          {{ t('payroll.jp.rollback') }}
        </el-button>
        <el-button @click="openAuditLogs">{{ t('payroll.jp.audit_log') }}</el-button>
      </div>
    </div>

    <!-- ═══ Workflow Steps ═══ -->
    <div class="workflow-bar">
      <div v-for="(step, idx) in CN_STATUS_WORKFLOW" :key="step" class="wf-step"
        :class="{ 'wf-active': currentStep >= idx, 'wf-current': currentStep === idx }">
        <div class="wf-dot">{{ idx + 1 }}</div>
        <span class="wf-label">{{ t('payroll.cn.status_' + step) }}</span>
        <div v-if="idx < CN_STATUS_WORKFLOW.length - 1" class="wf-line" />
      </div>
    </div>

    <!-- ═══ Summary Cards ═══ -->
    <div class="summary-row">
      <div v-for="(card, i) in summaryCards" :key="i" class="summary-card">
        <div class="s-label">{{ card.label }}</div>
        <div class="s-value" :style="{ color: card.color || undefined }">{{ card.value }}</div>
      </div>
    </div>

    <!-- ═══ Info ═══ -->
    <el-descriptions :column="4" border size="small" class="info-section">
      <el-descriptions-item :label="t('field.payroll_month')">{{ batch.payroll_month }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ entityLabel(batch.entity_id) }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.working_days_in_month')">{{ batch.working_days_in_month || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.created_by')">{{ batch.created_by || '-' }}</el-descriptions-item>
    </el-descriptions>

    <!-- ═══ Recalculation Warning ═══ -->
    <el-alert v-if="batch.status === 'calculated'" :title="t('payroll.jp.recalculate_overwrite_warning')" type="warning" :closable="false" show-icon style="margin-bottom:12px" />

    <!-- ═══ Records Table ═══ -->
    <div class="section-head">
      <h4>{{ t('payroll.jp.sheet_records') }}</h4>
    </div>

    <div class="table-card" v-loading="loading">
      <el-table :data="pagedRecords" border stripe size="small" max-height="480" :empty-text="t('payroll.jp.no_records')" style="width:100%">
        <el-table-column type="index" width="40" fixed="left" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="100" fixed="left" />
        <el-table-column width="130" fixed="left" show-overflow-tooltip>
          <template #header>{{ t('field.employee_name') }}</template>
          <template #default="{row}">
            {{ row.employee_name }}
            <el-tag v-if="isManuallyEdited(row)" size="small" type="warning" effect="plain" style="margin-left:4px">{{ t('payroll.cn.manually_edited') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.salary_type_label')" width="100" align="center">
          <template #default="{row}">
            <el-tag size="small" type="info">{{ t('payroll.cn.salary_type_' + (row.salary_type || 'monthly')) }}</el-tag>
          </template>
        </el-table-column>
        <!-- Attendance -->
        <el-table-column :label="t('payroll.cn.full_attendance_days')" width="65" align="center">
          <template #default="{row}">{{ row.full_attendance_days }}</template>
        </el-table-column>
        <!-- Earnings -->
        <el-table-column :label="t('payroll.cn.basic_salary')" width="100" align="right">
          <template #default="{row}">{{ fmt(row.basic_salary) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.position_allowance')" width="100" align="right">
          <template #default="{row}">{{ fmt(row.position_allowance) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.attendance_pay')" width="100" align="right">
          <template #default="{row}">{{ fmt(row.attendance_pay) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.full_attendance_bonus')" width="70" align="right">
          <template #default="{row}">{{ fmt(row.full_attendance_bonus) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.transport_allowance')" width="90" align="right">
          <template #default="{row}">{{ fmt(row.transport_allowance) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.bonus')" width="80" align="right">
          <template #default="{row}">{{ fmt(row.bonus) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.gross_pay')" width="110" align="right">
          <template #default="{row}"><strong>{{ fmt(row.gross_pay) }}</strong></template>
        </el-table-column>
        <!-- Deductions -->
        <el-table-column :label="t('payroll.cn.social_insurance')" width="90" align="right">
          <template #default="{row}">{{ fmt(row.social_insurance) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.housing_fund')" width="80" align="right">
          <template #default="{row}">{{ fmt(row.housing_fund) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.iit')" width="80" align="right">
          <template #default="{row}">{{ fmt(row.iit) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.absence_deduction')" width="90" align="right">
          <template #default="{row}">{{ fmt(row.absence_deduction) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.deduction_total')" width="100" align="right">
          <template #default="{row}">{{ fmt(row.deduction_total) }}</template>
        </el-table-column>
        <el-table-column :label="t('payroll.cn.net_pay')" width="110" align="right" fixed="right">
          <template #default="{row}"><strong style="color:#059669">{{ fmt(row.net_pay) }}</strong></template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="140" fixed="right" v-if="canCalculate || batch.status === 'calculated'">
          <template #default="{row}">
            <el-button v-if="canCalculate" size="small" text type="primary" @click="openEditRecord(row)">{{ t('action.edit') }}</el-button>
            <el-button v-if="batch.status === 'calculated'" size="small" text type="warning" @click="recalculateRecord(row)">{{ t('payroll.jp.recalculate_single') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center">
      <span class="helper-text">{{ records.length }} {{ t('action.records_total') }}</span>
      <el-pagination
        v-model:current-page="recPage"
        v-model:page-size="recPageSize"
        :page-sizes="[20, 50, 100]"
        :total="records.length"
        layout="total, sizes, prev, pager, next"
        small
      />
    </div>

    <!-- ═══ Rollback Dialog ═══ -->
    <el-dialog v-model="rollbackDialogVisible" :title="t('payroll.jp.rollback')" width="420px">
      <p>{{ t('payroll.cn.rollback_confirm') }}</p>
      <el-input v-model="rollbackReason" :placeholder="t('payroll.cn.rollback_reason_placeholder')" type="textarea" :rows="2" />
      <template #footer>
        <el-button @click="rollbackDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="warning" @click="doRollback">{{ t('payroll.jp.rollback') }}</el-button>
      </template>
    </el-dialog>

    <!-- ═══ Edit Record Dialog ═══ -->
    <el-dialog v-model="editDialogVisible" :title="t('payroll.cn.edit_record')" width="700px" top="2vh">
      <template v-for="group in editFieldGroups" :key="group.title">
        <h4 class="edit-group-title">{{ group.title }}</h4>
        <el-row :gutter="12">
          <el-col v-for="f in group.fields" :key="f.key" :span="8">
            <el-form-item :label="f.label" size="small">
              <el-input-number v-model="editForm[f.key]" :min="f.min" :precision="f.precision" :step="f.precision > 1 ? 1 : 0.5" style="width:100%" size="small" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>
      <!-- Calculated readonly summary -->
      <el-descriptions :column="3" border size="small" style="margin-top:12px">
        <el-descriptions-item :label="t('payroll.cn.attendance_pay')">{{ fmt(editForm.attendance_pay) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.sick_leave_pay')">{{ fmt(editForm.sick_leave_pay) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.gross_pay')"><strong>{{ fmt(editForm.gross_pay) }}</strong></el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.social_insurance')">{{ fmt(editForm.social_insurance) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.housing_fund')">{{ fmt(editForm.housing_fund) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.iit')">{{ fmt(editForm.iit) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.deduction_total')">{{ fmt(editForm.deduction_total) }}</el-descriptions-item>
        <el-descriptions-item :label="t('payroll.cn.net_pay')"><strong style="color:#059669">{{ fmt(editForm.net_pay) }}</strong></el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="editDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" @click="saveEditRecord">{{ t('action.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- ═══ Audit Log Dialog (Timeline Style) ═══ -->
    <el-dialog v-model="auditDialogVisible" :title="t('payroll.jp.audit_log')" width="750px" top="5vh">
      <div v-loading="auditLoading" style="max-height:520px;overflow-y:auto">
        <div v-if="auditLogs.length === 0 && !auditLoading" style="text-align:center;padding:40px;color:#9ca3af">
          {{ t('payroll.jp.no_records') }}
        </div>
        <div v-for="(log, idx) in auditLogs" :key="idx" class="audit-item" @click="toggleAuditDetail(idx)">
          <div class="audit-line">
            <div class="audit-body">
              <div class="audit-head">
                <el-tag size="small" :color="cnActionLabel(log.action).color" effect="dark" style="color:#fff">
                  {{ t(cnActionLabel(log.action).label) }}
                </el-tag>
                <span class="audit-user">{{ log.user_name }}</span>
                <span class="audit-time">{{ (log.created_at || '').replace('T', ' ').substring(0, 19) }}</span>
              </div>
              <div class="audit-summary">{{ parseCnAuditValue(log.after_value) || parseCnAuditValue(log.before_value) || '—' }}</div>
              <div v-if="expandedAudit.has(idx)" class="audit-expand">
                <div v-if="log.before_value" class="audit-json-label">Before:</div>
                <pre v-if="log.before_value" class="audit-json">{{ typeof log.before_value === 'string' ? log.before_value : JSON.stringify(log.before_value, null, 2) }}</pre>
                <div v-if="log.after_value" class="audit-json-label">After:</div>
                <pre v-if="log.after_value" class="audit-json">{{ typeof log.after_value === 'string' ? log.after_value : JSON.stringify(log.after_value, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="helper-text" style="margin-top:8px">{{ auditLogs.length }} {{ t('action.records_total') }}</div>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { max-width:1500px; margin:0 auto; padding:24px; font-size:15px; }

/* ── Header ── */
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.header-left { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.header-left h3 { margin:0; font-size:1.25rem; font-weight:700; color:#1d2a3a; }
.header-actions { display:flex; gap:6px; flex-wrap:wrap; }

/* ── Chips ── */
.rollback-chip { background:#fce4ec; color:#c62828; padding:2px 10px; border-radius:12px; font-size:.8rem; font-weight:600; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ── Workflow ── */
.workflow-bar { display:flex; align-items:center; margin-bottom:20px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:12px 24px; }
.wf-step { display:flex; align-items:center; gap:8px; }
.wf-dot { width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.8rem; font-weight:700; border:2px solid #d1d5db; color:#9ca3af; background:#f9fafb; transition:all .3s; }
.wf-active .wf-dot { border-color:#1B6CB2; color:#1B6CB2; background:#eff6ff; }
.wf-current .wf-dot { background:#1B6CB2; color:#fff; border-color:#1B6CB2; }
.wf-label { font-size:.85rem; color:#9ca3af; font-weight:600; white-space:nowrap; }
.wf-active .wf-label { color:#1B6CB2; }
.wf-line { width:44px; height:2px; background:#d1d5db; margin:0 12px; }
.wf-active .wf-line { background:#1B6CB2; }

/* ── Summary ── */
.summary-row { display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }
.summary-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px 20px; text-align:center; flex:1; min-width:130px; }
.s-label { font-size:.75rem; color:#6b7280; margin-bottom:4px; text-transform:uppercase; letter-spacing:.03em; }
.s-value { font-size:1.3rem; font-weight:700; color:#1d2a3a; }

/* ── Info ── */
.info-section { margin-bottom:20px; }

/* ── Records ── */
.section-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.section-head h4 { margin:0; font-size:1rem; font-weight:700; }
.table-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.table-card :deep(.el-table) { width: 100% !important; }
.table-card :deep(.el-table__body-wrapper) { overflow-x: auto !important; }

/* ── Edit Dialog ── */
.edit-group-title { font-size:.85rem; font-weight:700; color:#1B6CB2; padding-bottom:4px; margin:0 0 8px 0; border-bottom:1px solid #e5e7eb; }

/* ── Audit ── */
.audit-item { cursor:pointer; padding:8px 0; border-bottom:1px solid #f3f4f6; transition:background .15s; }
.audit-item:hover { background:#fafbfc; }
.audit-line { display:flex; gap:12px; align-items:flex-start; }
.audit-body { flex:1; min-width:0; }
.audit-head { display:flex; align-items:center; gap:10px; margin-bottom:3px; }
.audit-user { font-weight:600; color:#1d2a3a; font-size:.9rem; }
.audit-time { color:#9ca3af; font-size:.8rem; margin-left:auto; }
.audit-summary { color:#6b7280; font-size:.85rem; }
.audit-expand { margin-top:8px; padding:8px 10px; background:#f9fafb; border-radius:6px; }
.audit-json-label { font-size:.75rem; font-weight:700; color:#6b7280; margin:4px 0 2px; }
.audit-json { font-size:.75rem; color:#1d2a3a; white-space:pre-wrap; word-break:break-all; margin:0; }

/* ── Misc ── */
.helper-text { color:#6b7280; font-size:.85rem; }
</style>
