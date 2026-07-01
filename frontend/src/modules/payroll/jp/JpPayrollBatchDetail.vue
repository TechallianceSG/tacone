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
const deleteLoading = ref(false)
const savingRecords = ref(false)
const batch = ref<any>({})
const records = ref<any[]>([])
const calcWarnings = ref<string[]>([])
const calcSummary = ref<any>(null)

// Editable record tracking
const editingRecords = ref<Set<string>>(new Set())

// Entity dropdown
const entities = ref<any[]>([])

// ── Status helpers ──
const statusColors: Record<string, string> = {
  draft: '',
  calculated: 'warning',
  confirmed: 'success',
  voided: 'danger',
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

function canDelete(): boolean {
  return batch.value.status === 'voided' || batch.value.status === 'draft'
}

function canEditRecords(): boolean {
  return batch.value.status === 'draft'
}

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const [batchesRes, entitiesRes] = await Promise.all([
      payrollJpApi.batches(),
      fetch('/api/masterdata/entities').then(r => r.json()).catch(() => ({ data: [] })),
    ])
    entities.value = entitiesRes.data || []
    const allBatches = batchesRes.data.data?.items || []
    batch.value = allBatches.find((b: any) => b.batch_id === route.params.id || b.sheet_id === route.params.id) || {}
    records.value = batch.value.records || batch.value.items || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

async function calculate() {
  calcLoading.value = true
  calcWarnings.value = []
  calcSummary.value = null
  try {
    const res = await payrollJpApi.calculateBatch(route.params.id as string)
    ElMessage.success(t('payroll.jp.calculated'))
    // Reload to get updated data with calculation results
    await load()
    // Check for warnings in the response
    if (res.data?.warnings?.length) {
      calcWarnings.value = res.data.warnings
    }
    if (res.data?.summary) {
      calcSummary.value = res.data.summary
    }
  } catch (e: any) {
    ElMessage.error(e.message)
  }
  finally { calcLoading.value = false }
}

async function confirmSheet() {
  try {
    await ElMessageBox.confirm(
      t('payroll.jp.confirm_confirm_msg'),
      t('payroll.jp.confirm_sheet'),
      { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
  } catch {
    return // User cancelled
  }

  confirmLoading.value = true
  try {
    await payrollJpApi.confirmSheet(route.params.id as string)
    ElMessage.success(t('payroll.jp.confirmed'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { confirmLoading.value = false }
}

async function deleteSheet() {
  try {
    await ElMessageBox.confirm(
      t('payroll.jp.delete_confirm_msg'),
      t('action.delete'),
      { confirmButtonText: t('action.delete'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
  } catch {
    return
  }

  deleteLoading.value = true
  try {
    // Mark as deleted by voiding
    await payrollJpApi.confirmSheet(route.params.id as string)
    ElMessage.success(t('payroll.jp.sheet_deleted'))
    router.push('/payroll/jp/batches')
  } catch (e: any) { ElMessage.error(e.message) }
  finally { deleteLoading.value = false }
}

// ── Record Editing ──
function toggleEditRecord(recordId: string) {
  if (editingRecords.value.has(recordId)) {
    editingRecords.value.delete(recordId)
  } else {
    editingRecords.value.add(recordId)
  }
}

function isEditingRecord(recordId: string): boolean {
  return editingRecords.value.has(recordId)
}

async function saveRecord(record: any) {
  savingRecords.value = true
  try {
    await payrollJpApi.saveEmployee({
      record_id: record.record_id || record.id,
      sheet_id: route.params.id,
      actual_work_days: record.actual_work_days,
      actual_work_hours: record.actual_work_hours,
      overtime_hours: record.overtime_hours,
      commute_allowance: record.commute_allowance,
      housing_allowance: record.housing_allowance,
      family_allowance: record.family_allowance,
      position_allowance: record.position_allowance,
      fixed_allowance: record.fixed_allowance,
      transport_allowance: record.transport_allowance,
      phone_allowance: record.phone_allowance,
      project_bonus: record.project_bonus,
      performance_bonus: record.performance_bonus,
    })
    editingRecords.value.delete(record.record_id || record.id)
    ElMessage.success(t('action.saved'))
  } catch (e: any) { ElMessage.error(e.message) }
  finally { savingRecords.value = false }
}

// ── Computed ──
const entityLabel = computed(() => {
  if (!batch.value.entity_id) return batch.value.entity_id || '-'
  const found = entities.value.find((e: any) => e.entity_id === batch.value.entity_id)
  if (!found) return batch.value.entity_id
  return `${found.entity_code || ''} - ${found.entity_name || ''} (${found.country || ''})`
})

const summaryCards = computed(() => {
  return [
    { label: t('field.employee_count'), value: batch.value.employee_count || records.value.length || 0, color: '' },
    { label: t('field.gross_total'), value: batch.value.gross_total || 0, color: '', format: true },
    { label: t('field.deduction_total'), value: batch.value.deduction_total || 0, color: 'var(--el-color-danger)', format: true },
    { label: t('field.net_total'), value: batch.value.net_total || 0, color: 'var(--el-color-primary)', format: true },
    { label: t('field.employer_cost_total'), value: batch.value.employer_cost_total || 0, color: 'var(--el-color-warning)', format: true },
  ]
})

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px">
        <h3>{{ t('payroll.jp.batch_detail') }} — {{ batch.sheet_id || batch.batch_id }}</h3>
        <el-tag :type="statusColors[batch.status] || ''" size="small">{{ batch.status }}</el-tag>
      </div>
      <div style="display:flex;gap:8px">
        <el-button v-if="canCalculate" type="primary" :loading="calcLoading" @click="calculate">
          {{ t('payroll.jp.calculate') }}
        </el-button>
        <el-button v-if="canConfirm" type="success" :loading="confirmLoading" @click="confirmSheet">
          {{ t('payroll.jp.confirm_sheet') }}
        </el-button>
        <el-button v-if="canDelete" type="danger" plain :loading="deleteLoading" @click="deleteSheet">
          {{ t('action.delete') }}
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
        <div class="step-indicator">
          <span class="step-number">{{ idx + 1 }}</span>
        </div>
        <div class="step-label">{{ t('payroll.jp.status_' + step) }}</div>
        <div v-if="idx < statusWorkflow.length - 1" class="step-connector" />
      </div>
    </div>

    <!-- Summary Cards -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="4" v-for="card in summaryCards" :key="card.label">
        <div class="summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value" :style="{ color: card.color }">
            <template v-if="card.format">¥{{ Number(card.value).toLocaleString() }}</template>
            <template v-else>{{ card.value }}</template>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Sheet Info -->
    <el-descriptions :column="4" border size="small" style="margin-bottom:20px">
      <el-descriptions-item :label="t('field.payroll_month')">{{ batch.payroll_month }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ entityLabel }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.sheet_id')">{{ batch.sheet_id || batch.batch_id }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.created_by')">{{ batch.created_by || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.notes')" :span="4">{{ batch.notes || '-' }}</el-descriptions-item>
    </el-descriptions>

    <!-- Calculation Summary (shown after calculate) -->
    <div v-if="calcSummary || calcWarnings.length" class="calc-summary-section">
      <h4>{{ t('payroll.jp.calculation_summary') }}</h4>

      <div v-if="calcWarnings.length" class="calc-warnings">
        <el-alert
          v-for="(warn, i) in calcWarnings"
          :key="i"
          :title="warn"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom:6px"
        />
      </div>

      <el-descriptions v-if="calcSummary" :column="3" border size="small">
        <el-descriptions-item :label="t('payroll.jp.total_employees_processed')">
          {{ calcSummary.total_processed || calcSummary.employee_count }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('payroll.jp.errors_count')">
          <span v-if="(calcSummary.errors || 0) > 0" style="color:var(--el-color-danger)">
            {{ calcSummary.errors }}
          </span>
          <span v-else>0</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('payroll.jp.warnings_count')">
          <span v-if="(calcSummary.warnings || 0) > 0" style="color:var(--el-color-warning)">
            {{ calcSummary.warnings }}
          </span>
          <span v-else>0</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- Records Table -->
    <div style="margin-top:20px">
      <div class="table-header">
        <h4>{{ t('payroll.jp.sheet_records') }}</h4>
        <div v-if="records.length > 0" class="helper-text">{{ records.length }} {{ t('action.records_total') }}</div>
      </div>

      <el-table :data="records" v-loading="loading" border stripe size="small" max-height="600">
        <el-table-column type="index" width="45" label="#" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="110" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" width="130" />
        <el-table-column prop="base_pay_calculated" :label="t('field.base_pay')" width="100" align="right">
          <template #default="{row}">{{ row.base_pay_calculated ? Number(row.base_pay_calculated).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="gross_pay" :label="t('field.gross_pay')" width="110" align="right">
          <template #default="{row}">{{ row.gross_pay ? Number(row.gross_pay).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.health_insurance')" width="90" align="right">
          <template #default="{row}">{{ row.health_insurance_employee ? Number(row.health_insurance_employee).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.pension')" width="90" align="right">
          <template #default="{row}">{{ row.pension_employee ? Number(row.pension_employee).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.employment_insurance')" width="90" align="right">
          <template #default="{row}">{{ row.employment_insurance_employee ? Number(row.employment_insurance_employee).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.care_insurance')" width="90" align="right">
          <template #default="{row}">{{ row.care_insurance_employee ? Number(row.care_insurance_employee).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="income_tax" :label="t('field.income_tax')" width="90" align="right">
          <template #default="{row}">{{ row.income_tax ? Number(row.income_tax).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="monthly_resident_tax" :label="t('field.monthly_resident_tax')" width="90" align="right">
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
        <el-table-column prop="employer_cost_total" :label="t('field.employer_cost_total')" width="110" align="right">
          <template #default="{row}">
            <span style="color:var(--el-color-warning)">{{ row.employer_cost_total ? Number(row.employer_cost_total).toLocaleString() : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('action.actions')" width="80" fixed="right">
          <template #default="{row}">
            <el-button
              v-if="canEditRecords"
              size="small"
              text
              @click="toggleEditRecord(row.record_id || row.id)"
            >
              {{ isEditingRecord(row.record_id || row.id) ? t('action.cancel') : t('action.edit') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Inline Edit Section for Draft Records -->
      <div v-if="canEditRecords && records.length > 0" style="margin-top:16px">
        <div
          v-for="record in records.filter((r:any) => isEditingRecord(r.record_id || r.id))"
          :key="record.record_id || record.id"
          class="edit-section"
        >
          <div class="edit-section-header">
            <strong>{{ record.employee_name }} ({{ record.employee_number }})</strong>
          </div>
          <el-row :gutter="12">
            <el-col :span="6">
              <el-form-item :label="t('field.actual_work_days')">
                <el-input-number v-model="record.actual_work_days" :min="0" :max="31" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.actual_work_hours')">
                <el-input-number v-model="record.actual_work_hours" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.overtime_hours')">
                <el-input-number v-model="record.overtime_hours" :min="0" :precision="1" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.commute_allowance')">
                <el-input-number v-model="record.commute_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.housing_allowance')">
                <el-input-number v-model="record.housing_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.family_allowance')">
                <el-input-number v-model="record.family_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.position_allowance')">
                <el-input-number v-model="record.position_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.fixed_allowance')">
                <el-input-number v-model="record.fixed_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.transport_allowance')">
                <el-input-number v-model="record.transport_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.phone_allowance')">
                <el-input-number v-model="record.phone_allowance" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.project_bonus')">
                <el-input-number v-model="record.project_bonus" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('field.performance_bonus')">
                <el-input-number v-model="record.performance_bonus" :min="0" :precision="0" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <div style="text-align:right;margin-top:8px">
            <el-button size="small" @click="toggleEditRecord(record.record_id || record.id)">{{ t('action.cancel') }}</el-button>
            <el-button size="small" type="primary" :loading="savingRecords" @click="saveRecord(record)">{{ t('action.save') }}</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !batch.sheet_id && !batch.batch_id" class="empty-state">
      <el-empty :description="t('payroll.jp.batch_not_found')" />
    </div>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }

/* Workflow */
.workflow-bar { display: flex; align-items: flex-start; margin-bottom: 20px; gap: 0; }
.workflow-step { display: flex; align-items: center; position: relative; }
.step-indicator { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 600; border: 2px solid #d9d9d9; color: #999; background: #fafafa; }
.step-active .step-indicator { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.step-current .step-indicator { background: var(--el-color-primary); color: #fff; border-color: var(--el-color-primary); }
.step-label { margin-left: 6px; font-size: 0.85rem; color: #999; white-space: nowrap; }
.step-active .step-label { color: var(--el-color-primary); }
.step-connector { width: 40px; height: 2px; background: #d9d9d9; margin: 0 8px; align-self: center; margin-top: -16px; }
.step-active .step-connector { background: var(--el-color-primary); }

/* Summary Cards */
.summary-row { margin-bottom: 20px; }
.summary-card { background: var(--el-bg-color-page); border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 16px; text-align: center; }
.summary-label { font-size: 0.78rem; color: var(--el-text-color-secondary); margin-bottom: 6px; }
.summary-value { font-size: 1.3rem; font-weight: 700; }

/* Calculation Summary */
.calc-summary-section { margin-bottom: 20px; padding: 16px; background: var(--el-bg-color-page); border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.calc-summary-section h4 { margin: 0 0 12px 0; font-size: 1rem; }
.calc-warnings { margin-bottom: 12px; }

/* Table */
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.table-header h4 { margin: 0; font-size: 1rem; }

/* Edit Section */
.edit-section { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 16px; margin-bottom: 12px; background: var(--el-color-primary-light-9); }
.edit-section-header { margin-bottom: 12px; font-size: 0.95rem; }

.helper-text { color: var(--el-text-color-secondary); font-size: 0.85rem; }
.empty-state { margin-top: 40px; }
</style>
