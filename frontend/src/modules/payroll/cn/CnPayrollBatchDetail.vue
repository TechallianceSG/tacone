<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollCnApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const route = useRoute()
const { t } = useI18n()
const batch = ref<any>({})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await payrollCnApi.batches()
    const batches = res.data.data?.items || []
    batch.value = batches.find((b: any) => b.batch_id === route.params.id) || {}
  } finally { loading.value = false }
}

async function calculate() {
  try { await payrollCnApi.calculateBatch(route.params.id as string); ElMessage.success(t('payroll.cn.calculated')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.cn.batch_detail') }} — {{ batch.batch_id }}</h3>
      <el-button v-if="batch.status === 'draft'" type="primary" @click="calculate">{{ t('payroll.cn.calculate') }}</el-button>
    </div>
    <el-descriptions :column="3" border>
      <el-descriptions-item :label="t('field.payroll_month')">{{ batch.payroll_month }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.status')"><el-tag :type="batch.status === 'calculated' ? 'success' : 'info'">{{ batch.status }}</el-tag></el-descriptions-item>
      <el-descriptions-item :label="t('field.entity_id')">{{ batch.entity_id }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.employee_count')">{{ batch.employee_count }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.gross_total')">{{ batch.gross_total }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.net_total')">{{ batch.net_total }}</el-descriptions-item>
      <el-descriptions-item :label="t('field.employer_cost_total')">{{ batch.employer_cost_total }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
</style>
