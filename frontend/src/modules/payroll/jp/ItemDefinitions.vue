<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ category: '', code: '', taxable: true, payslip_visible: true })

async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.itemDefinitions()
    items.value = res.data.data?.items || []
    total.value = items.value.length
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  form.value = row ? { ...row } : { item_id: '', category: '', code: '', taxable: true, payslip_visible: true }
  dialogVisible.value = true
}

async function save() {
  try {
    await payrollJpApi.saveItemDefinition(form.value)
    dialogVisible.value = false
    ElMessage.success(t('action.saved'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.jp.item_definitions') }}</h3>
      <el-button type="primary" @click="openDialog()">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column prop="code" :label="t('field.code')" />
      <el-table-column prop="category" :label="t('field.category')" />
      <el-table-column prop="sub_category" :label="t('field.sub_category')" />
      <el-table-column prop="taxable" :label="t('field.taxable')">
        <template #default="{ row }"><el-tag :type="row.taxable ? 'warning' : 'info'" size="small">{{ row.taxable ? 'Yes' : 'No' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="payslip_visible" :label="t('field.payslip_visible')">
        <template #default="{ row }"><el-tag :type="row.payslip_visible ? 'success' : 'info'" size="small">{{ row.payslip_visible ? 'Yes' : 'No' }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120">
        <template #default="{ row }"><el-button size="small" text @click="openDialog(row)">{{ t('action.edit') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('payroll.jp.item_definitions')" width="500px">
      <el-form :model="form" label-width="140px">
        <el-form-item :label="t('field.item_id')"><el-input v-model="form.item_id" /></el-form-item>
        <el-form-item :label="t('field.code')"><el-input v-model="form.code" /></el-form-item>
        <el-form-item :label="t('field.category')"><el-input v-model="form.category" /></el-form-item>
        <el-form-item :label="t('field.sub_category')"><el-input v-model="form.sub_category" /></el-form-item>
        <el-form-item :label="t('field.taxable')"><el-switch v-model="form.taxable" /></el-form-item>
        <el-form-item :label="t('field.payslip_visible')"><el-switch v-model="form.payslip_visible" /></el-form-item>
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
