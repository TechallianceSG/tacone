<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollCnApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()
const loading = ref(false)
const batches = ref<any[]>([])
const dialogVisible = ref(false)
const form = ref({ payroll_month: '', entity_id: '', notes: '' })

async function load() {
  loading.value = true
  try { const res = await payrollCnApi.batches(); batches.value = res.data.data?.items || [] } finally { loading.value = false }
}

async function create() {
  try { await payrollCnApi.createBatch(form.value); dialogVisible.value = false; ElMessage.success(t('action.created')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.cn.batches') }}</h3>
      <el-button type="primary" @click="dialogVisible = true">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="batches" v-loading="loading" border stripe>
      <el-table-column prop="batch_id" :label="t('field.batch_id')" />
      <el-table-column prop="payroll_month" :label="t('field.payroll_month')" />
      <el-table-column prop="status" :label="t('field.status')">
        <template #default="{ row }"><el-tag :type="row.status === 'calculated' ? 'success' : 'info'">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="employee_count" :label="t('field.employee_count')" />
      <el-table-column prop="gross_total" :label="t('field.gross_total')" />
      <el-table-column prop="net_total" :label="t('field.net_total')" />
    </el-table>
    <div class="helper-text">{{ batches.length }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('action.create')" width="400px">
      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('field.payroll_month')"><el-input v-model="form.payroll_month" placeholder="2026-07" /></el-form-item>
        <el-form-item :label="t('field.entity_id')"><el-input v-model="form.entity_id" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button><el-button type="primary" @click="create">{{ t('action.create') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
</style>
