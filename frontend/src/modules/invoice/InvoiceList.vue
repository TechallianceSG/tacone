<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { invoiceApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()
const loading = ref(false)
const invoices = ref<any[]>([])
const total = ref(0)
const statusFilter = ref('')
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ currency: 'JPY', tax_rate: '10%', status: 'draft' })

async function load() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (statusFilter.value) params.status = statusFilter.value
    const res = await invoiceApi.list(params)
    invoices.value = res.data.data?.items || []
    total.value = invoices.value.length
  } finally { loading.value = false }
}

function viewDetail(id: string) { router.push(`/invoice/invoices/${id}`) }

async function createInvoice() {
  try {
    await invoiceApi.create(form.value)
    dialogVisible.value = false
    ElMessage.success(t('action.created'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function submitInvoice(id: string) {
  try { await invoiceApi.submit(id); ElMessage.success(t('invoice.submitted')); load() } catch (e: any) { ElMessage.error(e.message) }
}

async function approveInvoice(id: string) {
  try { await invoiceApi.approve(id); ElMessage.success(t('invoice.approved')); load() } catch (e: any) { ElMessage.error(e.message) }
}

async function sendEmail(id: string) {
  try { await invoiceApi.sendEmail(id); ElMessage.success(t('action.email_sent')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('invoice.list') }}</h3>
      <div class="header-actions">
        <el-select v-model="statusFilter" :placeholder="t('field.status')" clearable @change="load" style="width:140px;margin-right:12px">
          <el-option label="Draft" value="draft" /><el-option label="Pending Approval" value="pending_approval" />
          <el-option label="Approved" value="approved" /><el-option label="Sent" value="sent" /><el-option label="Paid" value="paid" />
        </el-select>
        <el-button type="primary" @click="dialogVisible = true">{{ t('action.create') }}</el-button>
      </div>
    </div>
    <el-table :data="invoices" v-loading="loading" border stripe>
      <el-table-column prop="invoice_number" :label="t('field.invoice_number')" />
      <el-table-column prop="customer_name" :label="t('field.customer_name')" />
      <el-table-column prop="total_amount" :label="t('field.total_amount')" />
      <el-table-column prop="currency" :label="t('field.currency')" width="80" />
      <el-table-column prop="status" :label="t('field.status')">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'approved' ? 'success' : row.status === 'sent' ? 'primary' : row.status === 'paid' ? 'info' : row.status === 'draft' ? '' : 'warning'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="260">
        <template #default="{ row }">
          <el-button size="small" text @click="viewDetail(row.invoice_id)">{{ t('action.detail') }}</el-button>
          <el-button v-if="row.status === 'draft'" size="small" text type="warning" @click="submitInvoice(row.invoice_id)">{{ t('invoice.submit') }}</el-button>
          <el-button v-if="row.status === 'pending_approval'" size="small" text type="success" @click="approveInvoice(row.invoice_id)">{{ t('invoice.approve') }}</el-button>
          <el-button v-if="row.status === 'approved'" size="small" text type="primary" @click="sendEmail(row.invoice_id)">{{ t('action.send_email') }}</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('action.create')" width="500px">
      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('field.project_id')"><el-input v-model="form.project_id" /></el-form-item>
        <el-form-item :label="t('field.customer_name')"><el-input v-model="form.customer_name" /></el-form-item>
        <el-form-item :label="t('field.total_amount')"><el-input-number v-model="form.total_amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.currency')"><el-input v-model="form.currency" /></el-form-item>
        <el-form-item :label="t('field.tax_rate')"><el-input v-model="form.tax_rate" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button><el-button type="primary" @click="createInvoice">{{ t('action.create') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.header-actions { display: flex; align-items: center; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
</style>
