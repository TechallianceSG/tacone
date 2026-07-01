<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="card" style="text-align:center;padding:48px">
      <p class="muted">Loading payslip data...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="card" style="text-align:center;padding:48px">
      <h2 style="color:var(--red)">Payslip Not Found</h2>
      <p class="muted">{{ error }}</p>
      <a href="javascript:history.back()" class="button secondary" style="margin-top:16px">← Back</a>
    </div>

    <!-- Payslip Content — exact match of original payslip_html_view -->
    <div v-else class="payslip-container">
      <div class="payslip-header">
        <h2>📄 Payslip / 工资单</h2>
        <div class="subtitle">{{ data.entity_name }}</div>
      </div>

      <div class="payslip-body">
        <!-- Info Grid -->
        <div class="payslip-info">
          <div><div class="label">Payroll Month / 月份</div><div class="value">{{ data.payroll_month }}</div></div>
          <div><div class="label">Employee / 员工</div><div class="value">{{ data.employee_name }}</div></div>
          <div><div class="label">Employee No / 工号</div><div class="value">{{ data.employee_number }}</div></div>
          <div><div class="label">Department / 部门</div><div class="value">{{ data.department }}</div></div>
          <div><div class="label">Salary Type / 薪资类型</div><div class="value">{{ salaryTypeLabel }}</div></div>
          <div><div class="label">Currency / 币种</div><div class="value">{{ data.currency }}</div></div>
        </div>

        <!-- Status Badge -->
        <span :class="['badge', statusBadgeClass]">{{ statusLabel }}</span>
        <span class="muted" style="font-size:11px;margin-left:8px">Generated: {{ formatDate(data.created_at) }}</span>

        <!-- Calculation Messages -->
        <div v-if="data.calculation_messages?.length" class="message-strip" style="margin-top:16px">
          <strong>📐 Calculation Notes / 计算说明</strong>
          <ul style="margin:4px 0 0;padding-left:20px;font-size:12px">
            <li v-for="msg in data.calculation_messages" :key="msg">{{ msg }}</li>
          </ul>
        </div>

        <!-- Earnings -->
        <h3>💰 Earnings / 应发</h3>
        <table class="payslip-table">
          <template v-if="data.earnings?.length">
            <tr v-for="item in data.earnings" :key="item.label" :class="{ 'muted': item.type === 'info' }" style="font-size:12px">
              <td>{{ item.label }}<span v-if="item.note" style="font-size:11px"> ({{ item.note }})</span></td>
              <td class="right"><template v-if="item.type !== 'info'">{{ fmt(item.amount) }}</template></td>
            </tr>
          </template>
          <tr v-else><td class="muted">No earnings data</td><td></td></tr>
          <tr class="total-row"><td>GROSS PAY / 应发合计</td><td class="right">{{ fmt(data.gross_pay) }}</td></tr>
        </table>

        <!-- Deductions -->
        <h3>📉 Deductions / 扣除</h3>
        <table class="payslip-table">
          <template v-if="data.deductions?.length">
            <tr v-for="item in data.deductions" :key="item.label">
              <td>{{ item.label }}</td>
              <td class="right">{{ fmt(item.amount) }}</td>
            </tr>
          </template>
          <tr v-else><td class="muted">No deductions</td><td></td></tr>
          <tr class="total-row"><td>TOTAL DEDUCTION / 扣除合计</td><td class="right">{{ fmt(data.deduction_total) }}</td></tr>
        </table>

        <!-- Net Pay -->
        <table class="payslip-table" style="margin-top:12px">
          <tr class="net-row"><td>💵 NET PAY / 实发</td><td class="right">{{ fmt(data.net_pay) }}</td></tr>
        </table>

        <!-- Employer Costs -->
        <template v-if="data.employer_costs?.length">
          <h3>🏢 Employer Costs / 雇主成本</h3>
          <table class="payslip-table">
            <tr v-for="item in data.employer_costs" :key="item.label">
              <td>{{ item.label }}</td>
              <td class="right">{{ fmt(item.amount) }}</td>
            </tr>
            <tr class="total-row"><td>TOTAL EMPLOYER COST</td><td class="right">{{ fmt(data.employer_cost_total) }}</td></tr>
          </table>
        </template>

        <!-- Bank Info -->
        <template v-if="data.bank_info">
          <h3>🏦 Bank Info / 银行信息</h3>
          <table class="payslip-table">
            <tr v-if="data.bank_info.bank_name">
              <td>Bank</td>
              <td>{{ data.bank_info.bank_name }}<template v-if="data.bank_info.bank_branch"> / {{ data.bank_info.bank_branch }}</template></td>
            </tr>
            <tr v-if="data.bank_info.bank_account">
              <td>Account</td>
              <td>{{ data.bank_info.bank_account }}<template v-if="data.bank_info.bank_account_type"> ({{ data.bank_info.bank_account_type }})</template></td>
            </tr>
          </table>
        </template>

        <!-- Footer -->
        <div class="payslip-footer">
          <p>Generated: {{ formatDate(data.created_at) }} · Computer-generated payslip · For queries contact HR: hr@tacjob.com</p>
          <a v-if="data.pdf_available" class="button" :href="pdfDownloadUrl" target="_blank" style="margin-top:12px">📥 Download PDF</a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const data = ref({})

