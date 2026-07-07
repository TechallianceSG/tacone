<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const payslips = ref<any[]>([])
const sendingIds = ref<Set<string>>(new Set())
const filterMonth = ref(new Date().toISOString().slice(0, 7))
const filterSearch = ref('')

const page = ref(1)
const pageSize = ref(20)

const filtered = ref<any[]>([])

const smtpConfigured = ref(false)
const unsentCount = computed(() => filtered.value.filter(r => r.email_status !== 'sent').length)

// ── Send progress dialog ──
const progressDialog = ref(false)
const progressProcessing = ref(false)
const progressData = ref({ sent: 0, failed: 0, total: 0, results: [] as any[] })

// ── Payslip HTML preview dialog ──
const previewDialog = ref(false)
const previewHtml = ref('')
const previewLoading = ref(false)
const previewEmployee = ref<any>(null)

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

function handlePageChange(p: number) { page.value = p }
function handleSizeChange(s: number) { pageSize.value = s; page.value = 1 }

function applyFilters() { load() }

function clearFilters() {
  filterMonth.value = new Date().toISOString().slice(0, 7)
  filterSearch.value = ''
  load()
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (filterMonth.value) params.payroll_month = filterMonth.value
    if (filterSearch.value) params.search = filterSearch.value
    const res = await payrollJpApi.payslips(params)
    filtered.value = res.data.data || []
    payslips.value = filtered.value
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

// ── Single Send ──
async function sendEmail(record: any) {
  const id = record.record_id || record.id
  sendingIds.value.add(id)
  try {
    await payrollJpApi.sendSinglePayslip(id)
    ElMessage.success(t('action.email_sent'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { sendingIds.value.delete(id) }
}

// ── Batch Send All ──
async function sendAll() {
  const count = unsentCount.value
  if (!count) {
    ElMessage.info(t('payroll.jp.no_unsent_payslips'))
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认发送 ${count} 封工资单邮件？已发送过的将自动跳过。`,
      '一键发送全部',
      { confirmButtonText: '发送', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }

  openProgressDialog()
  progressData.value.total = count

  try {
    const payload: Record<string, any> = {}
    if (filterMonth.value) payload.payroll_month = filterMonth.value
    if (filterSearch.value) payload.search = filterSearch.value
    const res = await payrollJpApi.sendPayslipsAll(payload)
    const data = res.data?.data || res.data || {}
    progressData.value.sent = data.sent || 0
    progressData.value.failed = data.failed || 0
    progressData.value.results = data.results || []
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    progressProcessing.value = false
    await load()
  }
}

function openProgressDialog() {
  progressData.value = { sent: 0, failed: 0, total: 0, results: [] }
  progressProcessing.value = true
  progressDialog.value = true
}

async function resendFailed() {
  const failedIds = progressData.value.results
    .filter(r => r.status === 'failed')
    .map(r => r.record_id)
    .filter(Boolean)
  if (!failedIds.length) return

  progressProcessing.value = true
  progressData.value.sent = 0
  progressData.value.failed = 0
  progressData.value.total = failedIds.length
  progressData.value.results = []

  try {
    const res = await payrollJpApi.sendPayslipsSelected({ record_ids: failedIds })
    const data = res.data?.data || res.data || {}
    progressData.value.sent = data.sent || 0
    progressData.value.failed = data.failed || 0
    progressData.value.results = data.results || []
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    progressProcessing.value = false
    await load()
  }
}

const progressPercent = computed(() => {
  if (!progressData.value.total) return 0
  return Math.round(((progressData.value.sent + progressData.value.failed) / progressData.value.total) * 100)
})

// ── Preview ──
async function viewPayslip(record: any) {
  const id = record.record_id || record.id
  previewEmployee.value = record
  previewDialog.value = true
  previewLoading.value = true
  previewHtml.value = ''
  try {
    const res = await payrollJpApi.viewPayslipHtml(id)
    previewHtml.value = res.data?.data?.html || res.data?.html || ''
    if (!previewHtml.value) {
      previewHtml.value = '<div style="text-align:center;padding:60px;color:#9ca3af;font-family:sans-serif;"><p>😕 HTML preview not available</p><p style="font-size:12px;">The payslip may not have been generated yet.</p></div>'
    }
  } catch {
    previewHtml.value = '<div style="text-align:center;padding:60px;color:#9ca3af;font-family:sans-serif;"><p>😕 HTML preview not available</p></div>'
  }
  finally { previewLoading.value = false }
}

// ── Email Logs ──
const emailLogs = ref<any[]>([])
const logLoading = ref(false)
const logDialog = ref(false)
const logPage = ref(1)
const logPageSize = ref(20)
const logPaged = computed(() => {
  const start = (logPage.value - 1) * logPageSize.value
  return emailLogs.value.slice(start, start + logPageSize.value)
})

async function openLogDialog() {
  logDialog.value = true
  logPage.value = 1
  logLoading.value = true
  try {
    const res = await payrollJpApi.emailLogs({ limit: 500 })
    emailLogs.value = res.data?.data || res.data || []
  } catch { emailLogs.value = [] }
  finally { logLoading.value = false }
}

onMounted(async () => {
  await load()
  // Check SMTP status
  try {
    const res = await payrollJpApi.getSmtpStatus()
    smtpConfigured.value = res.data?.data?.smtp_configured || res.data?.smtp_configured || false
  } catch { smtpConfigured.value = false }
})
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.payslips') }}</h2>
        <span v-if="!smtpConfigured" class="smtp-warning">
          ⚠️ {{ t('payroll.jp.smtp_not_configured') }}
        </span>
      </div>
    </div>

    <!-- Filters -->
    <div class="fiori-filters">
      <el-input v-model="filterSearch" :placeholder="t('payroll.jp.search_employee_placeholder')" clearable style="width:240px" @keyup.enter="applyFilters" />
      <el-date-picker v-model="filterMonth" type="month" format="YYYY-MM" value-format="YYYY-MM" :placeholder="t('field.payroll_month')" style="width:160px" />
      <el-button type="primary" @click="applyFilters">{{ t('action.filter') }}</el-button>
      <el-button @click="clearFilters">{{ t('action.clear') }}</el-button>
      <el-button text type="info" @click="openLogDialog">📋 发送日志</el-button>
    </div>

    <!-- Batch Action Bar -->
    <div class="batch-bar" :class="{ 'batch-disabled': !smtpConfigured }">
      <div class="batch-left">
        <span class="batch-count">{{ unsentCount }} 封待发送</span>
        <span v-if="!smtpConfigured" style="font-size:.78rem;color:#e65100;">⚠️ 前往<router-link to="/payroll/jp/email-settings" style="color:#1B6CB2;">邮件设置</router-link>配置SMTP后即可发送</span>
      </div>
      <div class="batch-actions">
        <el-tooltip :content="!smtpConfigured ? '请先在邮件设置中配置SMTP' : ''" placement="top">
          <el-button type="primary" :disabled="!unsentCount || !smtpConfigured" @click="sendAll">
            📨 一键发送全部{{ unsentCount ? `（${unsentCount}封）` : '' }}
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- Table -->
    <div class="fiori-card">
      <el-table
        :data="paged"
        v-loading="loading"
        border stripe size="small"
        style="width:100%"
      >
        <el-table-column type="index" min-width="50" :index="(idx: number) => (page - 1) * pageSize + idx + 1" />
        <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="120" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="160" show-overflow-tooltip />
        <el-table-column prop="payroll_month" :label="t('field.payroll_month')" min-width="110" />
        <el-table-column prop="gross_pay" :label="t('field.gross_pay')" min-width="130" align="right">
          <template #default="{row}">{{ row.gross_pay ? '¥' + Number(row.gross_pay).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="net_pay" :label="t('field.net_pay')" min-width="130" align="right">
          <template #default="{row}"><strong style="color:#1B6CB2">{{ row.net_pay ? '¥' + Number(row.net_pay).toLocaleString() : '-' }}</strong></template>
        </el-table-column>
        <el-table-column prop="email_status" :label="t('field.email_status')" min-width="110" align="center">
          <template #default="{row}">
            <el-tag size="small" :type="row.email_status==='sent'?'success':row.email_status==='failed'?'danger':'info'">
              {{ row.email_status === 'sent' ? '✅ ' + t('payroll.jp.email_sent') : row.email_status === 'failed' ? '❌ ' + t('payroll.jp.email_failed') : row.email_status || '—' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="180" fixed="right">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="viewPayslip(row)">👁️ {{ t('payroll.jp.view') }}</el-button>
            <el-button
              size="small" text type="warning"
              :loading="sendingIds.has(row.record_id||row.id)"
              :disabled="!smtpConfigured"
              @click="sendEmail(row)"
            >📤 {{ t('payroll.jp.send_email') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
        <span class="helper-text">{{ filtered.length }} {{ t('action.records_total') }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filtered.length"
          layout="total, sizes, prev, pager, next, jumper"
          background small
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- ═══ Email Logs Dialog ═══ -->
    <el-dialog v-model="logDialog" title="📋 邮件发送日志" width="900px" top="3vh" destroy-on-close>
      <div v-loading="logLoading" style="min-height:200px;">
        <template v-if="logPaged.length">
          <el-table :data="logPaged" border stripe size="small" style="width:100%">
            <el-table-column prop="sent_at" label="发送时间" min-width="160">
              <template #default="{row}">{{ row.sent_at?.slice(0, 19) || '—' }}</template>
            </el-table-column>
            <el-table-column prop="employee_name" label="员工" min-width="120" show-overflow-tooltip />
            <el-table-column prop="recipient_email" label="收件人" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" min-width="70" align="center">
              <template #default="{row}">
                <el-tag size="small" :type="row.status==='sent'?'success':'danger'">{{ row.status==='sent'?'✅ 成功':'❌ 失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="sent_by" label="操作人" min-width="100" />
            <el-table-column prop="error_message" label="失败原因" min-width="180" show-overflow-tooltip>
              <template #default="{row}"><span :style="{color:row.error_message?'#dc2626':'#9ca3af'}">{{ row.error_message || '—' }}</span></template>
            </el-table-column>
          </el-table>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;padding:0 4px">
            <span class="helper-text">{{ emailLogs.length }} 条记录</span>
            <el-pagination
              v-model:current-page="logPage"
              v-model:page-size="logPageSize"
              :page-sizes="[10, 20, 50]"
              :total="emailLogs.length"
              layout="total, sizes, prev, pager, next"
              background small
            />
          </div>
        </template>
        <div v-else style="text-align:center;padding:40px;color:#9ca3af;">暂无发送记录</div>
      </div>
      <template #footer><el-button @click="logDialog = false">关闭</el-button></template>
    </el-dialog>

    <!-- ═══ Send Progress Dialog ═══ -->
    <el-dialog
      v-model="progressDialog"
      :title="t('payroll.jp.send_progress_title')"
      width="700px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      destroy-on-close
    >
      <div style="padding:8px 0;">
        <!-- Progress -->
        <div v-if="progressProcessing" style="text-align:center;padding:20px 0;">
          <el-progress :percentage="progressPercent" :stroke-width="18" :text-inside="true" />
          <p style="color:#6b7280;margin-top:12px;font-size:14px;">{{ t('payroll.jp.test_email_sending') }}</p>
        </div>
        <!-- Summary -->
        <div v-else class="send-summary">
          <div class="summary-cards">
            <div class="summary-card success">
              <div class="summary-num">{{ progressData.sent }}</div>
              <div class="summary-label">✅ Sent</div>
            </div>
            <div class="summary-card danger">
              <div class="summary-num">{{ progressData.failed }}</div>
              <div class="summary-label">❌ Failed</div>
            </div>
            <div class="summary-card">
              <div class="summary-num">{{ progressData.total }}</div>
              <div class="summary-label">📋 Total</div>
            </div>
          </div>
          <h4 style="margin:16px 0 8px;font-size:14px;color:#1d2a3a;">{{ t('payroll.jp.send_complete') }}</h4>
        </div>

        <!-- Results Table -->
        <div v-if="progressData.results.length" style="max-height:300px;overflow-y:auto;margin-top:8px;">
          <table class="result-table">
            <thead>
              <tr>
                <th>{{ t('field.employee_name') }}</th>
                <th style="text-align:center;width:80px;">Status</th>
                <th style="width:200px;">Error</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in progressData.results" :key="i" :class="{ 'row-failed': r.status === 'failed' }">
                <td>{{ r.employee_name || r.record_id || '—' }}</td>
                <td style="text-align:center;">
                  <span v-if="r.status === 'sent'">✅</span>
                  <span v-else>❌</span>
                </td>
                <td style="font-size:12px;color:#dc2626;">{{ r.error || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <template #footer>
        <div style="display:flex;justify-content:space-between;">
          <el-button v-if="progressData.failed > 0 && !progressProcessing" type="warning" size="small" @click="resendFailed">
            🔄 {{ t('payroll.jp.resend_failed') }}
          </el-button>
          <span v-else></span>
          <el-button :disabled="progressProcessing" @click="progressDialog = false">{{ t('action.close') }}</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ═══ Payslip HTML Preview Dialog ═══ -->
    <el-dialog
      v-model="previewDialog"
      width="1000px"
      top="2vh"
      destroy-on-close
      :close-on-click-modal="false"
      class="preview-dialog"
    >
      <template #header>
        <div class="preview-header">
          <div>
            <span class="preview-title">{{ t('payroll.jp.view') }}</span>
            <span class="preview-subtitle">— {{ previewEmployee?.employee_name || '' }}</span>
            <span v-if="previewEmployee?.employee_number" class="preview-badge">{{ previewEmployee.employee_number }}</span>
          </div>
        </div>
      </template>

      <div style="min-height:350px;position:relative;">
        <!-- Loading Skeleton -->
        <div v-if="previewLoading" class="preview-skeleton">
          <el-skeleton :rows="3" animated />
          <el-skeleton style="margin-top:16px;" :rows="6" animated />
          <el-skeleton style="margin-top:16px;" :rows="3" animated />
        </div>

        <!-- Iframe -->
        <iframe
          v-if="previewHtml && !previewLoading"
          :srcdoc="previewHtml"
          class="preview-iframe"
          sandbox="allow-same-origin allow-print"
          title="Payslip Preview"
        />

        <!-- Empty -->
        <div v-if="!previewHtml && !previewLoading" class="preview-empty">
          <span style="font-size:48px;">📄</span>
          <p>{{ t('payroll.jp.no_records') }}</p>
        </div>
      </div>

      <template #footer>
        <el-button @click="previewDialog = false">{{ t('action.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1400px; margin: 0 auto; padding: 24px; font-size: 15px; }
.fiori-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.toolbar-left h2 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #1d2a3a; }
.smtp-warning { font-size: .82rem; color: #e65100; background: #fff3e0; padding: 3px 10px; border-radius: 12px; }

.fiori-filters { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; align-items: center; }
.fiori-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; padding: 16px; }
.fiori-card :deep(.el-table) { width: 100% !important; }
.fiori-card :deep(.el-table__body-wrapper) { overflow-x: auto !important; }
.helper-text { color: #6b7280; font-size: .85rem; }

/* Batch Bar */
.batch-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; margin-bottom: 10px;
  background: #f0f5ff; border: 1px solid #c7d8f5; border-radius: 8px;
  min-height: 36px;
}
.batch-disabled { background: #fefce8; border-color: #fde68a; }
.batch-left { display: flex; align-items: center; gap: 8px; }
.batch-count { font-size: .85rem; font-weight: 600; color: #1B6CB2; }
.batch-actions { display: flex; gap: 8px; }

/* Progress Dialog */
.send-summary { text-align: center; }
.summary-cards { display: flex; gap: 16px; justify-content: center; }
.summary-card {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 16px 28px; text-align: center; min-width: 100px;
}
.summary-card.success { border-color: #86efac; background: #f0fdf4; }
.summary-card.danger { border-color: #fca5a5; background: #fef2f2; }
.summary-num { font-size: 1.8rem; font-weight: 800; color: #1d2a3a; }
.summary-label { font-size: .8rem; color: #6b7280; margin-top: 2px; }

/* Result Table */
.result-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.result-table th { text-align: left; padding: 6px 8px; border-bottom: 2px solid #e5e7eb; color: #6b7280; font-weight: 600; }
.result-table td { padding: 5px 8px; border-bottom: 1px solid #f3f4f6; }
.result-table .row-failed { background: #fef2f2; }

/* Preview Dialog */
.preview-header { display: flex; align-items: center; gap: 8px; }
.preview-title { font-size: 1.1rem; font-weight: 700; color: #1d2a3a; }
.preview-subtitle { font-size: 1rem; color: #374151; }
.preview-badge { font-size: .75rem; background: #e5e7eb; color: #6b7280; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }

.preview-skeleton { padding: 20px; }
.preview-iframe {
  width: 100%; height: 78vh;
  border: 1px solid #e5e7eb; border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  background: #fff;
}
.preview-empty { text-align: center; padding: 60px; color: #9ca3af; }
.preview-empty p { margin-top: 12px; font-size: 15px; }
</style>

<style>
/* Global overrides for the preview dialog */
.preview-dialog .el-dialog__header { padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; margin-bottom: 0; }
.preview-dialog .el-dialog__body { padding: 12px 20px; }
.preview-dialog .el-dialog__footer { padding-top: 8px; border-top: 1px solid #e5e7eb; }

</style>
