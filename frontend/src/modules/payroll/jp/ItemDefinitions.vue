<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const loading = ref(false)
const items = ref<any[]>([])
const dialogVisible = ref(false)
const form = ref<Record<string, any>>({})
const saving = ref(false)

const categoryLabels: Record<string, string> = { earning: '支給 (Earning)', deduction: '控除 (Deduction)', employer_cost: '会社負担 (Employer Cost)' }
const subCategoryLabels: Record<string, string> = { base: '基本', overtime: '残業', allowance: '手当', manual: '手動入力', statutory: '法定', attendance: '勤怠' }
const categories = ['earning', 'deduction', 'employer_cost']

function getLabel(row: any, lang: string): string { try { const labels = typeof row.labels === 'string' ? JSON.parse(row.labels) : row.labels; return labels?.[lang] || labels?.ja || row.code || '-' } catch { return row.code || '-' } }

async function load() { loading.value = true; try { const res = await payrollJpApi.itemDefinitions(); items.value = res.data.data?.items || res.data.data || [] } catch (e: any) { ElMessage.error(e.message) } finally { loading.value = false } }
function openEdit(row: any) { form.value = { ...row }; dialogVisible.value = true }
async function save() { saving.value = true; try { await payrollJpApi.saveItemDefinition(form.value); dialogVisible.value = false; ElMessage.success(t('action.saved')); await load() } catch (e: any) { ElMessage.error(e.message) } finally { saving.value = false } }
onMounted(load)
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.item_definitions') }}</h2>
        <span class="count-chip">{{ items.length }} {{ t('action.records_total') }}</span>
      </div>
      <el-tooltip content="工资项目暂由系统预定义，后续版本开放" placement="left">
        <el-button type="primary" disabled>{{ t('action.create') }}</el-button>
      </el-tooltip>
    </div>
    <div class="fiori-card">
      <el-table :data="items" v-loading="loading" border stripe size="small">
        <el-table-column prop="display_order" label="#" width="45" align="center" />
        <el-table-column prop="code" :label="t('field.code')" width="130" />
        <el-table-column label="日本語" min-width="160" show-overflow-tooltip>
          <template #default="{row}">{{ getLabel(row, 'ja') }}</template>
        </el-table-column>
        <el-table-column label="English" min-width="180" show-overflow-tooltip>
          <template #default="{row}">{{ getLabel(row, 'en') }}</template>
        </el-table-column>
        <el-table-column label="中文" min-width="140" show-overflow-tooltip>
          <template #default="{row}">{{ getLabel(row, 'zh') }}</template>
        </el-table-column>
        <el-table-column :label="t('field.category')" width="150">
          <template #default="{row}">
            <el-tag size="small" :type="row.category==='earning'?'success':row.category==='deduction'?'danger':'warning'">{{ categoryLabels[row.category] || row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('field.sub_category')" width="110">
          <template #default="{row}"><span class="muted-text">{{ subCategoryLabels[row.sub_category] || row.sub_category }}</span></template>
        </el-table-column>
        <el-table-column :label="t('field.taxable')" width="70" align="center">
          <template #default="{row}"><el-tag :type="row.taxable?'warning':'info'" size="small">{{ row.taxable?t('field.yes'):t('field.no') }}</el-tag></template>
        </el-table-column>
        <el-table-column label="SI" width="55" align="center">
          <template #default="{row}"><span class="dot" :class="row.social_insurance_base?'dot-on':'dot-off'" /></template>
        </el-table-column>
        <el-table-column label="EI" width="55" align="center">
          <template #default="{row}"><span class="dot" :class="row.employment_insurance_base?'dot-on':'dot-off'" /></template>
        </el-table-column>
        <el-table-column :label="t('field.payslip_visible')" width="70" align="center">
          <template #default="{row}"><el-tag :type="row.payslip_visible?'success':'info'" size="small">{{ row.payslip_visible?t('field.yes'):t('field.no') }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="70" fixed="right">
          <template #default="{row}"><el-button size="small" text type="primary" @click="openEdit(row)">{{ t('action.edit') }}</el-button></template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="t('action.edit')" width="560px">
      <el-form :model="form" label-width="150px">
        <el-form-item :label="t('field.item_id')"><el-input v-model="form.item_id" disabled /></el-form-item>
        <el-form-item :label="t('field.code')"><el-input v-model="form.code" disabled /></el-form-item>
        <el-descriptions :column="1" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="日本語">{{ getLabel(form, 'ja') }}</el-descriptions-item>
          <el-descriptions-item label="English">{{ getLabel(form, 'en') }}</el-descriptions-item>
          <el-descriptions-item label="中文">{{ getLabel(form, 'zh') }}</el-descriptions-item>
        </el-descriptions>
        <el-form-item :label="t('field.taxable')"><el-switch v-model="form.taxable" /></el-form-item>
        <el-form-item label="社会保険算定基礎"><el-switch v-model="form.social_insurance_base" /></el-form-item>
        <el-form-item label="雇用保険算定基礎"><el-switch v-model="form.employment_insurance_base" /></el-form-item>
        <el-form-item :label="t('field.payslip_visible')"><el-switch v-model="form.payslip_visible" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">{{ t('action.cancel') }}</el-button><el-button type="primary" :loading="saving" @click="save">{{ t('action.save') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width:1500px; margin:0 auto; padding:24px; font-size:15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.count-chip { background:#e8f0fe; color:#1B6CB2; padding:2px 12px; border-radius:12px; font-size:.82rem; font-weight:600; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%; }
.dot-on { background:#10b981; }
.dot-off { background:#d1d5db; }
.muted-text { color:#6b7280; font-size:.85rem; }
</style>
