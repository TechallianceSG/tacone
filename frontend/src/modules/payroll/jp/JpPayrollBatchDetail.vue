<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ── State ──
const loading = ref(false)
const calcLoading = ref(false)
const confirmLoading = ref(false)
const batch = ref<any>({})
const records = ref<any[]>([])

// Editable tracking
const editingRecordId = ref<string | null>(null)
const editForm = ref<Record<string, any>>({})
const savingRecord = ref(false)

// Entity dropdown
const entities = ref<any[]>([])

// ── Status helpers ──
const statusConfig: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.jp.status_draft' },
  calculated: { type: 'warning', label: 'payroll.jp.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.jp.status_confirmed' },
  voided: { type: 'danger', label: 'payroll.jp.status_voided' },
}

const statusWorkflow = ['draft', 'calculated', 'confirmed']

function statusIndex(status: string): number {
  return statusWorkflow.indexOf(status)
}

function canCalculate(): boolean {
  return batch.value.status === 'draft'
}

function canConfirm(): boolean {
  return batch.value.status === 'calculated'
}

function canEditRecords(): boolean {
  return batch.value.status === 'draft'
}

// ── Methods ──
async function load() {
  loading.value = true
  const id = route.params.id as string
  try {
    const [sheetRes, entitiesRes] = await Promise.all([
      payrollJpApi.getSheet(id).catch(() => payrollJpApi.getBatch(id)),
      fetch('/api/masterdata/entities').then(r => r.json()).catch(() => ({ data: [] })),
    ])
    entities.value = entitiesRes.data || []
    batch.value = sheetRes.data.data || sheetRes.data || {}
    records.value = batch.value.records || batch.value.items || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function entityLabel(entityId: string) {
  const found = entities.value.find((e: any) => e.entity_id === entityId)
  if (!found) return entityId
  return `${found.entity_code || found.entity_id} - ${found.entity_name || ''} (${found.country || ''})`
}

async function calculate() {
  calcLoading.value = true
  try {
    const id = route.params.id as string
    await payrollJpApi.calculateBatch(id)
    ElMessage.success(t('payroll.jp.calculated'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { calcLoading.value = false }
}

async function confirmSheet() {
  try {
    await ElMessageBox.confirm(
      t('payroll.jp.confirm_confirm_msg'),
      t('payroll.jp.confirm_sheet'),
      { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
  } catch { return }

  confirmLoading.value = true
  try {
    const id = route.params.id as string
    await payrollJpApi.confirmSheet(id)
    ElMessage.success(t('payroll.jp.confirmed'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { confirmLoading.value = false }
}

function goToRelease() {
  router.push(`/payroll/jp/batches/${route.params.id}/release`)
}

// ── Inline Editing ──
function startEdit(record: any) {
  editingRecordId.value = record.record_id || record.id
  editForm.value = { ...record }
}

function cancelEdit() {
  editingRecordId.value = null
  editForm.value = {}
}

async function saveRecord() {
  savingRecord.value = true
  try {
    const id = route.params.id as string
    await payrollJpApi.saveSheetRecords(id, { records: [editForm.value] })
    editingRecordId.value = null
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { savingRecord.value = false }
}

// ── Summary Cards ──
const summaryCards = computed(() => {
  const b = batch.value
  return [
    { label: t('field.employee_count'), value: b.employee_count || records.value.length || 0, color: '', format: false },
    { label: t('field.gross_total'), value: b.gross_total || 0, color: '', format: true },
    { label: t('field.deduction_total'), value: b.deduction_total || 0, color: 'var(--el-color-danger)', format: true },
    { label: t('field.net_total'), value: b.net_total || 0, color: 'var(--el-color-primary)', format: true },
    { label: t('field.employer_cost_total'), value: b.employer_cost_total || 0, color: 'var(--el-color-warning)', format: true },
  ]
})

// Editable field definitions for inline edit
const editableFields = [
  { key: 'actual_work_days', label: 'field.actual_work_days', min: 0, max: 31, precision: 1, width: 6 },
  { key: 'actual_work_hours', label: 'field.actual_work_hours', min: 0, precision: 1, width: 6 },
  { key: 'overtime_hours', label: 'field.overtime_hours', min: 0, precision: 1, width: 6 },
  { key: 'paid_leave_days', label: 'field.paid_leave_days', min: 0, precision: 1, width: 6 },
  { key: 'sick_leave_days', label: 'field.sick_leave_days', min: 0, precision: 1, width: 6 },
  { key: 'commute_allowance', label: 'field.commute_allowance', min: 0, precision: 0, width: 6 },
  { key: 'housing_allowance', label: 'field.housing_allowance', min: 0, precision: 0, width: 6 },
  { key: 'family_allowance', label: 'field.family_allowance', min: 0, precision: 0, width: 6 },
  { key: 'position_allowance', label: 'field.position_allowance', min: 0, precision: 0, width: 6 },
  { key: 'fixed_allowance', label: 'field.fixed_allowance', min: 0, precision: 0, width: 6 },
  { key: 'transport_allowance', label: 'field.transport_allowance', min: 0, precision: 0, width: 6 },
  { key: 'phone_allowance', label: 'field.phone_allowance', min: 0, precision: 0, width: 6 },
  { key: 'project_bonus', label: 'field.project_bonus', min: 0, precision: 0, width: 6 },
  { key: 'performance_bonus', label: 'field.performance_bonus', min: 0, precision: 0, width: 6 },
  { key: 'other_allowance', label: 'field.other_allowance', min: 0, precision: 0, width: 6 },
  { key: 'other_deduction', label: 'field.other_deduction', min: 0, precision: 0, width: 6 },
]

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <h3>{{ t('payroll.jp.batch_detail') }}</h3>
        <el-tag v-if="batch.status" :type="(statusConfig[batch.status]?.type || '') as any" size="default">
          {{ t(statusConfig[batch.status]?.label || batch.status) }}
        </el-tag>
        <span v-if="batch.sheet_id || batch.batch_id" class="helper-text">{{ batch.sheet_id || batch.batch_id }}</span>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <el-button v-if="canCalculate()" type="primary" :loading="calcLoading" @click="calculate">
          {{ t('payroll.jp.calculate') }}
        </el-button>
        <el-button v-if="canConfirm()" type="success" :loading="confirmLoading" @click="confirmSheet">
          {{ t('payroll.jp.confirm') }}
        </el-button>
        <el-button v-if="batch.status === 'confirmed'" type="success" plain @click="goToRelease">
          {{ t('action.release') }} →
        </el-button>
      </div>
    </div>

    <!-- Workflow Steps -->
    <div class="workflow-bar">
      <div
        v-for="(step, idx) in statusWorkflow"
        :key="step"
        class="workflow-step"
        :class="{
          'step-active': statusIndex(batch.status) >= idx,
          'step-current': statusIndex(batch.status) === idx
        }"
      >
        <div class="step-indicator"><span class="step-number">{{ idx + 1 }}</span></div>
        <div class="step-label">{{ t('payroll.jp.status_' + step) }}</div>
        <div v-if="idx < statusWorkflow.length - 1" class="step-connector" />
      </div>
    </div>

    <!-- Summary Cards -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="4" v-for="(card, i) in summaryCards" :key="i" style="min-width:160px;flex:1">
        <div class="summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value" :style="{ color: card.color || undefined }">
            <template v-if="card.format">¥{{ Number(card.value).toLocaleString() }}</template>
            <template v-else>{{ card.value }}</template>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Sheet Info -->
    <el-descriptions :column="4" border size="small" style="margin-bottom:20px">
      <el-descriptions-item :label="t('field.payroll_month')">{{ batch.payroll_month || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ entityLabel(batch.entity_id) }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.sheet_id')">{{ batch.sheet_id || batch.batch_id || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.created_by')">{{ batch.created_by || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.notes')" :span="4">{{ batch.notes || '-' }}</el-descriptions-item>
    </el-descriptions>

    <!-- Records Section -->
    <div class="table-header">
      <h4>{{ t('payroll.jp.sheet_records') }}</h4>
      <div class="helper-text">{{ records.length }} {{ t('action.records_total') }}</div>
    </div>

    <el-table :data="records" v-loading="loading" border stripe size="small" max-height="500">
      <el-table-column type="index" width="40" label="#" />
      <el-table-column prop="employee_number" :label="t('field.employee_number')" width="110" fixed />
      <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="130" fixed show-overflow-tooltip />
      <el-table-column prop="base_pay_calculated" :label="t('field.base_pay')" width="110" align="right">
        <template #default="{row}">{{ row.base_pay_calculated ? Number(row.base_pay_calculated).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="gross_pay" :label="t('field.gross_pay')" width="120" align="right">
        <template #default="{row}">{{ row.gross_pay ? Number(row.gross_pay).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.health_insurance')" width="100" align="right">
        <template #default="{row}">{{ row.health_insurance_employee ? Number(row.health_insurance_employee).toLocaleString() : row.health_insurance ? Number(row.health_insurance).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.pension')" width="100" align="right">
        <template #default="{row}">{{ row.pension_employee ? Number(row.pension_employee).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.employment_insurance')" width="100" align="right">
        <template #default="{row}">{{ row.employment_insurance_employee ? Number(row.employment_insurance_employee).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.care_insurance')" width="100" align="right">
        <template #default="{row}">{{ row.care_insurance_employee ? Number(row.care_insurance_employee).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.income_tax')" width="100" align="right">
        <template #default="{row}">{{ row.income_tax ? Number(row.income_tax).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('field.monthly_resident_tax')" width="100" align="right">
        <template #default="{row}">{{ row.monthly_resident_tax ? Number(row.monthly_resident_tax).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="deduction_total" :label="t('field.deduction_total')" width="110" align="right">
        <template #default="{row}">
          <strong>{{ row.deduction_total ? Number(row.deduction_total).toLocaleString() : '-' }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="net_pay" :label="t('field.net_pay')" width="110" align="right">
        <template #default="{row}">
          <strong style="color:var(--el-color-primary)">{{ row.net_pay ? Number(row.net_pay).toLocaleString() : '-' }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="employer_cost_total" :label="t('field.employer_cost_total')" width="120" align="right">
        <template #default="{row}">
          <span style="color:var(--el-color-warning)">{{ row.employer_cost_total ? Number(row.employer_cost_total).toLocaleString() : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('field.actions')" width="70" fixed="right" v-if="canEditRecords()">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="startEdit(row)">{{ t('action.edit') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Inline Edit Panel (shown below table when editing a record) -->
    <div v-if="editingRecordId && canEditRecords()" class="edit-panel">
      <div class="edit-panel-header">
        <strong>{{ t('action.edit') }} — {{ editForm.employee_name }} ({{ editForm.employee_number }})</strong>
      </div>
      <el-row :gutter="12">
        <el-col :span="4" v-for="f in editableFields" :key="f.key">
          <el-form-item :label="t(f.label)" size="small">
            <el-input-number v-model="editForm[f.key]" :min="f.min" :precision="f.precision" style="width:100%" size="small" />
          </el-form-item>
        </el-col>
      </el-row>
      <div style="text-align:right;margin-top:12px">
        <el-button size="small" @click="cancelEdit">{{ t('action.cancel') }}</el-button>
        <el-button size="small" type="primary" :loading="savingRecord" @click="saveRecord">{{ t('action.save') }}</el-button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !batch.sheet_id && !batch.batch_id" class="empty-state">
      <el-empty :description="t('payroll.jp.batch_not_found')" />
    </div>
  </div>
</template>

<style scoped>
.page-container { max-width:1600px; margin:0 auto; padding:24px; font-size:15px; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.page-header h3 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }

.workflow-bar { display:flex; align-items:flex-start; margin-bottom:24px; gap:0; overflow-x:auto; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px 20px; }
.workflow-step { display:flex; align-items:center; position:relative; flex-shrink:0; }
.step-indicator { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.85rem; font-weight:700; border:2px solid #d1d5db; color:#9ca3af; background:#f9fafb; transition:all .3s; }
.step-active .step-indicator { border-color:#1B6CB2; color:#1B6CB2; background:#eff6ff; }
.step-current .step-indicator { background:#1B6CB2; color:#fff; border-color:#1B6CB2; }
.step-label { margin-left:6px; font-size:.85rem; color:#9ca3af; white-space:nowrap; font-weight:600; }
.step-active .step-label { color:#1B6CB2; }
.step-connector { width:50px; height:2px; background:#d1d5db; margin:0 8px; align-self:center; margin-top:-16px; }
.step-active .step-connector { background:#1B6CB2; }

.summary-row { margin-bottom:20px; display:flex; flex-wrap:wrap; gap:12px; }
.summary-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:18px; text-align:center; flex:1; min-width:140px; }
.summary-label { font-size:.78rem; color:#6b7280; margin-bottom:6px; text-transform:uppercase; letter-spacing:.03em; }
.summary-value { font-size:1.35rem; font-weight:700; color:#1d2a3a; }

.table-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.table-header h4 { margin:0; font-size:1rem; font-weight:700; color:#1d2a3a; }

.edit-panel { border:1px solid #1B6CB2; border-radius:10px; padding:16px; margin-top:12px; background:#eff6ff; }
.edit-panel-header { margin-bottom:12px; font-size:.95rem; font-weight:700; color:#1B6CB2; }

.helper-text { color:#6b7280; font-size:.85rem; }
.empty-state { margin-top:40px; }
</style>
