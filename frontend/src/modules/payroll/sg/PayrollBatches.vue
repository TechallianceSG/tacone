<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollSgApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const sheets = ref<any[]>([])
const filterEntity = ref('')
const filterMonth = ref('')
const filterStatus = ref('')

// Create dialog
const createDialog = ref(false)
const creating = ref(false)
const createForm = ref({ payroll_month: new Date().toISOString().slice(0, 7), entity_id: '', notes: '' })

const statusColors: Record<string, string> = {
  draft: '', hr_confirmed: 'info', calculated: 'warning',
  hr_reviewed: '', manager_review: 'warning', finalized: 'success', voided: 'danger'
}

async function load() {
  loading.value = true
  try {
    const res = await payrollSgApi.sheets()
    sheets.value = res.data.data?.items || []
  } finally { loading.value = false }
}

const filtered = computed(() => {
  let result = sheets.value
  if (filterEntity.value) result = result.filter(s => s.entity_id === filterEntity.value)
  if (filterMonth.value) result = result.filter(s => s.payroll_month === filterMonth.value)
  if (filterStatus.value) result = result.filter(s => s.status === filterStatus.value)
  return result
})

async function createSheet() {
  creating.value = true
  try {
    // Create sheet via the batch endpoint (which creates a monthly sheet)
    await payrollSgApi.createBatch(createForm.value)
    createDialog.value = false
    ElMessage.success(t('payroll.sg.sheet_created'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { creating.value = false }
}

function viewDetail(sheetId: string) {
  router.push(`/payroll/sg/batches/${sheetId}`)
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.sg.monthly_sheets') }}</h3>
      <el-button type="primary" @click="createDialog = true">{{ t('payroll.sg.create_sheet') }}</el-button>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <el-input v-model="filterMonth" :placeholder="t('field.payroll_month') + ' (YYYY-MM)'" clearable style="width:160px" />
      <el-input v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:140px" />
      <el-select v-model="filterStatus" :placeholder="t('field.status')" clearable style="width:130px">
        <el-option label="Draft" value="draft" /><el-option label="HR Confirmed" value="hr_confirmed" />
        <el-option label="Calculated" value="calculated" /><el-option label="HR Reviewed" value="hr_reviewed" />
        <el-option label="Manager Review" value="manager_review" /><el-option label="Finalized" value="finalized" />
      </el-select>
    </div>

    <el-table :data="filtered" v-loading="loading" border stripe size="small">
      <el-table-column prop="sheet_id" :label="t('field.sheet_id')" width="200" show-overflow-tooltip />
      <el-table-column prop="payroll_month" :label="t('field.payroll_month')" width="100" />
      <el-table-column prop="entity_id" :label="t('field.entity_id')" width="120" />
      <el-table-column prop="status" :label="t('field.status')" width="130">
        <template #default="{row}"><el-tag :type="statusColors[row.status] || ''" size="small">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="employee_count" :label="t('field.employee_count')" width="100" align="center" />
      <el-table-column prop="gross_total" :label="t('field.gross_total')" width="130" align="right">
        <template #default="{row}">{{ row.gross_total ? Number(row.gross_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="net_total" :label="t('field.net_total')" width="130" align="right">
        <template #default="{row}">{{ row.net_total ? Number(row.net_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_by" :label="t('field.created_by')" width="120" />
      <el-table-column :label="t('action.actions')" width="100" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="viewDetail(row.sheet_id)">{{ t('action.detail') }}</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="helper-text">{{ filtered.length }} {{ t('action.records_total') }}</div>

    <!-- Create Sheet Dialog -->
    <el-dialog v-model="createDialog" :title="t('payroll.sg.create_sheet')" width="420px">
      <el-form :model="createForm" label-width="130px">
        <el-form-item :label="t('field.payroll_month')">
          <el-input v-model="createForm.payroll_month" placeholder="2026-07" />
          <div class="form-hint">{{ t('payroll.sg.create_sheet_hint') }}</div>
        </el-form-item>
        <el-form-item :label="t('field.entity_id')"><el-input v-model="createForm.entity_id" placeholder="ENT-0002" /></el-form-item>
        <el-form-item :label="t('field.notes')"><el-input v-model="createForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="createSheet">{{ t('action.create') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.helper-text { margin-top: 8px; color: var(--el-text-color-secondary); font-size: 0.85rem; }
.form-hint { font-size: 0.78rem; color: var(--el-text-color-secondary); margin-top: 4px; }
</style>
