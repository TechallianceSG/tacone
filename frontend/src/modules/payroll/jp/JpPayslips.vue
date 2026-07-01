<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const payslips = ref<any[]>([])
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.payslips()
    payslips.value = res.data.data?.items || []
    total.value = payslips.value.length
  } finally { loading.value = false }
}

async function sendEmail(id: string) {
  try { await payrollJpApi.emailPayslip(id); ElMessage.success(t('action.email_sent')) } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header"><h3>{{ t('payroll.jp.payslips') }}</h3></div>
    <el-table :data="payslips" v-loading="loading" border stripe>
      <el-table-column prop="employee_name" :label="t('field.employee_name')" />
      <el-table-column prop="payroll_month" :label="t('field.payroll_month')" />
      <el-table-column prop="gross_pay" :label="t('field.gross_pay')" />
      <el-table-column prop="net_pay" :label="t('field.net_pay')" />
      <el-table-column prop="currency" :label="t('field.currency')" />
      <el-table-column :label="t('action.actions')" width="120">
        <template #default="{ row }"><el-button size="small" text type="primary" @click="sendEmail(row.record_id)">{{ t('action.send_email') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
</style>
