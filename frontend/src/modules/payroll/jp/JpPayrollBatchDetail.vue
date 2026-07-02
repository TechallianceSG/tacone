<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const { t } = useI18n()

// ── State ──
const loading = ref(false)
const batch = ref<any>({})
const records = ref<any[]>([])

// Action loading states
const calcLoading = ref(false)
const confirmLoading = ref(false)
const rollbackLoading = ref(false)

// Edit dialog
const editDialog = ref(false)
const editRecord = ref<any>(null)
const editForm = ref<Record<string, any>>({})
const savingRecord = ref(false)

// Recalculate per-row
const recalculatingIds = ref<Set<string>>(new Set())

// Rollback dialog
const rollbackDialog = ref(false)
const rollbackReason = ref('')

// Audit log dialog
const auditDialog = ref(false)
const auditLogs = ref<any[]>([])
const auditLoading = ref(false)

// Expanded audit detail
const expandedAudit = ref<Set<number>>(new Set())

// Records pagination
const recPage = ref(1)
const recPageSize = ref(20)
const pagedRecords = computed(() => {
  const start = (recPage.value - 1) * recPageSize.value
  return records.value.slice(start, start + recPageSize.value)
})

// Entities for labels
const entities = ref<any[]>([])

// ── Status config ──
const statusConfig: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.jp.status_draft' },
  calculated: { type: 'warning', label: 'payroll.jp.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.jp.status_confirmed' },
  voided: { type: 'danger', label: 'payroll.jp.status_voided' },
}
const statusWorkflow = ['draft', 'calculated', 'confirmed']
function statusIndex(s: string) { return statusWorkflow.indexOf(s) }

// ── Permission helpers ──
function canCalculate() { return batch.value.status === 'draft' || batch.value.status === 'calculated' }
function canConfirm() { return batch.value.status === 'calculated' }
function canEditRecords() { return batch.value.status === 'draft' || batch.value.status === 'calculated' }
function canRecalculateSingle() { return batch.value.status === 'calculated' }
function canRollback() { return batch.value.status === 'confirmed' }
function isManuallyEdited(r: any) { return r.manually_edited === true || r.manually_edited === 'true' || r.manually_edited === 1 }

// ── Audit action labels ──
const actionLabels: Record<string, { icon: string; label: string; color: string }> = {
  CALCULATE:           { icon: '🧮', label: '批量计算', color: '#409EFF' },
  RECALCULATE:         { icon: '🔄', label: '重新计算', color: '#409EFF' },
  RECALCULATE_SINGLE:  { icon: '🔁', label: '逐条重算', color: '#409EFF' },
  CONFIRM:             { icon: '✅', label: '定稿', color: '#67C23A' },
  ROLLBACK:            { icon: '↩️', label: '回退', color: '#E6A23C' },
  EDIT_RECORD:         { icon: '✏️', label: '编辑记录', color: '#909399' },
  EMAIL_SENT:          { icon: '📧', label: '发送邮件', color: '#409EFF' },
  EMAIL_BATCH_SENT:    { icon: '📧', label: '批量发送', color: '#409EFF' },
  EMAIL_SELECTED_SENT: { icon: '📧', label: '选中发送', color: '#409EFF' },
  VOID:                { icon: '🚫', label: '作废', color: '#F56C6C' },
  DELETE:              { icon: '🗑️', label: '删除', color: '#F56C6C' },
}

function actionLabel(action: string) {
  return actionLabels[action] || { icon: '📋', label: action, color: '#909399' }
}

function parseAuditValue(v: any): string {
  if (!v) return ''
  try {
    const obj = typeof v === 'string' ? JSON.parse(v) : v
    // Extract key fields for summary
    const parts: string[] = []
    if (obj.status) parts.push(`状态→${obj.status}`)
    if (obj.employee_count !== undefined) parts.push(`${obj.employee_count}人`)
    if (obj.gross_total !== undefined) parts.push(`应发¥${Number(obj.gross_total).toLocaleString()}`)
    if (obj.net_total !== undefined) parts.push(`实发¥${Number(obj.net_total).toLocaleString()}`)
    if (obj.reason) parts.push(`原因: ${obj.reason}`)
    if (obj.email_status) parts.push(`邮件: ${obj.email_status}`)
    if (obj.sent !== undefined) parts.push(`成功${obj.sent}封${obj.failed ? ` 失败${obj.failed}封` : ''}`)
    if (parts.length) return parts.join(' | ')
    return JSON.stringify(obj).substring(0, 150)
  } catch { return String(v).substring(0, 150) }
}

