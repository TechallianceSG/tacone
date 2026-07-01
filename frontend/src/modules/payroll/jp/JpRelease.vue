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
const sheet = ref<any>({})
const records = ref<any[]>([])
const selectedIds = ref<string[]>([])

// Email preview dialog
const emailDialog = ref(false)
const emailRecipients = ref<any[]>([])
const emailSending = ref(false)

// Payslip view dialog
const payslipHtmlDialog = ref(false)
const payslipHtmlContent = ref('')
const payslipEmployee = ref<any>(null)

// Individual sending state
const sendingIds = ref<Set<string>>(new Set())

// Entities for labels
const entities = ref<any[]>([])

// ── Computed ──
const sheetId = computed(() => route.params.id as string)

const summaryCards = computed(() => {
  const s = sheet.value
  return [
    { label: t('field.employee_count'), value: s.employee_count || records.value.length || 0, color: '', format: false },
    { label: t('field.gross_total'), value: s.gross_total || 0, color: '', format: true },
    { label: t('field.deduction_total'), value: s.deduction_total || 0, color: 'var(--el-color-danger)', format: true },
    { label: t('field.net_total'), value: s.net_total || 0, color: 'var(--el-color-primary)', format: true },
    { label: t('field.employer_cost_total'), value: s.employer_cost_total || 0, color: 'var(--el-color-warning)', format: true },
  ]
})

const allSelected = computed({
  get: () => records.value.length > 0 && selectedIds.value.length === records.value.length,
  set: (val: boolean) => {
    selectedIds.value = val ? records.value.map(r => r.record_id || r.id) : []
  }
})

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const [sheetRes, entitiesRes] = await Promise.all([
      payrollJpApi.releasePage(sheetId.value).catch(() => payrollJpApi.getSheet(sheetId.value)),
      fetch('/api/masterdata/entities').then(r => r.json()).catch(() => ({ data: [] })),
    ])
    entities.value = entitiesRes.data || []
    const data = sheetRes.data.data || sheetRes.data || {}
    sheet.value = data.sheet || data
    records.value = data.records || data.items || data.records_data || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function entityLabel(entityId: string) {
  const found = entities.value.find((e: any) => e.entity_id === entityId)
  if (!found) return entityId
  return `${found.entity_code || found.entity_id} - ${found.entity_name || ''} (${found.country || ''})`
}

// ── Individual Email ──
async function sendSingleEmail(record: any) {
  const id = record.record_id || record.id
  sendingIds.value.add(id)
  try {
    await payrollJpApi.sendPayslipEmail(id)
    ElMessage.success(t('action.email_sent'))
  } catch (e: any) { ElMessage.error(e.message) }
  finally { sendingIds.value.delete(id) }
}

// ── Bulk Email ──
function openSendSelected() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning(t('payroll.jp.no_records'))
    return
  }
  emailRecipients.value = records.value.filter(r => selectedIds.value.includes(r.record_id || r.id))
  emailDialog.value = true
}

function openSendAll() {
  emailRecipients.value = [...records.value]
  emailDialog.value = true
}

async function confirmSendEmails() {
  emailSending.value = true
  try {
    if (emailRecipients.value.length === records.value.length) {
      await payrollJpApi.sendAllPayslipEmails(sheetId.value)
    } else {
      // Send individually for selected
      for (const r of emailRecipients.value) {
        await payrollJpApi.sendPayslipEmail(r.record_id || r.id)
      }
    }
    emailDialog.value = false
    ElMessage.success(t('action.email_sent'))
  } catch (e: any) { ElMessage.error(e.message) }
  finally { emailSending.value = false }
}

// ── Payslip View ──
async function viewPayslipHtml(record: any) {
  payslipEmployee.value = record
  try {
    const id = record.record_id || record.id
    const res = await payrollJpApi.viewPayslipHtml(id)
    payslipHtmlContent.value = typeof res.data === 'string' ? res.data : res.data?.html || JSON.stringify(res.data)
    payslipHtmlDialog.value = true
  } catch (e: any) {
    // Fallback: show a simple preview
    payslipHtmlContent.value = generateSimplePreview(record)
    payslipHtmlDialog.value = true
  }
}

