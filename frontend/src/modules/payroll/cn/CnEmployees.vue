<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollCnApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const employees = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ city: '上海', salary_type: 'monthly', payroll_currency: 'CNY', active: true })

async function load() {
  loading.value = true
  try {
    const res = await payrollCnApi.employees()
    employees.value = res.data.data?.items || []
    total.value = employees.value.length
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  form.value = row ? { ...row } : { city: '上海', salary_type: 'monthly', payroll_currency: 'CNY', active: true }
  dialogVisible.value = true
}

async function save() {
  try { await payrollCnApi.saveEmployee(form.value); dialogVisible.value = false; ElMessage.success(t('action.saved')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.cn.employees') }}</h3>
      <el-button type="primary" @click="openDialog()">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="employees" v-loading="loading" border stripe>
      <el-table-column prop="employee_number" :label="t('field.employee_number')" />
      <el-table-column prop="employee_name" :label="t('field.employee_name')" />
      <el-table-column prop="city" :label="t('field.city')" />
      <el-table-column prop="salary_type" :label="t('field.salary_type')" />
      <el-table-column prop="basic_salary" :label="t('field.basic_salary')" />
      <el-table-column prop="active" :label="t('field.active')">
        <template #default="{ row }"><el-tag :type="row.active ? 'success' : 'info'" size="small">{{ row.active ? 'Active' : 'Inactive' }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120">
        <template #default="{ row }"><el-button size="small" text @click="openDialog(row)">{{ t('action.edit') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('payroll.cn.employees')" width="550px">
      <el-form :model="form" label-width="150px">
        <el-form-item :label="t('field.employee_id')"><el-input v-model="form.employee_id" /></el-form-item>
        <el-form-item :label="t('field.employee_number')"><el-input v-model="form.employee_number" /></el-form-item>
        <el-form-item :label="t('field.employee_name')"><el-input v-model="form.employee_name" /></el-form-item>
        <el-form-item :label="t('field.city')"><el-input v-model="form.city" /></el-form-item>
        <el-form-item :label="t('field.salary_type')"><el-select v-model="form.salary_type"><el-option label="Monthly" value="monthly" /><el-option label="Hourly" value="hourly" /></el-select></el-form-item>
        <el-form-item :label="t('field.basic_salary')"><el-input-number v-model="form.basic_salary" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.social_insurance_base')"><el-input-number v-model="form.social_insurance_base" :min="0" :precision="2" style="width:100%" /></el-form-item>
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
