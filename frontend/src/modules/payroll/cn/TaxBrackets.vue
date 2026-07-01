<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollCnApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const brackets = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ effective_year: 2026, status: 'active' })

async function load() {
  loading.value = true
  try {
    const res = await payrollCnApi.taxBrackets()
    brackets.value = res.data.data?.items || []
    total.value = brackets.value.length
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  form.value = row ? { ...row } : { effective_year: 2026, status: 'active' }
  dialogVisible.value = true
}

async function save() {
  try { await payrollCnApi.saveTaxBracket(form.value); dialogVisible.value = false; ElMessage.success(t('action.saved')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.cn.tax_brackets') }}</h3>
      <el-button type="primary" @click="openDialog()">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="brackets" v-loading="loading" border stripe>
      <el-table-column prop="effective_year" :label="t('field.effective_year')" />
      <el-table-column prop="min_income" :label="t('field.min_income')" />
      <el-table-column prop="max_income" :label="t('field.max_income')" />
      <el-table-column prop="tax_rate" :label="t('field.tax_rate')" />
      <el-table-column prop="quick_deduction" :label="t('field.quick_deduction')" />
      <el-table-column :label="t('action.actions')" width="120">
        <template #default="{ row }"><el-button size="small" text @click="openDialog(row)">{{ t('action.edit') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('payroll.cn.tax_brackets')" width="450px">
      <el-form :model="form" label-width="140px">
        <el-form-item :label="t('field.effective_year')"><el-input-number v-model="form.effective_year" :min="2020" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.min_income')"><el-input-number v-model="form.min_income" :min="0" :precision="0" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.max_income')"><el-input-number v-model="form.max_income" :min="0" :precision="0" style="width:100%" /></el-form-item>
        <el-form-item :label="t('field.tax_rate')"><el-input v-model="form.tax_rate" placeholder="0.03" /></el-form-item>
        <el-form-item :label="t('field.quick_deduction')"><el-input-number v-model="form.quick_deduction" :min="0" :precision="0" style="width:100%" /></el-form-item>
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