function generateSimplePreview(record: any) {
  const r = record
  const items = {
    earnings: [
      { label: t('field.basic_salary'), amount: r.base_pay_calculated },
      { label: t('field.commute_allowance'), amount: r.commute_allowance },
      { label: t('field.housing_allowance'), amount: r.housing_allowance },
      { label: t('field.family_allowance'), amount: r.family_allowance },
      { label: t('field.position_allowance'), amount: r.position_allowance },
      { label: t('field.fixed_allowance'), amount: r.fixed_allowance },
      { label: t('field.transport_allowance'), amount: r.transport_allowance },
      { label: t('field.phone_allowance'), amount: r.phone_allowance },
      { label: t('field.performance_bonus'), amount: r.performance_bonus },
      { label: t('field.project_bonus'), amount: r.project_bonus },
    ].filter(i => i.amount && Number(i.amount) > 0),
    deductions: [
      { label: t('field.health_insurance'), amount: r.health_insurance_employee || r.health_insurance },
      { label: t('field.pension'), amount: r.pension_employee || r.pension },
      { label: t('field.care_insurance'), amount: r.care_insurance_employee || r.care_insurance },
      { label: t('field.employment_insurance'), amount: r.employment_insurance_employee || r.employment_insurance },
      { label: t('field.income_tax'), amount: r.income_tax },
      { label: t('field.monthly_resident_tax'), amount: r.monthly_resident_tax },
      { label: t('field.recurring_deductions'), amount: r.recurring_deductions },
    ].filter(i => i.amount && Number(i.amount) > 0),
  }
  const fmt = (v: any) => '¥' + Number(v || 0).toLocaleString()

  let html = `<div class="ps-container">
    <div class="ps-header">
      <h2>📄 ${t('payroll.jp.payslips')}</h2>
      <p class="ps-subtitle">${sheet.value.entity_id ? entityLabel(sheet.value.entity_id) : ''}</p>
    </div>
    <div class="ps-body">
      <div class="ps-info">
        <div><span class="ps-label">${t('field.payroll_month')}</span><span class="ps-value">${sheet.value.payroll_month || '-'}</span></div>
        <div><span class="ps-label">${t('field.employee_name')}</span><span class="ps-value">${r.employee_name}</span></div>
        <div><span class="ps-label">${t('field.employee_number')}</span><span class="ps-value">${r.employee_number}</span></div>
        <div><span class="ps-label">${t('field.department')}</span><span class="ps-value">${r.department_label || '-'}</span></div>
        <div><span class="ps-label">${t('field.salary_type_label')}</span><span class="ps-value">${r.salary_type || '-'}</span></div>
        <div><span class="ps-label">${t('field.payroll_currency')}</span><span class="ps-value">JPY</span></div>
      </div>`

  // Earnings
  html += `<h3>💰 ${t('payroll.jp.earnings')}</h3><table class="ps-table">`
  if (items.earnings.length) {
    items.earnings.forEach(i => {
      html += `<tr><td>${i.label}</td><td class="ps-right">${fmt(i.amount)}</td></tr>`
    })
  } else {
    html += `<tr><td class="ps-muted">—</td><td></td></tr>`
  }
  html += `<tr class="ps-total"><td>${t('field.gross_pay').toUpperCase()}</td><td class="ps-right">${fmt(r.gross_pay)}</td></tr></table>`

  // Deductions
  html += `<h3>📉 ${t('payroll.jp.deductions')}</h3><table class="ps-table">`
  if (items.deductions.length) {
    items.deductions.forEach(i => {
      html += `<tr><td>${i.label}</td><td class="ps-right">${fmt(i.amount)}</td></tr>`
    })
  } else {
    html += `<tr><td class="ps-muted">—</td><td></td></tr>`
  }
  html += `<tr class="ps-total"><td>${t('field.deduction_total').toUpperCase()}</td><td class="ps-right">${fmt(r.deduction_total)}</td></tr></table>`

  // Net Pay
  html += `<table class="ps-table" style="margin-top:14px">
    <tr class="ps-net"><td>💵 ${t('field.net_pay').toUpperCase()}</td><td class="ps-right">${fmt(r.net_pay)}</td></tr>
  </table>`

  // Employer Cost
  html += `<h3>🏢 ${t('field.employer_cost_total')}</h3><table class="ps-table">
    <tr class="ps-total"><td>${t('field.employer_cost_total')}</td><td class="ps-right" style="color:var(--el-color-warning)">${fmt(r.employer_cost_total)}</td></tr>
  </table>`

  // Footer
  html += `<div class="ps-footer">
    <p>Generated: ${new Date().toISOString().replace('T',' ').substring(0,19)} · Computer-generated payslip · For queries contact HR</p>
  </div></div></div>`

  return html
}

