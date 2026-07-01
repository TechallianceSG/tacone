<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import client, { payrollSgApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ── State ──
const loading = ref(false)
const releases = ref<any[]>([])
const payslipMap = reactive<Record<string, any[]>>({})
const loadingPayslips = reactive<Record<string, boolean>>({})

// Confirm dialog
const confirmDialogVisible = ref(false)
const confirmActionKey = ref('')
const confirmTargetReleaseId = ref('')
const confirmLoading = ref(false)

// ── Computed ──
const statusColors: Record<string, string> = {
  pending_release: 'info',
  payslips_generated: 'warning',
  hr_confirmed: 'success',
  email_draft_prepared: 'warning',
  sent: 'primary',
  paid: 'info',
}

const statusLabels = computed<Record<string, string>>(() => ({
  pending_release: t('payroll.sg.release_status_pending'),
  payslips_generated: t('payroll.sg.release_status_generated'),
  hr_confirmed: t('payroll.sg.release_status_hr_confirmed'),
  email_draft_prepared: t('payroll.sg.release_status_email_draft'),
  sent: t('payroll.sg.release_status_sent'),
  paid: t('payroll.sg.release_status_paid'),
}))

// ── Data Loading ──
async function load() {
  loading.value = true
  try {
    const sheetId = route.query.sheet_id as string | undefined
    const params: Record<string, any> = {}
    if (sheetId) params.sheet_id = sheetId
    const res = await client.get('/api/payroll/sg/releases', { params })
    releases.value = res.data.data?.items || res.data.data || []
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadPayslipsForRelease(releaseId: string) {
  if (payslipMap[releaseId]?.length) return
  loadingPayslips[releaseId] = true
  try {
    const res = await client.get(`/api/payroll/sg/releases/${releaseId}/payslips`)
    payslipMap[releaseId] = res.data.data?.items || res.data.data || []
  } catch (e: any) {
    ElMessage.error(e.message)
    payslipMap[releaseId] = []
  } finally {
    loadingPayslips[releaseId] = false
  }
}

// ── Release Actions ──
function performReleaseAction(action: string, releaseId: string) {
  confirmActionKey.value = action
  confirmTargetReleaseId.value = releaseId
  confirmDialogVisible.value = true
}

const confirmTitle = computed(() => {
  const map: Record<string, string> = {
    generate_payslips: t('payroll.sg.generate_payslips_title'),
    hr_confirm_release: t('payroll.sg.hr_confirm_release_title'),
    regenerate_payslips: t('payroll.sg.regenerate_payslips_title'),
    prepare_emails: t('payroll.sg.prepare_emails_title'),
    send_emails: t('payroll.sg.send_emails_title'),
    mark_paid: t('payroll.sg.mark_paid_title'),
  }
  return map[confirmActionKey.value] || t('confirm.title')
})

const confirmMessage = computed(() => {
  const map: Record<string, string> = {
    generate_payslips: t('payroll.sg.generate_payslips_msg'),
    hr_confirm_release: t('payroll.sg.hr_confirm_release_msg'),
    regenerate_payslips: t('payroll.sg.regenerate_payslips_msg'),
    prepare_emails: t('payroll.sg.prepare_emails_msg'),
    send_emails: t('payroll.sg.send_emails_msg'),
    mark_paid: t('payroll.sg.mark_paid_msg'),
  }
  return map[confirmActionKey.value] || ''
})

async function confirmReleaseAction() {
  confirmLoading.value = true
  try {
    const releaseId = confirmTargetReleaseId.value
    switch (confirmActionKey.value) {
      case 'generate_payslips':
        await client.post(`/api/payroll/sg/releases/${releaseId}/generate-payslips`, {})
        ElMessage.success(t('payroll.sg.payslips_generated'))
        break
      case 'hr_confirm_release':
        await client.post(`/api/payroll/sg/releases/${releaseId}/hr-confirm`, {})
        ElMessage.success(t('payroll.sg.release_hr_confirmed'))
        break
      case 'regenerate_payslips':
        await client.post(`/api/payroll/sg/releases/${releaseId}/regenerate-payslips`, {})
        ElMessage.success(t('payroll.sg.payslips_regenerated'))
        break
      case 'prepare_emails':
        await client.post(`/api/payroll/sg/releases/${releaseId}/prepare-emails`, {})
        ElMessage.success(t('payroll.sg.emails_prepared'))
        break
      case 'send_emails':
        await payrollSgApi.batchEmailPayslips({ release_id: releaseId })
        ElMessage.success(t('payroll.sg.emails_sent'))
        break
      case 'mark_paid':
        await client.post(`/api/payroll/sg/releases/${releaseId}/mark-paid`, {})
        ElMessage.success(t('payroll.sg.release_marked_paid'))
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

// ── Individual Payslip Actions ──
async function sendSinglePayslip(payslipId: string, releaseId: string) {
  try {
    await payrollSgApi.emailPayslip(payslipId)
    ElMessage.success(t('payroll.sg.email_sent'))
    loadPayslipsForRelease(releaseId)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// ── Expand Handler ──
function onExpandChange(row: any, expandedRows: any[]) {
  if (expandedRows.some((r: any) => r.release_id === row.release_id)) {
    loadPayslipsForRelease(row.release_id)
  }
}

function getActionButtons(release: any): { action: string; label: string; type: string }[] {
  switch (release.status) {
    case 'pending_release':
      return [{ action: 'generate_payslips', label: t('payroll.sg.action_generate_payslips'), type: 'primary' }]
    case 'payslips_generated':
      return [
        { action: 'hr_confirm_release', label: t('payroll.sg.action_hr_confirm'), type: 'success' },
        { action: 'regenerate_payslips', label: t('payroll.sg.action_regenerate'), type: 'warning' },
      ]
    case 'hr_confirmed':
      return [{ action: 'prepare_emails', label: t('payroll.sg.action_prepare_emails'), type: 'primary' }]
    case 'email_draft_prepared':
      return [{ action: 'send_emails', label: t('payroll.sg.action_send_emails'), type: 'primary' }]
    case 'sent':
      return [{ action: 'mark_paid', label: t('payroll.sg.action_mark_paid'), type: 'success' }]
    case 'paid':
      return []
    default:
      return []
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- ── Page Header ── -->
    <div class="page-header">
      <h3>{{ t('payroll.sg.payslips') }}</h3>
      <el-button size="default" @click="load" :loading="loading" :icon="null">
        {{ t('action.refresh') }}
      </el-button>
    </div>

    <!-- ── Release Batches Table ── -->
    <el-table
      :data="releases"
      v-loading="loading"
      border
      stripe
      size="small"
      row-key="release_id"
      @expand-change="onExpandChange"
      style="width: 100%"
    >
      <!-- Expand row: Payslips per release -->
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <div class="payslip-expand-container">
            <div v-if="loadingPayslips[row.release_id]" class="expand-loading">
              <el-icon class="is-loading"><svg viewBox="0 0 1024 1024"><path d="M988 548c-19.9 0-36-16.1-36-36 0-59.4-11.6-117-34.6-171.3a440.45 440.45 0 00-94.3-139.9 437.71 437.71 0 00-139.9-94.3C629 83.6 571.4 72 512 72c-19.9 0-36-16.1-36-36s16.1-36 36-36c69.1 0 136.2 13.5 199.3 40.3C772.3 66 827 103 874 150c47 47 83.9 101.8 109.7 162.7 26.7 63.1 40.2 130.2 40.2 199.3.1 19.9-16 36-35.9 36z"/></svg></el-icon>
              {{ t('payroll.sg.loading_payslips') }}
            </div>
            <el-table v-else :data="(payslipMap[row.release_id] || [])" border stripe size="small" style="width: 100%">
              <el-table-column prop="employee_number" :label="t('field.employee_number')" width="130" />
              <el-table-column prop="employee_name" :label="t('field.employee_name')" width="150" />
              <el-table-column prop="department_label" :label="t('field.department')" width="130" />
              <el-table-column prop="gross_pay" :label="t('payroll.sg.gross_pay')" width="120" align="right">
                <template #default="{ row: p }">{{ p.gross_pay != null ? Number(p.gross_pay).toLocaleString() : '-' }}</template>
              </el-table-column>
              <el-table-column prop="deduction_total" :label="t('payroll.sg.deduction_total')" width="120" align="right">
                <template #default="{ row: p }">{{ p.deduction_total != null ? Number(p.deduction_total).toLocaleString() : '-' }}</template>
              </el-table-column>
              <el-table-column prop="net_pay" :label="t('payroll.sg.net_pay')" width="120" align="right">
                <template #default="{ row: p }"><strong>{{ p.net_pay != null ? Number(p.net_pay).toLocaleString() : '-' }}</strong></template>
              </el-table-column>
              <el-table-column prop="status" :label="t('field.status')" width="100">
                <template #default="{ row: p }">
                  <el-tag :type="p.status === 'sent' ? 'success' : p.status === 'failed' ? 'danger' : 'info'" size="small">
                    {{ p.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="email_status" :label="t('payroll.sg.email_status')" width="110">
                <template #default="{ row: p }">
                  <el-tag :type="p.email_status === 'sent' ? 'success' : p.email_status === 'failed' ? 'danger' : 'info'" size="small">
                    {{ p.email_status || '-' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('action.actions')" width="100" fixed="right">
                <template #default="{ row: p }">
                  <el-button
                    size="small"
                    text
                    type="primary"
                    :disabled="p.email_status === 'sent'"
                    @click="sendSinglePayslip(p.payslip_id || p.record_id, row.release_id)"
                  >
                    {{ t('action.send_email') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="!(payslipMap[row.release_id]?.length)" class="expand-empty">
              {{ t('payroll.sg.no_payslips') }}
            </div>
            <div v-if="payslipMap[row.release_id]?.length" class="helper-text">
              {{ payslipMap[row.release_id].length }} {{ t('action.records_total') }}
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- Release columns -->
      <el-table-column prop="release_id" :label="t('payroll.sg.release_id')" width="180" show-overflow-tooltip />
      <el-table-column prop="source_sheet_id" :label="t('payroll.sg.source_sheet')" width="180" show-overflow-tooltip />
      <el-table-column prop="payroll_month" :label="t('field.payroll_month')" width="100" />
      <el-table-column prop="status" :label="t('field.status')" width="150">
        <template #default="{ row }">
          <el-tag :type="statusColors[row.status] || 'info'" size="small" effect="dark">
            {{ statusLabels[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="employee_count" :label="t('payroll.sg.employee_count')" width="100" align="center" />
      <el-table-column prop="email_sent_count" :label="t('payroll.sg.email_sent')" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.email_sent_count != null">{{ row.email_sent_count }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="email_failed_count" :label="t('payroll.sg.email_failed')" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.email_failed_count != null" :class="{ 'text-danger': row.email_failed_count > 0 }">
            {{ row.email_failed_count }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="gross_total" :label="t('payroll.sg.gross_total')" width="130" align="right">
        <template #default="{ row }">{{ row.gross_total != null ? Number(row.gross_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="net_total" :label="t('payroll.sg.net_total')" width="130" align="right">
        <template #default="{ row }">{{ row.net_total != null ? Number(row.net_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="200" fixed="right">
        <template #default="{ row }">
          <template v-for="btn in getActionButtons(row)" :key="btn.action">
            <el-button
              size="small"
              :type="btn.type as any"
              @click="performReleaseAction(btn.action, row.release_id)"
              style="margin-left: 4px"
            >
              {{ btn.label }}
            </el-button>
          </template>
          <span v-if="getActionButtons(row).length === 0" class="completed-label">
            {{ t('payroll.sg.completed') }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <div class="helper-text">{{ releases.length }} {{ t('payroll.sg.releases_total') }}</div>

    <!-- ── Confirm Action Dialog ── -->
    <el-dialog v-model="confirmDialogVisible" :title="confirmTitle" width="420px" destroy-on-close>
      <p>{{ confirmMessage }}</p>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="confirmLoading" @click="confirmReleaseAction">{{ t('action.confirm') }}</el-button>
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
}

.page-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

/* ── Expand area ── */
.payslip-expand-container {
  padding: 12px 16px 12px 40px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
}

.expand-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
  padding: 16px;
}

.expand-loading .el-icon {
  font-size: 1rem;
}

.expand-empty {
  padding: 16px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

.helper-text {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

.text-danger {
  color: var(--el-color-danger);
  font-weight: 600;
}

.completed-label {
  color: var(--el-text-color-secondary);
  font-size: 0.82rem;
  font-style: italic;
  padding: 0 8px;
}
</style>
