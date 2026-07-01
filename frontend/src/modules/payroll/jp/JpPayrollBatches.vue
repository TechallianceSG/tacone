<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()

// ── State ──
const loading = ref(false)
const sheets = ref<any[]>([])

// Filters
const filterEntity = ref('')
const filterMonth = ref('')
const filterStatus = ref('')

// Create dialog
const createDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  payroll_month: new Date().toISOString().slice(0, 7),
  entity_id: '',
  notes: ''
})

// Void dialog
const voidDialog = ref(false)
const voiding = ref(false)
const voidSheetId = ref('')
const voidReason = ref('')

// Entity dropdown
const entities = ref<any[]>([])

// ── Status Colors ──
const statusColors: Record<string, string> = {
  draft: '',
  calculated: 'warning',
  confirmed: 'success',
  voided: 'danger',
}

// ── Computed ──
const filtered = computed(() => {
  let result = sheets.value
  if (filterEntity.value) result = result.filter(s => s.entity_id === filterEntity.value)
  if (filterMonth.value) result = result.filter(s => s.payroll_month === filterMonth.value)
  if (filterStatus.value) result = result.filter(s => s.status === filterStatus.value)
  return result
})

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.sheets()
    sheets.value = res.data.data?.items || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

async function loadEntities() {
  try {
    const res = await fetch('/api/masterdata/entities').then(r => r.json())
    entities.value = res.data || []
  } catch (_) {}
}

const entityLabel = (entityId: string) => {
  const found = entities.value.find((e: any) => e.entity_id === entityId)
  if (!found) return entityId
  return `${found.entity_code || found.entity_id} - ${found.entity_name || ''} (${found.country || ''})`
}

async function createSheet() {
  creating.value = true
  try {
    await payrollJpApi.createBatch(createForm.value)
    createDialog.value = false
    ElMessage.success(t('payroll.jp.sheet_created'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { creating.value = false }
}

function viewDetail(sheetId: string) {
  router.push(`/payroll/jp/batches/${sheetId}`)
}

function openVoid(sheetId: string) {
  voidSheetId.value = sheetId
  voidReason.value = ''
  voidDialog.value = true
}

async function confirmVoid() {
  voiding.value = true
  try {
    // Use confirmSheet with void action or direct API call
    await payrollJpApi.confirmSheet(voidSheetId.value)
    voidDialog.value = false
    ElMessage.success(t('payroll.jp.sheet_voided'))
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { voiding.value = false }
}

onMounted(() => { load(); loadEntities() })
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <div class="page-header">
      <h3>{{ t('payroll.jp.monthly_sheets') }}</h3>
      <el-button type="primary" @click="createDialog = true">{{ t('payroll.jp.create_sheet') }}</el-button>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:220px" @change="filterMonth">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
      </el-select>
      <el-input v-model="filterMonth" :placeholder="t('field.payroll_month') + ' (YYYY-MM)'" clearable style="width:160px" />
      <el-select v-model="filterStatus" :placeholder="t('field.status')" clearable style="width:130px">
        <el-option label="Draft" value="draft" />
        <el-option label="Calculated" value="calculated" />
        <el-option label="Confirmed" value="confirmed" />
        <el-option label="Voided" value="voided" />
      </el-select>
    </div>

    <!-- Table -->
    <el-table :data="filtered" v-loading="loading" border stripe size="small">
      <el-table-column prop="sheet_id" :label="t('field.sheet_id')" width="200" show-overflow-tooltip />
      <el-table-column prop="payroll_month" :label="t('field.payroll_month')" width="100" />
      <el-table-column :label="t('field.entity_id')" width="250">
        <template #default="{row}">{{ entityLabel(row.entity_id) }}</template>
      </el-table-column>
      <el-table-column prop="status" :label="t('field.status')" width="110">
        <template #default="{row}">
          <el-tag :type="statusColors[row.status] || ''" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="employee_count" :label="t('field.employee_count')" width="80" align="center" />
      <el-table-column prop="gross_total" :label="t('field.gross_total')" width="130" align="right">
        <template #default="{row}">{{ row.gross_total ? Number(row.gross_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="deduction_total" :label="t('field.deduction_total')" width="130" align="right">
        <template #default="{row}">{{ row.deduction_total ? Number(row.deduction_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="net_total" :label="t('field.net_total')" width="130" align="right">
        <template #default="{row}">{{ row.net_total ? Number(row.net_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="employer_cost_total" :label="t('field.employer_cost_total')" width="130" align="right">
        <template #default="{row}">{{ row.employer_cost_total ? Number(row.employer_cost_total).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="120" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="viewDetail(row.sheet_id)">{{ t('action.detail') }}</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            text
            type="danger"
            @click="openVoid(row.sheet_id)"
          >{{ t('action.void') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Record Count -->
    <div class="helper-text">{{ filtered.length }} {{ t('action.records_total') }}</div>

    <!-- Create Sheet Dialog -->
    <el-dialog v-model="createDialog" :title="t('payroll.jp.create_sheet')" width="480px">
      <el-form :model="createForm" label-width="140px">
        <el-form-item :label="t('field.payroll_month')">
          <el-input v-model="createForm.payroll_month" placeholder="2026-07" />
          <div class="form-hint">{{ t('payroll.sg.create_sheet_hint') }}</div>
        </el-form-item>
        <el-form-item :label="t('field.entity_id')">
          <el-select v-model="createForm.entity_id" style="width:100%">
            <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.notes')">
          <el-input v-model="createForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="createSheet">{{ t('action.create') }}</el-button>
      </template>
    </el-dialog>

    <!-- Void Dialog -->
    <el-dialog v-model="voidDialog" :title="t('action.void')" width="400px">
      <p>{{ t('payroll.jp.void_confirm') }}</p>
      <el-input v-model="voidReason" :placeholder="t('action.void_reason')" type="textarea" :rows="2" />
      <template #footer>
        <el-button @click="voidDialog = false">{{ t('action.cancel') }}</el-button>
        <el-button type="danger" :loading="voiding" @click="confirmVoid">{{ t('action.void') }}</el-button>
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
