<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const payslips = ref<any[]>([])
const sendingIds = ref<Set<string>>(new Set())
const filterMonth = ref('')
const filterSearch = ref('')

const filtered = ref<any[]>([])

async function load() { loading.value = true; try { const res = await payrollJpApi.payslips(); payslips.value = res.data.data?.items || res.data.data || []; filtered.value = [...payslips.value] } catch (e: any) { ElMessage.error(e.message) } finally { loading.value = false } }
async function sendEmail(record: any) { const id = record.record_id || record.id; sendingIds.value.add(id); try { await payrollJpApi.sendPayslipEmail(id); ElMessage.success(t('action.email_sent')) } catch (e: any) { ElMessage.error(e.message) } finally { sendingIds.value.delete(id) } }
function viewPayslip(record: any) { router.push(`/payroll/jp/batches/${record.batch_id || record.sheet_id}/release`) }
function applyFilters() { let r = payslips.value; if (filterMonth.value) r = r.filter((p: any) => p.payroll_month === filterMonth.value); if (filterSearch.value) { const q = filterSearch.value.toLowerCase(); r = r.filter((p: any) => (p.employee_name || '').toLowerCase().includes(q) || (p.employee_number || '').toLowerCase().includes(q)) }; filtered.value = r }

onMounted(load)
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.payslips') }}</h2>
        <span class="count-chip">{{ filtered.length }} {{ t('action.records_total') }}</span>
      </div>
    </div>
    <div class="fiori-filters">
      <el-input v-model="filterSearch" :placeholder="t('action.search')" clearable style="width:200px" @input="applyFilters" />
      <el-input v-model="filterMonth" :placeholder="t('field.payroll_month') + ' (YYYY-MM)'" clearable style="width:170px" @input="applyFilters" />
    </div>
    <div class="fiori-card">
      <el-table :data="filtered" v-loading="loading" border stripe size="small">
        <el-table-column prop="employee_number" :label="t('field.employee_number')" width="120" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" min-width="160" show-overflow-tooltip />
        <el-table-column prop="payroll_month" :label="t('field.payroll_month')" width="110" />
        <el-table-column prop="gross_pay" :label="t('field.gross_pay')" width="130" align="right">
          <template #default="{row}">{{ row.gross_pay ? '¥' + Number(row.gross_pay).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="net_pay" :label="t('field.net_pay')" width="130" align="right">
          <template #default="{row}"><strong style="color:#1B6CB2">{{ row.net_pay ? '¥' + Number(row.net_pay).toLocaleString() : '-' }}</strong></template>
        </el-table-column>
        <el-table-column prop="status" :label="t('field.status')" width="100" align="center">
          <template #default="{row}"><el-tag size="small" :type="row.status==='sent'?'success':'info'">{{ row.status || '-' }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="180" fixed="right">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="viewPayslip(row)">{{ t('payroll.jp.view') }}</el-button>
            <el-button size="small" text type="warning" :loading="sendingIds.has(row.record_id||row.id)" @click="sendEmail(row)">{{ t('payroll.jp.send_email') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.fiori-page { max-width:1400px; margin:0 auto; padding:24px; font-size:15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.count-chip { background:#e8f0fe; color:#1B6CB2; padding:2px 12px; border-radius:12px; font-size:.82rem; font-weight:600; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
</style>
