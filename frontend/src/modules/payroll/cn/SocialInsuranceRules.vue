<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollCnApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const rules = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ city: '', status: 'active' })

async function load() {
  loading.value = true
  try {
    const res = await payrollCnApi.socialInsuranceRules()
    rules.value = res.data.data?.items || []
    total.value = rules.value.length
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  form.value = row ? { ...row } : { city: '', status: 'active' }
  dialogVisible.value = true
}

async function save() {
  try { await payrollCnApi.saveSIRule(form.value); dialogVisible.value = false; ElMessage.success(t('action.saved')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.cn.rules') }}</h3>
      <el-button type="primary" @click="openDialog()">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="rules" v-loading="loading" border stripe>
      <el-table-column prop="city" :label="t('field.city')" />
      <el-table-column prop="pension_employee_rate" :label="t('field.pension_employee_rate')" />
      <el-table-column prop="medical_employee_rate" :label="t('field.medical_employee_rate')" />
      <el-table-column prop="housing_fund_employee_rate" :label="t('field.housing_fund_employee_rate')" />
      <el-table-column prop="status" :label="t('field.status')">
        <template #default="{ row }"><el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120">
        <template #default="{ row }"><el-button size="small" text @click="openDialog(row)">{{ t('action.edit') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('payroll.cn.rules')" width="550px">
      <el-form :model="form" label-width="180px">
        <el-form-item :label="t('field.city')"><el-input v-model="form.city" /></el-form-item>
        <el-form-item :label="t('field.pension_employee_rate')"><el-input v-model="form.pension_employee_rate" placeholder="0.08" /></el-form-item>
        <el-form-item :label="t('field.medical_employee_rate')"><el-input v-model="form.medical_employee_rate" placeholder="0.02" /></el-form-item>
        <el-form-item :label="t('field.unemployment_employee_rate')"><el-input v-model="form.unemployment_employee_rate" placeholder="0.005" /></el-form-item>
        <el-form-item :label="t('field.housing_fund_employee_rate')"><el-input v-model="form.housing_fund_employee_rate" placeholder="0.07" /></el-form-item>
        <el-form-item :label="t('field.social_insurance_base_min')"><el-input-number v-model="form.social_insurance_base_min" :min="0" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.social_insurance_base_max')"><el-input-number v-model="form.social_insurance_base_max" :min="0" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button><el-button type="primary" @click="save">{{ t('action.save') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
</style>
