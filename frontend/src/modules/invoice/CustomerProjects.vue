<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { invoiceApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const projects = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({ default_currency: 'JPY', default_tax_rate: '10%', payment_terms_days: 30, active: true })

async function load() {
  loading.value = true
  try { const res = await invoiceApi.projects(); projects.value = res.data.data?.items || []; total.value = projects.value.length } finally { loading.value = false }
}

function openDialog(row?: any) {
  form.value = row ? { ...row } : { default_currency: 'JPY', default_tax_rate: '10%', payment_terms_days: 30, active: true }
  dialogVisible.value = true
}

async function save() {
  try { await invoiceApi.saveProject(form.value); dialogVisible.value = false; ElMessage.success(t('action.saved')); load() } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('invoice.projects') }}</h3>
      <el-button type="primary" @click="openDialog()">{{ t('action.create') }}</el-button>
    </div>
    <el-table :data="projects" v-loading="loading" border stripe>
      <el-table-column prop="project_code" :label="t('field.project_code')" />
      <el-table-column prop="project_name" :label="t('field.project_name')" />
      <el-table-column prop="customer_name" :label="t('field.customer_name')" />
      <el-table-column prop="main_recipient_email" :label="t('field.main_recipient_email')" />
      <el-table-column prop="default_currency" :label="t('field.currency')" />
      <el-table-column prop="active" :label="t('field.active')">
        <template #default="{ row }"><el-tag :type="row.active ? 'success' : 'info'" size="small">{{ row.active ? 'Active' : 'Inactive' }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120" fixed="right">
        <template #default="{ row }"><el-button size="small" text @click="openDialog(row)">{{ t('action.edit') }}</el-button></template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ total }} {{ t('action.records_total') }}</div>

    <el-dialog v-model="dialogVisible" :title="t('invoice.projects')" width="600px">
      <el-form :model="form" label-width="150px">
        <el-form-item :label="t('field.project_id')"><el-input v-model="form.project_id" /></el-form-item>
        <el-form-item :label="t('field.project_code')"><el-input v-model="form.project_code" /></el-form-item>
        <el-form-item :label="t('field.project_name')"><el-input v-model="form.project_name" /></el-form-item>
        <el-form-item :label="t('field.customer_name')"><el-input v-model="form.customer_name" /></el-form-item>
        <el-form-item :label="t('field.main_recipient_name')"><el-input v-model="form.main_recipient_name" /></el-form-item>
        <el-form-item :label="t('field.main_recipient_email')"><el-input v-model="form.main_recipient_email" /></el-form-item>
        <el-form-item :label="t('field.default_currency')"><el-input v-model="form.default_currency" /></el-form-item>
        <el-form-item :label="t('field.default_tax_rate')"><el-input v-model="form.default_tax_rate" /></el-form-item>
        <el-form-item :label="t('field.payment_terms_days')"><el-input-number v-model="form.payment_terms_days" :min="0" style="width:100%" /></el-form-item>
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