// ── Data loading ──
async function load() {
  loading.value = true
  const id = route.params.id as string
  try {
    const [batchRes, entitiesRes] = await Promise.all([
      payrollJpApi.getBatch(id),
      payrollJpApi.entities().catch(() => ({ data: { data: [] } })),
    ])
    entities.value = entitiesRes.data?.data || []
    batch.value = batchRes.data.data || batchRes.data || {}
    records.value = batch.value.records || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function entityLabel(entityId: string) {
  const found = entities.value.find((e: any) => e.entity_id === entityId)
  if (!found) return entityId
  return `${found.entity_code || found.entity_id} - ${found.entity_name || ''} (${found.country || ''})`
}

// ── Calculate / Recalculate ──
async function calculate() {
  const isRecalc = batch.value.status === 'calculated'
  if (isRecalc) {
    try {
      await ElMessageBox.confirm(t('payroll.jp.recalculate_confirm_msg'), t('payroll.jp.recalculate'),
        { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' })
    } catch { return }
  }
  calcLoading.value = true
  try {
    const id = route.params.id as string
    const res = await payrollJpApi.calculateBatch(id)
    const data = res.data?.data || res.data || {}
    if (data.warning) { ElMessage.warning(data.warning) }
    else { ElMessage.success(isRecalc ? t('payroll.jp.recalculated') : t('payroll.jp.calculated')) }
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { calcLoading.value = false }
}

async function recalculateSingle(record: any) {
  const id = record.record_id || record.id
  recalculatingIds.value.add(id)
  try {
    await payrollJpApi.recalculateSingleRecord(route.params.id as string, id)
    ElMessage.success(t('payroll.jp.recalculated'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { recalculatingIds.value.delete(id) }
}

// ── Confirm ──
async function confirmSheet() {
  try {
    await ElMessageBox.confirm(t('payroll.jp.confirm_confirm_msg'), t('payroll.jp.confirm_sheet'),
      { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' })
  } catch { return }
  confirmLoading.value = true
  try {
    const res = await payrollJpApi.confirmSheet(route.params.id as string)
    const data = res.data?.data || res.data || {}
    ElMessage.success(t('payroll.jp.confirmed') + (data.payslips_generated ? ` (${data.payslips_generated} payslips)` : ''))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { confirmLoading.value = false }
}

// ── Rollback ──
function openRollback() { rollbackReason.value = ''; rollbackDialog.value = true }
async function confirmRollback() {
  if (!rollbackReason.value.trim()) { ElMessage.warning(t('payroll.jp.rollback_reason_required')); return }
  rollbackLoading.value = true
  try {
    await payrollJpApi.rollbackBatch(route.params.id as string, { reason: rollbackReason.value })
    rollbackDialog.value = false
    ElMessage.success(t('payroll.jp.rolled_back'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { rollbackLoading.value = false }
}

// ── Edit Dialog ──
function openEdit(record: any) {
  editRecord.value = record
  editForm.value = { ...record }
  editDialog.value = true
}
async function saveEdit() {
  savingRecord.value = true
  try {
    const batchId = route.params.id as string
    const recordId = editForm.value.record_id || editForm.value.id
    await payrollJpApi.editRecord(batchId, recordId, editForm.value)
    editDialog.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { savingRecord.value = false }
}

// ── Audit Logs ──
async function openAuditLogs() {
  auditDialog.value = true
  auditLoading.value = true
  try {
    const res = await payrollJpApi.getBatchAuditLogs(route.params.id as string)
    auditLogs.value = res.data?.data?.items || res.data?.data || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { auditLoading.value = false }
}

function toggleAuditDetail(idx: number) {
  if (expandedAudit.value.has(idx)) { expandedAudit.value.delete(idx) }
  else { expandedAudit.value.add(idx) }
}

// ── Summary cards ──
const summaryCards = computed(() => {
  const b = batch.value
  return [
    { label: t('field.employee_count'), value: b.employee_count || records.value.length || 0, format: false },
    { label: t('field.gross_total'), value: b.gross_total || 0, format: true, color: '' },
    { label: t('field.deduction_total'), value: b.deduction_total || 0, format: true, color: 'var(--el-color-danger)' },
    { label: t('field.net_total'), value: b.net_total || 0, format: true, color: 'var(--el-color-primary)' },
    { label: t('field.employer_cost_total'), value: b.employer_cost_total || 0, format: true, color: 'var(--el-color-warning)' },
  ]
})

// ── Editable fields for dialog ──
const editFields = [
  { key: 'absence_days', label: 'field.absence_days', min: 0, max: 31, precision: 1 },
  { key: 'actual_work_days', label: 'field.actual_work_days', min: 0, max: 31, precision: 1 },
  { key: 'actual_work_hours', label: 'field.actual_work_hours', min: 0, precision: 1 },
  { key: 'overtime_hours', label: 'field.overtime_hours', min: 0, precision: 1 },
  { key: 'commute_allowance', label: 'field.commute_allowance', min: 0, precision: 0 },
  { key: 'housing_allowance', label: 'field.housing_allowance', min: 0, precision: 0 },
  { key: 'transport_allowance', label: 'field.transport_allowance', min: 0, precision: 0 },
  { key: 'phone_allowance', label: 'field.phone_allowance', min: 0, precision: 0 },
  { key: 'performance_bonus', label: 'field.performance_bonus', min: 0, precision: 0 },
  { key: 'project_bonus', label: 'field.project_bonus', min: 0, precision: 0 },
  { key: 'other_allowance', label: 'field.other_allowance', min: 0, precision: 0 },
  { key: 'other_deduction', label: 'field.other_deduction', min: 0, precision: 0 },
]

function fmt(v: any) { return v != null ? Number(v).toLocaleString() : '-' }

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- ═══ Header ═══ -->
    <div class="page-header">
      <div class="header-left">
        <h3>{{ t('payroll.jp.batch_detail') }}</h3>
        <el-tag v-if="batch.status" :type="(statusConfig[batch.status]?.type || '') as any" size="default">
          {{ t(statusConfig[batch.status]?.label || batch.status) }}
        </el-tag>
        <span class="helper-text">{{ batch.batch_id || batch.sheet_id || '-' }}</span>
        <span v-if="batch.recalculate_count > 0" class="recalc-chip">🔄 {{ t('payroll.jp.recalculate_count') }}: {{ batch.recalculate_count }}</span>
        <span v-if="batch.rollback_reason" class="rollback-chip">↩ {{ batch.rollback_reason }}</span>
      </div>
      <div class="header-actions">
        <el-button v-if="canCalculate()" type="primary" :loading="calcLoading" @click="calculate">
          {{ batch.status === 'calculated' ? t('payroll.jp.recalculate') : t('payroll.jp.calculate') }}
        </el-button>
        <el-button v-if="canConfirm()" type="success" :loading="confirmLoading" @click="confirmSheet">
          {{ t('payroll.jp.confirm') }}
        </el-button>
        <el-button v-if="canRollback()" type="warning" plain @click="openRollback">
          {{ t('payroll.jp.rollback') }}
        </el-button>
        <el-button @click="openAuditLogs">{{ t('payroll.jp.audit_log') }}</el-button>
      </div>
    </div>

    <!-- ═══ Workflow Steps ═══ -->
    <div class="workflow-bar">
      <div v-for="(step, idx) in statusWorkflow" :key="step" class="wf-step"
        :class="{ 'wf-active': statusIndex(batch.status) >= idx, 'wf-current': statusIndex(batch.status) === idx }">
        <div class="wf-dot">{{ idx + 1 }}</div>
        <span class="wf-label">{{ t('payroll.jp.status_' + step) }}</span>
        <div v-if="idx < statusWorkflow.length - 1" class="wf-line" />
      </div>
    </div>

    <!-- ═══ Summary Cards ═══ -->
    <div class="summary-row">
      <div v-for="(card, i) in summaryCards" :key="i" class="summary-card">
        <div class="s-label">{{ card.label }}</div>
        <div class="s-value" :style="{ color: card.color || undefined }">
          {{ card.format ? '¥' + Number(card.value).toLocaleString() : card.value }}
        </div>
      </div>
    </div>

    <!-- ═══ Info ═══ -->
    <el-descriptions :column="4" border size="small" class="info-section">
      <el-descriptions-item :label="t('field.payroll_month')">{{ batch.payroll_month }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ entityLabel(batch.entity_id) }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.working_days_in_month')">{{ batch.working_days_in_month || 22 }} {{ t('field.days') }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.created_by')">{{ batch.created_by || '-' }}</el-descriptions-item>
    </el-descriptions>

    <!-- ═══ Records Table ═══ -->
    <div class="section-head">
      <h4>{{ t('payroll.jp.sheet_records') }}</h4>
    </div>

    <div class="table-card" v-loading="loading">
      <el-table :data="pagedRecords" border stripe size="small" max-height="480" :empty-text="t('payroll.jp.no_records')" style="width:100%">
        <el-table-column type="index" min-width="45" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="110" />
        <el-table-column min-width="140" show-overflow-tooltip>
          <template #header>{{ t('field.employee_name') }}</template>
          <template #default="{row}">
            {{ row.employee_name }}
            <el-tag v-if="isManuallyEdited(row)" size="small" type="warning" effect="plain" class="ml-6">{{ t('payroll.jp.manually_edited') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="salary_type" :label="t('field.salary_type_label')" min-width="100" align="center" />
        <el-table-column :label="t('field.base_pay')" min-width="100" align="right">
          <template #default="{row}">{{ fmt(row.base_pay_calculated) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.gross_pay')" min-width="110" align="right">
          <template #default="{row}">{{ fmt(row.gross_pay) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.deduction_total')" min-width="110" align="right">
          <template #default="{row}"><span style="color:var(--el-color-danger)">{{ fmt(row.deduction_total) }}</span></template>
        </el-table-column>
        <el-table-column :label="t('field.net_pay')" min-width="110" align="right">
          <template #default="{row}"><strong style="color:var(--el-color-primary)">{{ fmt(row.net_pay) }}</strong></template>
        </el-table-column>
        <!-- Actions -->
        <el-table-column :label="t('field.actions')" min-width="160" fixed="right" v-if="canEditRecords() || canRecalculateSingle()">
          <template #default="{row}">
            <el-button v-if="canEditRecords()" size="small" text type="primary" @click="openEdit(row)">{{ t('action.edit') }}</el-button>
            <el-button v-if="canRecalculateSingle()" size="small" text type="warning"
              :loading="recalculatingIds.has(row.record_id || row.id)" @click="recalculateSingle(row)">
              {{ t('payroll.jp.recalculate_single') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
        <span class="helper-text">{{ records.length }} {{ t('action.records_total') }}</span>
        <el-pagination
          v-model:current-page="recPage" v-model:page-size="recPageSize"
          :page-sizes="[10, 20, 50, 100]" :total="records.length"
          layout="total, sizes, prev, pager, next, jumper"
          background small
        />
      </div>
    </div>

    <!-- ═══ Edit Dialog ═══ -->
    <el-dialog v-model="editDialog" :title="t('action.edit') + ' — ' + (editRecord?.employee_name || '')" width="620px" destroy-on-close>
      <el-alert :title="t('payroll.jp.edit_hint')" type="info" :closable="false" show-icon style="margin-bottom:16px" />
      <el-row :gutter="12">
        <el-col :span="8" v-for="f in editFields" :key="f.key">
          <el-form-item :label="t(f.label)" size="small">
            <el-input-number v-model="editForm[f.key]" :min="f.min" :precision="f.precision" style="width:100%" size="small" controls-position="right" />
          </el-form-item>
        </el-col>
      </el-row>
      <template #footer>
        <el-button @click="editDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="savingRecord" @click="saveEdit">{{ t('action.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- ═══ Rollback Dialog ═══ -->
    <el-dialog v-model="rollbackDialog" :title="t('payroll.jp.rollback_confirm_title')" width="500px" top="15vh">
      <el-alert :title="t('payroll.jp.rollback_confirm_msg')" type="warning" :closable="false" show-icon style="margin-bottom:16px" />
      <el-input v-model="rollbackReason" type="textarea" :rows="3" :placeholder="t('payroll.jp.rollback_reason_placeholder')" maxlength="500" show-word-limit />
      <template #footer>
        <el-button @click="rollbackDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="warning" :loading="rollbackLoading" @click="confirmRollback">{{ t('payroll.jp.rollback') }}</el-button>
      </template>
    </el-dialog>

    <!-- ═══ Audit Log Dialog (Timeline Style) ═══ -->
    <el-dialog v-model="auditDialog" :title="t('payroll.jp.audit_log')" width="750px" top="5vh">
      <div v-loading="auditLoading" style="max-height:520px;overflow-y:auto">
        <div v-if="auditLogs.length === 0 && !auditLoading" style="text-align:center;padding:40px;color:#9ca3af">
          {{ t('payroll.jp.no_records') }}
        </div>
        <div v-for="(log, idx) in auditLogs" :key="idx" class="audit-item" @click="toggleAuditDetail(idx)">
          <div class="audit-line">
            <div class="audit-body">
              <div class="audit-head">
                <el-tag size="small" :color="actionLabel(log.action).color" effect="dark" style="color:#fff">
                  {{ actionLabel(log.action).label }}
                </el-tag>
                <span class="audit-user">{{ log.user_name }}</span>
                <span class="audit-time">{{ (log.created_at || '').replace('T', ' ').substring(0, 19) }}</span>
              </div>
              <div class="audit-summary">{{ parseAuditValue(log.after_value) || parseAuditValue(log.before_value) || '—' }}</div>
              <!-- Expanded detail -->
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
.recalc-chip { background:#fef3c7; color:#92400e; padding:2px 10px; border-radius:12px; font-size:.8rem; font-weight:600; }
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

/* ── Audit Timeline ── */
.audit-item { cursor:pointer; padding:8px 0; border-bottom:1px solid #f3f4f6; transition:background .15s; }
.audit-item:hover { background:#fafbfc; }
.audit-line { display:flex; gap:12px; align-items:flex-start; }
.audit-icon { font-size:1.2rem; width:32px; text-align:center; flex-shrink:0; padding-top:2px; }
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
.ml-6 { margin-left:6px; }
</style>
