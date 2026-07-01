<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import client, { payrollSgApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ── State ──
const loading = ref(false)
const saving = ref(false)
const sheet = ref<any>({})
const records = ref<any[]>([])
const reportView = ref(false)

// Batch dialogs
const batchDaysDialog = ref(false)
const batchDaysValue = ref<number | null>(null)
const batchHoursDialog = ref(false)
const batchHoursValue = ref<number | null>(null)

// Confirm dialog
const confirmDialogVisible = ref(false)
const confirmActionKey = ref('')
const confirmLoading = ref(false)

// ── Computed ──
const statusSteps = ['draft', 'hr_confirmed', 'calculated', 'hr_reviewed', 'manager_review', 'finalized']

const stepLabels = computed(() => [
  t('payroll.sg.step_draft'),
  t('payroll.sg.step_hr_confirmed'),
  t('payroll.sg.step_calculated'),
  t('payroll.sg.step_hr_reviewed'),
  t('payroll.sg.step_manager_review'),
  t('payroll.sg.step_finalized'),
])

const currentStep = computed(() => {
  const idx = statusSteps.indexOf(sheet.value.status)
  return idx >= 0 ? idx : 0
})

const isEditable = computed(() => ['draft', 'hr_confirmed'].includes(sheet.value.status))
const isCalculated = computed(() => {
  const idx = statusSteps.indexOf(sheet.value.status)
  return idx >= 2
})
const isFinalized = computed(() => sheet.value.status === 'finalized')

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    draft: 'info',
    hr_confirmed: 'warning',
    calculated: 'primary',
    hr_reviewed: 'success',
    manager_review: 'warning',
    finalized: 'success',
  }
  return map[sheet.value.status] || 'info'
})

const summaryCards = computed(() => [
  { label: t('payroll.sg.employee_count'), value: sheet.value.employee_count ?? 0 },
  { label: t('payroll.sg.gross_total'), value: sheet.value.gross_total != null ? Number(sheet.value.gross_total).toLocaleString() : '-' },
  { label: t('payroll.sg.deduction_total'), value: sheet.value.deduction_total != null ? Number(sheet.value.deduction_total).toLocaleString() : '-' },
  { label: t('payroll.sg.net_total'), value: sheet.value.net_total != null ? Number(sheet.value.net_total).toLocaleString() : '-' },
])