const lang = computed(() => route.query.lang || 'zh')

const salaryTypeLabel = computed(() => {
  const labels = { monthly: 'Monthly / 月薪', hourly: 'Hourly / 时薪', daily: 'Daily / 日薪', monthly_hour: 'Monthly+Hour / 月薪+时薪' }
  return labels[data.value?.salary_type] || data.value?.salary_type || '—'
})

const statusLabel = computed(() => {
  const labels = { generated: '✅ Generated', sent: '📧 Sent', voided: '❌ Voided', draft: '📝 Draft' }
  return labels[data.value?.status] || data.value?.status || '—'
})

const statusBadgeClass = computed(() => {
  const map = { generated: 'active', sent: 'active', active: 'active', voided: 'voided', draft: 'draft', failed: 'voided' }
  return map[data.value?.status] || ''
})

const pdfDownloadUrl = computed(() => `/api/payslip/download?payslip_id=${encodeURIComponent(data.value?.payslip_id || '')}`)

function fmt(amount) {
  const curr = data.value?.currency || 'SGD'
  const num = typeof amount === 'number' ? amount : parseFloat(amount) || 0
  return `${curr} ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(isoStr) {
  if (!isoStr) return '—'
  try { return isoStr.replace('T', ' ').substring(0, 19) } catch { return isoStr }
}

async function fetchPayslip() {
  const payslipId = route.query.payslip_id
  if (!payslipId) { error.value = 'Missing payslip_id parameter.'; loading.value = false; return }

  loading.value = true; error.value = ''
  try {
    const sessionId = route.query.session_id || ''
    const params = new URLSearchParams({ payslip_id: payslipId, lang: lang.value })
    if (sessionId) params.set('session_id', sessionId)
    const res = await fetch(`/api/payslip/view?${params.toString()}`, { credentials: 'same-origin' })
    const json = await res.json()
    if (!res.ok || json.error) { error.value = json.error || `HTTP ${res.status}`; return }
    data.value = json
  } catch (e) {
    error.value = `Network error: ${e.message}`
  } finally {
    loading.value = false
  }
}

onMounted(fetchPayslip)
watch(() => route.query.payslip_id, fetchPayslip)
watch(lang, fetchPayslip)
</script>

<style scoped>
/* ===== EXACT MATCH of original payslip_html_view CSS ===== */
.payslip-container {
  max-width: 700px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', 'Noto Sans JP', Arial, sans-serif;
  font-size: 13px;
  color: #1a1a2e;
  line-height: 1.5;
}

.payslip-header {
  background: linear-gradient(135deg, #14213d 0%, #1a3a5c 100%);
  color: white;
  padding: 24px 28px;
  border-radius: 12px 12px 0 0;
}

.payslip-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 850;
}

.payslip-header .subtitle {
  opacity: .85;
  font-size: 13px;
}

.payslip-body {
  background: white;
  border: 1px solid #e0e5ec;
  border-top: none;
  padding: 24px 28px;
  border-radius: 0 0 12px 12px;
}

.payslip-body h3 {
  font-size: 14px;
  color: var(--navy);
  border-bottom: 2px solid var(--blue);
  padding-bottom: 6px;
  margin: 18px 0 10px;
}

.payslip-body h3:first-child {
  margin-top: 0;
}

.payslip-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 24px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.payslip-info .label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .03em;
}

.payslip-info .value {
  font-weight: 700;
  font-size: 14px;
}

.payslip-table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.payslip-table td {
  padding: 6px 12px;
  border-bottom: 1px solid #f0f2f5;
}

.payslip-table .right {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.payslip-table .total-row td {
  font-weight: 850;
  font-size: 15px;
  border-top: 2px solid var(--navy);
  padding-top: 10px;
  color: var(--blue);
}

.payslip-table .net-row td {
  font-weight: 850;
  font-size: 18px;
  color: var(--green);
  padding: 12px;
  background: #ecfdf5;
  border-radius: 8px;
}

.payslip-footer {
  margin-top: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 11px;
  border-top: 1px solid #e0e5ec;
  padding-top: 14px;
}

@media print {
  :deep(body) { background: white; margin: 0; padding: 0; }
  :deep(.site-header), :deep(.primary-nav), main > *:not(.payslip-container) { display: none !important; }
  .payslip-container { max-width: 100%; box-shadow: none; }
  .payslip-body { border: none; }
}

@media (max-width: 760px) {
  .payslip-container { max-width: 100%; }
  .payslip-header { padding: 20px 18px; }
  .payslip-body { padding: 20px 18px; }
  .payslip-info { grid-template-columns: 1fr; }
}
</style>
