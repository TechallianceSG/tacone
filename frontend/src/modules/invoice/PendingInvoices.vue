<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { invoiceApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const pending = ref<any[]>([])
const total = ref(0)

async function load() {
  loading.value = true
  try { const res = await invoiceApi.pending(); pending.value = res.data.data?.items || []; total.value = pending.value.length } finally { loading.value = false }
}

async function scanPending() {
  try { const res = await invoiceApi.scanPending(); ElMessage.success(t('invoice.scanned', { count: res.data.data.created })); load() } catch (e: any) { ElMessage.error(e.message) }
}

async function convert(id: string) {
  try { await invoiceApi.convertPending(id); ElMessage.success(t('invoice.converted')); load() } catch (e: any) { ElMessage.error(e.message) }
}

async function remind(id: string) {
  try { await invoiceApi.remindPending(id); ElMessage.success(t('invoice.reminded')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('invoice.pending') }}</h3>
      <el-button type="primary" @click="scanPending">{{ t('invoice.scan') }}</el-button>
    </div>
    <el-table :data="pending" v-loading="loading" border stripe>
      <el-table-column prop="customer_name" :label="t('field.customer_name')" />
      <el-table-column prop="project_name" :label="t('field.project_name')" />
      <el-table-column prop="period_start" :label="t('field.period_start')" />
      <el-table-column prop="period_end" :label="t('field.period_end')" />
      <el-table-column prop="estimated_amount" :label="t('field.estimated_amount')" />
      <el-table-column prop="status" :label="t('field.status')">
        <template #default="{ row }"><el-tag size="small" :type="row.status === 'converted' ? 'success' : row.status === 'reminded' ? 'warning' : 'info'">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="200">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button size="small" text type="primary" @click="convert(row.pending_id)">{{ t('invoice.convert') }}</el-button>
            <el-button size="small" text type="warning" @click="remind(row.pending_id)">{{ t('invoice.remind') }}</el-button>
          </template>
        </template>
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
