<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { invoiceApi } from '@/api/client'
import { ElMessage } from 'element-plus'
import { INVOICE_STATUS_CONFIG, INVOICE_PAYMENT_METHODS } from '@/constants/invoice'

const route = useRoute()
const { t } = useI18n()
const loading = ref(false)
const invoice = ref<any>({})
const paymentDialog = ref(false)
const paymentForm = ref({ amount: 0, payment_method: INVOICE_PAYMENT_METHODS[0].value, payment_date: '', reference_number: '' })

async function load() {
  loading.value = true
  try { const res = await invoiceApi.get(route.params.id as string); invoice.value = res.data.data || {} } finally { loading.value = false }
}

async function submit() {
  try { await invoiceApi.submit(route.params.id as string); ElMessage.success(t('invoice.submitted')); load() } catch (e: any) { ElMessage.error(e.message) }
}
async function approve() {
  try { await invoiceApi.approve(route.params.id as string); ElMessage.success(t('invoice.approved')); load() } catch (e: any) { ElMessage.error(e.message) }
}
async function reject() {
  try { await invoiceApi.reject(route.params.id as string); ElMessage.success(t('invoice.rejected')); load() } catch (e: any) { ElMessage.error(e.message) }
}
async function sendEmail() {
  try { await invoiceApi.sendEmail(route.params.id as string); ElMessage.success(t('action.email_sent')); load() } catch (e: any) { ElMessage.error(e.message) }
}

async function registerPayment() {
  try {
    await invoiceApi.registerPayment(route.params.id as string, paymentForm.value)
    paymentDialog.value = false
    ElMessage.success(t('invoice.payment_registered'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

const statusTagType = (s: string) => (INVOICE_STATUS_CONFIG[s]?.type || 'warning') as string

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('invoice.detail') }} — {{ invoice.invoice_number }}</h3>
      <div class="header-actions">
        <el-button v-if="invoice.status === 'draft'" type="warning" @click="submit">{{ t('invoice.submit') }}</el-button>
        <el-button v-if="invoice.status === 'pending_approval'" type="success" @click="approve">{{ t('invoice.approve') }}</el-button>
        <el-button v-if="invoice.status === 'pending_approval'" type="danger" @click="reject">{{ t('invoice.reject') }}</el-button>
        <el-button v-if="invoice.status === 'approved'" type="primary" @click="sendEmail">{{ t('action.send_email') }}</el-button>
        <el-button v-if="invoice.status === 'sent' || invoice.status === 'approved'" @click="paymentDialog = true">{{ t('invoice.register_payment') }}</el-button>
      </div>
    </div>

    <!-- Invoice Info -->
    <el-descriptions :column="3" border style="margin-bottom: 20px">
      <el-descriptions-item :label="t('field.invoice_number')">{{ invoice.invoice_number }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.status')">
        <el-tag :type="statusTagType(invoice.status)">{{ invoice.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item :label="t('field.customer_name')">{{ invoice.customer_name }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.invoice_date')">{{ invoice.invoice_date }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.due_date')">{{ invoice.due_date }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.currency')">{{ invoice.currency }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.subtotal')">{{ invoice.subtotal }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.tax_amount')">{{ invoice.tax_amount }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.total_amount')"><strong>{{ invoice.total_amount }}</strong></el-descriptions-item>
    </el-descriptions>

    <!-- Items -->
    <el-card header="Line Items" style="margin-bottom: 20px">
      <el-table :data="invoice.items || []" border stripe size="small">
        <el-table-column prop="description" :label="t('field.description')" />
        <el-table-column prop="employee_name" :label="t('field.employee_name')" />
        <el-table-column prop="quantity" :label="t('field.quantity')" />
        <el-table-column prop="unit_price" :label="t('field.unit_price')" />
        <el-table-column prop="amount" :label="t('field.amount')" />
      </el-table>
    </el-card>

    <!-- Approval History -->
    <el-card header="Approval History" style="margin-bottom: 20px">
      <el-timeline>
        <el-timeline-item v-for="rec in (invoice.approvals || [])" :key="rec.approval_id"
          :timestamp="rec.acted_at" placement="top"
          :type="rec.action === 'approved' ? 'success' : rec.action === 'rejected' ? 'danger' : 'primary'">
          <p><strong>{{ rec.approver_name }}</strong> — {{ rec.action }}</p>
          <p v-if="rec.comment" style="color:#999">{{ rec.comment }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- Payments -->
    <el-card header="Payments" style="margin-bottom: 20px">
      <el-table :data="invoice.payments || []" border stripe size="small">
        <el-table-column prop="payment_date" :label="t('field.payment_date')" />
        <el-table-column prop="amount" :label="t('field.amount')" />
        <el-table-column prop="payment_method" :label="t('field.payment_method')" />
        <el-table-column prop="reference_number" :label="t('field.reference_number')" />
      </el-table>
    </el-card>

    <!-- Payment Dialog -->
    <el-dialog v-model="paymentDialog" :title="t('invoice.register_payment')" width="450px">
      <el-form :model="paymentForm" label-width="130px">
        <el-form-item :label="t('field.amount')"><el-input-number v-model="paymentForm.amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.payment_date')"><el-input v-model="paymentForm.payment_date" type="date" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.payment_method')">
          <el-select v-model="paymentForm.payment_method" style="width:100%">
            <el-option v-for="pm in INVOICE_PAYMENT_METHODS" :key="pm.value" :label="pm.label" :value="pm.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.reference_number')"><el-input v-model="paymentForm.reference_number" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="paymentDialog = false">{{ t('action.cancel') }}</el-button><el-button type="primary" @click="registerPayment">{{ t('action.save') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