async function downloadPdf(record: any) {
  try {
    const id = record.record_id || record.id
    const res = await payrollJpApi.downloadPayslipPdf(id)
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  } catch (e: any) { ElMessage.error(e.message) }
}

function printPayslip(record: any) {
  payslipEmployee.value = record
  payslipHtmlContent.value = generateSimplePreview(record)
  payslipHtmlDialog.value = true
  setTimeout(() => {
    try { globalThis.print() } catch (_) { /* print may be blocked */ }
  }, 500)
}

function doPrint() {
  try { globalThis.print() } catch (_) { /* print may be blocked */ }
}

// ── CSV Export ──
async function exportCsv() {
  try {
    const res = await payrollJpApi.exportCsv(sheetId.value)
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `payroll_jp_${sheetId.value}_${sheet.value.payroll_month || 'export'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <h3>{{ t('payroll.jp.release_title') }}</h3>
        <el-tag type="success" size="default">{{ t('payroll.jp.status_confirmed') }}</el-tag>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <el-button @click="exportCsv">{{ t('payroll.jp.csv_export') }}</el-button>
        <el-button type="warning" @click="openSendSelected" :disabled="selectedIds.length === 0">
          {{ t('payroll.jp.send_selected') }} ({{ selectedIds.length }})
        </el-button>
        <el-button type="primary" @click="openSendAll">
          {{ t('payroll.jp.send_all') }}
        </el-button>
      </div>
    </div>

    <!-- Sheet Info -->
    <el-descriptions :column="3" border size="small" style="margin-bottom:20px">
      <el-descriptions-item :label="t('field.sheet_id')">{{ sheet.sheet_id || sheet.batch_id || sheetId }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.payroll_month')">{{ sheet.payroll_month || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ entityLabel(sheet.entity_id) }}</el-descriptions-item>
    </el-descriptions>

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

    <!-- Employee Table -->
    <div class="table-header">
      <h4>{{ t('payroll.jp.release_summary') }}</h4>
      <div class="helper-text">{{ records.length }} {{ t('action.records_total') }}</div>
    </div>

    <el-table :data="records" v-loading="loading" border stripe size="small" max-height="520"
      @selection-change="(rows:any[]) => selectedIds = rows.map((r:any) => r.record_id || r.id)">
      <el-table-column type="selection" width="40" />
      <el-table-column type="index" width="40" label="#" />
      <el-table-column prop="employee_number" :label="t('field.employee_number')" width="110" />
      <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="140" show-overflow-tooltip />
      <el-table-column prop="salary_type" :label="t('field.salary_type_label')" width="100">
        <template #default="{row}">
          <el-tag size="small" type="info">{{ row.salary_type || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="gross_pay" :label="t('field.gross_pay')" width="120" align="right">
        <template #default="{row}">{{ row.gross_pay ? '¥' + Number(row.gross_pay).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="deduction_total" :label="t('field.deduction_total')" width="120" align="right">
        <template #default="{row}">{{ row.deduction_total ? '¥' + Number(row.deduction_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="net_pay" :label="t('field.net_pay')" width="120" align="right">
        <template #default="{row}">
          <strong style="color:var(--el-color-primary)">{{ row.net_pay ? '¥' + Number(row.net_pay).toLocaleString() : '-' }}</strong>
        </template>
      </el-table-column>
      <el-table-column :label="t('field.actions')" width="220" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="viewPayslipHtml(row)">
            {{ t('payroll.jp.view_payslip_html') }}
          </el-button>
          <el-button size="small" text @click="downloadPdf(row)">
            {{ t('payroll.jp.download_payslip_pdf') }}
          </el-button>
          <el-button size="small" text @click="printPayslip(row)">
            {{ t('payroll.jp.print') }}
          </el-button>
          <el-button
            size="small" text type="warning"
            :loading="sendingIds.has(row.record_id || row.id)"
            @click="sendSingleEmail(row)"
          >
            {{ t('payroll.jp.send_email') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Email Preview Dialog -->
    <el-dialog v-model="emailDialog" :title="t('payroll.jp.email_preview')" width="650px" top="3vh">
      <el-alert
        :title="t('payroll.jp.smtp_not_configured')"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom:12px"
      />
      <p class="helper-text" style="margin-bottom:12px">
        {{ t('payroll.jp.send_all') }}: <strong>{{ emailRecipients.length }}</strong> {{ t('field.employee_count').toLowerCase() }}
      </p>
      <el-table :data="emailRecipients" border stripe size="small" max-height="300">
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="110" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" />
        <el-table-column prop="email" :label="t('field.email')" min-width="200" show-overflow-tooltip />
        <el-table-column prop="net_pay" :label="t('field.net_pay')" width="120" align="right">
          <template #default="{row}">{{ row.net_pay ? '¥' + Number(row.net_pay).toLocaleString() : '-' }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="emailDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="emailSending" @click="confirmSendEmails">
          {{ t('payroll.jp.send_email') }} ({{ emailRecipients.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- Payslip HTML View Dialog -->
    <el-dialog v-model="payslipHtmlDialog" :title="t('payroll.jp.view_payslip_html')" width="850px" top="2vh" fullscreen>
      <div v-html="payslipHtmlContent" class="payslip-html-wrapper" />
      <template #footer>
        <el-button @click="payslipHtmlDialog = false">{{ t('action.close') }}</el-button>
        <el-button type="primary" @click="doPrint">{{ t('payroll.jp.print') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { max-width:1500px; margin:0 auto; padding:24px; font-size:15px; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.page-header h3 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }

.summary-row { margin-bottom:20px; display:flex; flex-wrap:wrap; gap:12px; }
.summary-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:18px; text-align:center; flex:1; min-width:140px; }
.summary-label { font-size:.78rem; color:#6b7280; margin-bottom:6px; text-transform:uppercase; letter-spacing:.03em; }
.summary-value { font-size:1.35rem; font-weight:700; color:#1d2a3a; }
.table-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.table-header h4 { margin:0; font-size:1rem; font-weight:700; color:#1d2a3a; }
.helper-text { color:#6b7280; font-size:.85rem; }
.payslip-html-wrapper { max-height:70vh; overflow-y:auto; }
.payslip-html-wrapper :deep(.ps-container) { max-width:780px; margin:0 auto; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','Noto Sans JP',Arial,sans-serif; font-size:14px; color:#1a1a2e; line-height:1.5; }
.payslip-html-wrapper :deep(.ps-header) { background:linear-gradient(135deg,#0f2b46,#1a4a7a); color:#fff; padding:24px 28px; border-radius:12px 12px 0 0; }
.payslip-html-wrapper :deep(.ps-header h2) { margin:0 0 4px; font-size:22px; font-weight:800; }
.payslip-html-wrapper :deep(.ps-subtitle) { opacity:.85; font-size:14px; margin:0; }
.payslip-html-wrapper :deep(.ps-body) { background:#fff; border:1px solid #e5e7eb; border-top:none; padding:24px 28px; border-radius:0 0 12px 12px; }
.payslip-html-wrapper :deep(.ps-body h3) { font-size:15px; color:#1d2a3a; border-bottom:2px solid #1B6CB2; padding-bottom:6px; margin:18px 0 10px; }
.payslip-html-wrapper :deep(.ps-info) { display:grid; grid-template-columns:1fr 1fr; gap:6px 24px; margin-bottom:16px; padding:12px 16px; background:#f9fafb; border-radius:8px; }
.payslip-html-wrapper :deep(.ps-info .ps-label) { color:#6b7280; font-size:12px; text-transform:uppercase; letter-spacing:.03em; display:block; }
.payslip-html-wrapper :deep(.ps-info .ps-value) { font-weight:700; font-size:15px; }
.payslip-html-wrapper :deep(.ps-table) { width:100%; border-collapse:collapse; margin:8px 0; }
.payslip-html-wrapper :deep(.ps-table td) { padding:7px 12px; border-bottom:1px solid #f3f4f6; }
.payslip-html-wrapper :deep(.ps-right) { text-align:right; font-variant-numeric:tabular-nums; font-weight:650; }
.payslip-html-wrapper :deep(.ps-total td) { font-weight:800; font-size:16px; border-top:2px solid #1d2a3a; padding-top:10px; color:#1B6CB2; }
.payslip-html-wrapper :deep(.ps-net td) { font-weight:800; font-size:19px; color:#059669; padding:12px; background:#ecfdf5; border-radius:8px; }
.payslip-html-wrapper :deep(.ps-muted) { color:#9ca3af; }
.payslip-html-wrapper :deep(.ps-footer) { margin-top:20px; text-align:center; color:#9ca3af; font-size:12px; border-top:1px solid #e5e7eb; padding-top:14px; }
@media print { .payslip-html-wrapper :deep(.ps-container) { max-width:100%; box-shadow:none; } .payslip-html-wrapper :deep(.ps-body) { border:none; } }
</style>
