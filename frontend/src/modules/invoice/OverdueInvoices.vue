<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { invoiceApi } from '@/api/client'

const { t } = useI18n()
const router = useRouter()
const loading = ref(false)
const overdueList = ref<any[]>([])
const total = ref(0)

async function load() {
  loading.value = true
  try { const res = await invoiceApi.overdue(); overdueList.value = res.data.data?.items || []; total.value = overdueList.value.length } finally { loading.value = false }
}

function viewDetail(id: string) { router.push(`/invoice/invoices/${id}`) }

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('invoice.overdue') }}</h3>
      <el-tag v-if="total > 0" type="danger" size="large">{{ total }} {{ t('invoice.overdue_count') }}</el-tag>
    </div>
    <el-table :data="overdueList" v-loading="loading" border stripe>
      <el-table-column prop="invoice_number" :label="t('field.invoice_number')" />
      <el-table-column prop="customer_name" :label="t('field.customer_name')" />
      <el-table-column prop="due_date" :label="t('field.due_date')" />
      <el-table-column prop="total_amount" :label="t('field.total_amount')" />
      <el-table-column prop="balance" :label="t('field.balance')">
        <template #default="{ row }"><span style="color: var(--el-color-danger); font-weight: 600">{{ row.balance }}</span></template>
      </el-table-column>
      <el-table-column prop="overdue_days" :label="t('field.overdue_days')">
        <template #default="{ row }">
          <el-tag :type="row.overdue_days > 60 ? 'danger' : row.overdue_days > 30 ? 'warning' : ''" size="small">{{ row.overdue_days }} days</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120" fixed="right">
        <template #default="{ row }"><el-button size="small" text @click="viewDetail(row.invoice_id)">{{ t('action.detail') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
</style>