// ── Data Loading ──
async function load() {
  loading.value = true
  try {
    const res = await payrollSgApi.getSheet(route.params.id as string)
    const data = res.data.data || res.data || {}
    sheet.value = data
    records.value = data.records || []
    // Ensure performance_bonus defaults to 0 for draft records
    if (isEditable.value) {
      records.value.forEach((r: any) => {
        if (r.performance_bonus == null) r.performance_bonus = 0
      })
    }
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// ── Save Records (inline edit) ──
async function saveRecords() {
  saving.value = true
  try {
    await client.post(`/api/payroll/sg/sheets/${route.params.id}/records`, { records: records.value })
    ElMessage.success(t('common.saved'))
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// ── Batch Actions ──
async function batchSetDays() {
  if (batchDaysValue.value == null) return
  try {
    await client.post(`/api/payroll/sg/sheets/${route.params.id}/batch-days`, { value: batchDaysValue.value })
    batchDaysDialog.value = false
    batchDaysValue.value = null
    ElMessage.success(t('payroll.sg.batch_days_set'))
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function batchSetHours() {
  if (batchHoursValue.value == null) return
  try {
    await client.post(`/api/payroll/sg/sheets/${route.params.id}/batch-hours`, { value: batchHoursValue.value })
    batchHoursDialog.value = false
    batchHoursValue.value = null
    ElMessage.success(t('payroll.sg.batch_hours_set'))
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// ── State Transition Actions ──
function performAction(action: string) {
  confirmActionKey.value = action
  confirmDialogVisible.value = true
}

const confirmTitle = computed(() => {
  const map: Record<string, string> = {
    confirm_basic: t('payroll.sg.confirm_basic_title'),
    return_draft: t('payroll.sg.return_draft_title'),
    calculate: t('payroll.sg.calculate_title'),
    hr_approve: t('payroll.sg.hr_approve_title'),
    hr_reject: t('payroll.sg.hr_reject_title'),
    send_manager: t('payroll.sg.send_manager_title'),
    manager_approve: t('payroll.sg.manager_approve_title'),
    manager_reject: t('payroll.sg.manager_reject_title'),
    view_release: '',
  }
  return map[confirmActionKey.value] || t('confirm.title')
})

const confirmMessage = computed(() => {
  const map: Record<string, string> = {
    confirm_basic: t('payroll.sg.confirm_basic_msg'),
    return_draft: t('payroll.sg.return_draft_msg'),
    calculate: t('payroll.sg.calculate_msg'),
    hr_approve: t('payroll.sg.hr_approve_msg'),
    hr_reject: t('payroll.sg.hr_reject_msg'),
    send_manager: t('payroll.sg.send_manager_msg'),
    manager_approve: t('payroll.sg.manager_approve_msg'),
    manager_reject: t('payroll.sg.manager_reject_msg'),
  }
  return map[confirmActionKey.value] || ''
})

async function confirmAction() {
  confirmLoading.value = true
  try {
    const sheetId = route.params.id as string
    switch (confirmActionKey.value) {
      case 'confirm_basic':
        await payrollSgApi.confirmSheet(sheetId)
        ElMessage.success(t('payroll.sg.confirmed'))
        break
      case 'return_draft':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/return-draft`, {})
        ElMessage.success(t('payroll.sg.returned_to_draft'))
        break
      case 'calculate':
        await payrollSgApi.calculateBatch(sheetId, {})
        ElMessage.success(t('payroll.sg.calculated'))
        break
      case 'hr_approve':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/hr-approve`, {})
        ElMessage.success(t('payroll.sg.hr_approved'))
        break
      case 'hr_reject':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/hr-reject`, {})
        ElMessage.success(t('payroll.sg.hr_rejected'))
        break
      case 'send_manager':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/send-manager`, {})
        ElMessage.success(t('payroll.sg.sent_to_manager'))
        break
      case 'manager_approve':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/manager-approve`, {})
        ElMessage.success(t('payroll.sg.manager_approved'))
        break
      case 'manager_reject':
        await client.post(`/api/payroll/sg/sheets/${sheetId}/manager-reject`, {})
        ElMessage.success(t('payroll.sg.manager_rejected'))
        break
      case 'finalize':
        await payrollSgApi.releaseSheet(sheetId)
        ElMessage.success(t('payroll.sg.finalized'))
        break
    }
    confirmDialogVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    confirmLoading.value = false
  }
}

function goToRelease() {
  router.push(`/payroll/sg/payslips?sheet_id=${route.params.id}`)
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- ── Page Header ── -->
    <div class="page-header">
      <div class="header-left">
        <h3>{{ t('payroll.sg.batch_detail') }} — {{ sheet.sheet_id }}</h3>
        <el-tag :type="statusTagType" size="large" effect="dark" class="status-tag">{{ sheet.status }}</el-tag>
      </div>
      <div class="header-actions">
        <!-- Draft actions -->
        <template v-if="sheet.status === 'draft'">
          <el-button type="primary" size="default" @click="performAction('confirm_basic')">
            {{ t('payroll.sg.confirm_basic_info') }}
          </el-button>
        </template>

        <!-- HR Confirmed actions -->
        <template v-if="sheet.status === 'hr_confirmed'">
          <el-button type="primary" size="default" @click="performAction('calculate')">
            {{ t('payroll.sg.calculate_payroll') }}
          </el-button>
          <el-button size="default" @click="performAction('return_draft')">
            {{ t('payroll.sg.return_to_draft') }}
          </el-button>
        </template>

        <!-- Calculated actions -->
        <template v-if="sheet.status === 'calculated'">
          <el-button type="success" size="default" @click="performAction('hr_approve')">
            {{ t('payroll.sg.hr_approve') }}
          </el-button>
          <el-button size="default" @click="performAction('hr_reject')">
            {{ t('payroll.sg.return') }}
          </el-button>
        </template>

        <!-- HR Reviewed actions -->
        <template v-if="sheet.status === 'hr_reviewed'">
          <el-button type="primary" size="default" @click="performAction('send_manager')">
            {{ t('payroll.sg.send_to_manager') }}
          </el-button>
        </template>

        <!-- Manager Review actions -->
        <template v-if="sheet.status === 'manager_review'">
          <el-button type="success" size="default" @click="performAction('manager_approve')">
            {{ t('payroll.sg.manager_approve') }}
          </el-button>
          <el-button type="danger" size="default" @click="performAction('manager_reject')">
            {{ t('payroll.sg.manager_reject') }}
          </el-button>
        </template>

        <!-- Finalized actions -->
        <template v-if="sheet.status === 'finalized'">
          <el-button type="primary" size="default" @click="goToRelease">
            {{ t('payroll.sg.view_release') }}
          </el-button>
        </template>
      </div>
    </div>

    <!-- ── Sheet Info Bar ── -->
    <el-descriptions :column="4" border size="small" style="margin-bottom: 20px">
      <el-descriptions-item :label="t('field.payroll_month')">
        {{ sheet.payroll_month }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">
        {{ sheet.entity_label || sheet.entity_id }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('field.employee_count')">
        {{ sheet.employee_count ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('field.created_by')">
        {{ sheet.created_by || '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('common.created_at')">
        {{ sheet.created_at ? new Date(sheet.created_at).toLocaleString() : '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('common.updated_at')">
        {{ sheet.updated_at ? new Date(sheet.updated_at).toLocaleString() : '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('field.notes')" :span="2">
        {{ sheet.notes || '-' }}
      </el-descriptions-item>
    </el-descriptions>

    <!-- ── Workflow Steps ── -->
    <el-steps :active="currentStep" finish-status="success" class="workflow-steps">
      <el-step v-for="(label, index) in stepLabels" :key="index" :title="label" />
    </el-steps>

    <!-- ── Summary Statistics Cards ── -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="6" v-for="card in summaryCards" :key="card.label">
        <el-card shadow="never" class="summary-card">
          <el-statistic :title="card.label" :value="card.value" />
        </el-card>
      </el-col>
    </el-row>

    <!-- ── View Toggle ── -->
    <div class="view-toggle">
      <el-switch v-model="reportView" :active-text="t('payroll.sg.report_view')" :inactive-text="t('payroll.sg.detail_view')" />
    </div>

    <!-- ── Records Table (Detail View) ── -->
    <el-card v-if="!reportView" shadow="never" class="records-card">
      <!-- Batch Actions Bar (draft only) -->
      <div v-if="sheet.status === 'draft'" class="batch-actions-bar">
        <span class="batch-label">{{ t('payroll.sg.batch_actions') }}:</span>
        <el-button size="small" @click="batchDaysDialog = true">{{ t('payroll.sg.batch_set_days') }}</el-button>
        <el-button size="small" @click="batchHoursDialog = true">{{ t('payroll.sg.batch_set_hours') }}</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveRecords" class="save-records-btn">
          {{ t('common.save') }}
        </el-button>
      </div>
      <!-- Single Save button for hr_confirmed -->
      <div v-else-if="sheet.status === 'hr_confirmed'" class="batch-actions-bar">
        <el-button size="small" type="primary" :loading="saving" @click="saveRecords">
          {{ t('common.save') }}
        </el-button>
      </div>

      <el-table :data="records" v-loading="loading" max-height="620" border stripe size="small" style="width: 100%">
        <!-- Always-visible columns -->
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="130" fixed="left" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" width="160" fixed="left" />
        <el-table-column prop="department_label" :label="t('field.department')" width="140" />
        <el-table-column prop="salary_type" :label="t('field.payroll__salary_type')" width="100" />

        <!-- Editable columns (draft / hr_confirmed) -->
        <template v-if="isEditable">
          <el-table-column prop="actual_work_days" :label="t('payroll.sg.actual_work_days')" width="120">
            <template #default="{ row }">
              <el-input v-model="row.actual_work_days" size="small" type="number" step="0.5" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="actual_work_hours" :label="t('payroll.sg.actual_work_hours')" width="120">
            <template #default="{ row }">
              <el-input v-model="row.actual_work_hours" size="small" type="number" step="0.5" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="paid_leave_days" :label="t('payroll.sg.paid_leave_days')" width="120">
            <template #default="{ row }">
              <el-input v-model="row.paid_leave_days" size="small" type="number" step="0.5" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="overtime_hours" :label="t('payroll.sg.overtime_hours')" width="110">
            <template #default="{ row }">
              <el-input v-model="row.overtime_hours" size="small" type="number" step="0.5" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="fixed_allowance" :label="t('payroll.sg.fixed_allowance')" width="120">
            <template #default="{ row }">
              <el-input v-model="row.fixed_allowance" size="small" type="number" step="0.01" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="performance_bonus" :label="t('payroll.sg.performance_bonus')" width="130">
            <template #default="{ row }">
              <el-input v-model="row.performance_bonus" size="small" type="number" step="0.01" min="0" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column prop="performance_reference" :label="t('payroll.sg.performance_reference')" width="160">
            <template #default="{ row }">
              <span class="readonly-hint">{{ row.performance_reference || '-' }}</span>
            </template>
          </el-table-column>
        </template>

        <!-- Calculated+ columns (readonly) -->
        <template v-if="isCalculated">
          <el-table-column prop="base_pay_calculated" :label="t('payroll.sg.base_pay')" width="130" align="right">
            <template #default="{ row }">{{ row.base_pay_calculated != null ? Number(row.base_pay_calculated).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="gross_pay" :label="t('payroll.sg.gross_pay')" width="130" align="right">
            <template #default="{ row }">{{ row.gross_pay != null ? Number(row.gross_pay).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="cpf_employee" :label="t('payroll.sg.cpf_employee')" width="120" align="right">
            <template #default="{ row }">{{ row.cpf_employee != null ? Number(row.cpf_employee).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="cpf_employer" :label="t('payroll.sg.cpf_employer')" width="120" align="right">
            <template #default="{ row }">{{ row.cpf_employer != null ? Number(row.cpf_employer).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="deduction_total" :label="t('payroll.sg.deduction_total')" width="120" align="right">
            <template #default="{ row }">{{ row.deduction_total != null ? Number(row.deduction_total).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="net_pay" :label="t('payroll.sg.net_pay')" width="130" align="right">
            <template #default="{ row }">
              <strong>{{ row.net_pay != null ? Number(row.net_pay).toLocaleString() : '-' }}</strong>
            </template>
          </el-table-column>
          <el-table-column prop="employer_cost_total" :label="t('payroll.sg.employer_cost')" width="130" align="right">
            <template #default="{ row }">{{ row.employer_cost_total != null ? Number(row.employer_cost_total).toLocaleString() : '-' }}</template>
          </el-table-column>
        </template>
      </el-table>
      <div class="helper-text">{{ records.length }} {{ t('action.records_total') }}</div>
    </el-card>

    <!-- ── Report View ── -->
    <el-card v-else shadow="never" class="records-card">
      <div class="report-header">
        <h3>{{ t('payroll.sg.payroll_report') }}</h3>
        <p>{{ sheet.payroll_month }} — {{ sheet.entity_label || sheet.entity_id }}</p>
      </div>
      <table class="report-table">
        <thead>
          <tr>
            <th>{{ t('field.employee_number') }}</th>
            <th>{{ t('field.employee_name') }}</th>
            <th>{{ t('field.department') }}</th>
            <th>{{ t('payroll.sg.gross_pay') }}</th>
            <th>{{ t('payroll.sg.deduction_total') }}</th>
            <th>{{ t('payroll.sg.net_pay') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.record_id">
            <td>{{ r.employee_number }}</td>
            <td>{{ r.employee_name }}</td>
            <td>{{ r.department_label }}</td>
            <td class="amount">{{ r.gross_pay != null ? Number(r.gross_pay).toLocaleString() : '-' }}</td>
            <td class="amount">{{ r.deduction_total != null ? Number(r.deduction_total).toLocaleString() : '-' }}</td>
            <td class="amount"><strong>{{ r.net_pay != null ? Number(r.net_pay).toLocaleString() : '-' }}</strong></td>
          </tr>
        </tbody>
        <tfoot v-if="records.length > 0">
          <tr>
            <th colspan="3">{{ t('payroll.sg.total') }}</th>
            <th class="amount">{{ sheet.gross_total != null ? Number(sheet.gross_total).toLocaleString() : '-' }}</th>
            <th class="amount">{{ sheet.deduction_total != null ? Number(sheet.deduction_total).toLocaleString() : '-' }}</th>
            <th class="amount">{{ sheet.net_total != null ? Number(sheet.net_total).toLocaleString() : '-' }}</th>
          </tr>
        </tfoot>
      </table>
      <div class="print-footer">
        <span>{{ t('payroll.sg.generated_at') }}: {{ new Date().toLocaleString() }}</span>
      </div>
    </el-card>

    <!-- ── Batch Set Days Dialog ── -->
    <el-dialog v-model="batchDaysDialog" :title="t('payroll.sg.batch_set_days')" width="380px" destroy-on-close>
      <el-form label-width="160px">
        <el-form-item :label="t('payroll.sg.actual_work_days')">
          <el-input-number v-model="batchDaysValue" :min="0" :step="0.5" :precision="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDaysDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" @click="batchSetDays">{{ t('action.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- ── Batch Set Hours Dialog ── -->
    <el-dialog v-model="batchHoursDialog" :title="t('payroll.sg.batch_set_hours')" width="380px" destroy-on-close>
      <el-form label-width="160px">
        <el-form-item :label="t('payroll.sg.actual_work_hours')">
          <el-input-number v-model="batchHoursValue" :min="0" :step="0.5" :precision="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchHoursDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" @click="batchSetHours">{{ t('action.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- ── Confirm Action Dialog ── -->
    <el-dialog v-model="confirmDialogVisible" :title="confirmTitle" width="420px" destroy-on-close>
      <p>{{ confirmMessage }}</p>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="confirmLoading" @click="confirmAction">{{ t('action.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container {
  padding: 24px;
  max-width: 1500px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h3 {
  margin: 0;
  font-size: 1.25rem;
  white-space: nowrap;
}

.status-tag {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.workflow-steps {
  margin-bottom: 24px;
  padding: 4px 0;
}

.summary-row {
  margin-bottom: 20px;
}

.summary-card {
  border: 1px solid var(--el-border-color-lighter);
}

.summary-card :deep(.el-statistic__title) {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
}

.summary-card :deep(.el-statistic__content) {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.view-toggle {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.records-card {
  margin-bottom: 20px;
}

.batch-actions-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.batch-label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-right: 4px;
}

.save-records-btn {
  margin-left: auto;
}

.readonly-hint {
  color: var(--el-text-color-secondary);
  font-style: italic;
  font-size: 0.82rem;
}

.helper-text {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

/* ── Report View ── */
.report-header {
  text-align: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--el-border-color);
}

.report-header h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}

.report-header p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.report-table th,
.report-table td {
  border: 1px solid var(--el-border-color);
  padding: 6px 10px;
  text-align: left;
}

.report-table th {
  background: var(--el-fill-color);
  font-weight: 600;
}

.report-table .amount {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.report-table tfoot th {
  background: var(--el-fill-color-lighter);
}

.print-footer {
  margin-top: 16px;
  text-align: right;
  font-size: 0.78rem;
  color: var(--el-text-color-secondary);
}

/* ── Responsive ── */
@media print {
  .page-header,
  .workflow-steps,
  .view-toggle,
  .batch-actions-bar,
  .header-actions {
    display: none !important;
  }
}
</style>
