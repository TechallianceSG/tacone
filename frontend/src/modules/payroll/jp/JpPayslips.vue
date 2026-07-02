<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const payslips = ref<any[]>([])
const sendingIds = ref<Set<string>>(new Set())
const filterMonth = ref('')
const filterSearch = ref('')

const page = ref(1)
const pageSize = ref(20)

const filtered = ref<any[]>([])

// Payslip HTML preview dialog
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

function applyFilters() {
  let r = payslips.value
  if (filterMonth.value) r = r.filter((p: any) => p.payroll_month === filterMonth.value)
  if (filterSearch.value) {
    const q = filterSearch.value.toLowerCase()
    r = r.filter((p: any) => (p.employee_name || '').toLowerCase().includes(q) || (p.employee_number || '').toLowerCase().includes(q))
  }
  filtered.value = r
  page.value = 1
}

function clearFilters() {
  filterMonth.value = ''
  filterSearch.value = ''
  filtered.value = [...payslips.value]
  page.value = 1
}

async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.payslips()
    payslips.value = res.data.data?.items || res.data.data || []
    filtered.value = [...payslips.value]
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

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

async function viewPayslip(record: any) {
  const id = record.record_id || record.id
  previewEmployee.value = record
  previewDialog.value = true
  previewLoading.value = true
  previewHtml.value = ''
  try {
    // Try loading stored HTML first
    const res = await payrollJpApi.viewPayslipHtml(id)
    previewHtml.value = res.data?.data?.html || res.data?.html || ''
  } catch {
    previewHtml.value = '<p style="text-align:center;padding:40px;color:#9ca3af;">HTML preview not available</p>'
  }
  finally { previewLoading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.payslips') }}</h2>
      </div>
    </div>
    <div class="fiori-filters">
      <el-input v-model="filterSearch" :placeholder="t('action.search')" clearable style="width:200px" @keyup.enter="applyFilters" />
      <el-date-picker v-model="filterMonth" type="month" value-format="YYYY-MM" :placeholder="t('field.payroll_month')" clearable style="width:170px" />
      <el-button type="primary" @click="applyFilters">{{ t('action.filter') }}</el-button>
      <el-button @click="clearFilters">{{ t('action.clear') }}</el-button>
    </div>
    <div class="fiori-card">
      <el-table :data="paged" v-loading="loading" border stripe size="small" style="width:100%">
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
              {{ row.email_status === 'sent' ? '✅ ' + t('payroll.jp.email_sent') : row.email_status === 'failed' ? '❌ ' + t('payroll.jp.email_failed') : row.email_status || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="180" fixed="right">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="viewPayslip(row)">{{ t('payroll.jp.view') }}</el-button>
            <el-button size="small" text type="warning" :loading="sendingIds.has(row.record_id||row.id)" @click="sendEmail(row)">{{ t('payroll.jp.send_email') }}</el-button>
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
          background
          small
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- ═══ Payslip HTML Preview Dialog ═══ -->
    <el-dialog v-model="previewDialog" :title="t('payroll.jp.view') + ' — ' + (previewEmployee?.employee_name || '')" width="780px" top="3vh" destroy-on-close>
      <div v-loading="previewLoading" style="min-height:300px">
        <iframe v-if="previewHtml && !previewLoading" :srcdoc="previewHtml" style="width:100%;height:70vh;border:1px solid #e5e7eb;border-radius:6px" sandbox="allow-same-origin" />
        <div v-if="!previewHtml && !previewLoading" style="text-align:center;padding:60px;color:#9ca3af">
          {{ t('payroll.jp.no_records') }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width:1400px; margin:0 auto; padding:24px; font-size:15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; padding:16px; }
.fiori-card :deep(.el-table) { width: 100% !important; }
.fiori-card :deep(.el-table__body-wrapper) { overflow-x: auto !important; }
.helper-text { color:#6b7280; font-size:.85rem; }
</style>
