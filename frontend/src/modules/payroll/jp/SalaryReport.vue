<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

// ── Calculation Execution ──
const calcRunning = ref(false)
const calcResult = ref<any>(null)
const calcMonth = ref(new Date().toISOString().slice(0, 7))
const calcEntity = ref('')
const calcNotes = ref('')
const entities = ref<any[]>([])

// ── Report Table ──
const loading = ref(false)
const records = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const pages = ref(1)
const sortBy = ref('calculated_at')
const sortDir = ref<'asc' | 'desc'>('desc')
const searchQuery = ref('')
const filters = reactive({
  payroll_month: '',
  entity: '',
  status: '',
})

const statusOptions = [
  { value: 'completed', label: 'payroll.jp.status_confirmed' },
  { value: 'calculated', label: 'payroll.jp.status_calculated' },
  { value: 'draft', label: 'payroll.jp.status_draft' },
  { value: 'voided', label: 'payroll.jp.status_voided' },
]

let searchTimer: any = null

// ── Computed ──
const visiblePages = computed(() => {
  const pgs: (number | string)[] = []
  const totalPages = pages.value
  if (totalPages <= 7) { for (let i = 1; i <= totalPages; i++) pgs.push(i); return pgs }
  pgs.push(1)
  if (page.value > 3) pgs.push('...')
  const start = Math.max(2, page.value - 1)
  const end = Math.min(totalPages - 1, page.value + 1)
  for (let i = start; i <= end; i++) pgs.push(i)
  if (page.value < totalPages - 2) pgs.push('...')
  pgs.push(totalPages)
  return pgs
})

const statusBadgeTypes: Record<string, string> = {
  completed: 'success',
  calculated: 'warning',
  draft: '',
  voided: 'danger',
  running: 'warning',
  failed: 'danger',
}

const statusLabels: Record<string, string> = {
  completed: 'payroll.jp.status_confirmed',
  calculated: 'payroll.jp.status_calculated',
  draft: 'payroll.jp.status_draft',
  voided: 'payroll.jp.status_voided',
  running: 'app.loading',
  failed: 'error.load_failed',
}

// ── Methods ──
function entityLabel(entityId: string) {
  const found = entities.value.find((e: any) => e.entity_id === entityId)
  if (!found) return entityId
  return `${found.entity_code || found.entity_id} - ${found.entity_name || ''} (${found.country || ''})`
}

async function executeCalculation() {
  calcRunning.value = true
  calcResult.value = null
  try {
    // Use the monthly sheet creation + calculation flow
    const res = await payrollJpApi.createBatch({
      payroll_month: calcMonth.value,
      entity_id: calcEntity.value || undefined,
      notes: calcNotes.value || undefined,
    })
    const sheetData = res.data.data || res.data || {}
    const sheetId = sheetData.sheet_id || sheetData.batch_id

    if (sheetId) {
      // Auto-calculate after creation
      await payrollJpApi.calculateBatch(sheetId)
    }

    calcResult.value = {
      success: true,
      sheet_id: sheetId,
      payroll_month: calcMonth.value,
      entity: calcEntity.value,
      calculated_at: new Date().toISOString(),
    }
    ElMessage.success(t('payroll.jp.calculated'))
  } catch (e: any) {
    calcResult.value = {
      success: false,
      error: e.message || 'Calculation failed',
      calculated_at: new Date().toISOString(),
    }
    ElMessage.error(e.message)
  } finally {
    calcRunning.value = false
    loadRecords()
  }
}

function formatDateTime(isoStr: string) {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('sv-SE').replace('T', ' ')
  } catch { return isoStr.replace('T', ' ').substring(0, 19) }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadRecords() }, 350)
}

function applyFilters() { page.value = 1; loadRecords() }

function clearFilters() {
  filters.payroll_month = ''
  filters.entity = ''
  filters.status = ''
  searchQuery.value = ''
  page.value = 1
  loadRecords()
}

function onPerPageChange() { page.value = 1; loadRecords() }

function goToPage(p: number) {
  if (p < 1 || p > pages.value) return
  page.value = p
  loadRecords()
}

function toggleSort(field: string) {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortDir.value = 'asc'
  }
  loadRecords()
}

function sortIcon(field: string) {
  if (sortBy.value !== field) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

async function loadRecords() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_dir: sortDir.value,
    }
    if (filters.payroll_month) params.payroll_month = filters.payroll_month
    if (filters.entity) params.entity_id = filters.entity
    if (filters.status) params.status = filters.status
    if (searchQuery.value) params.q = searchQuery.value

    const res = await payrollJpApi.sheets(params)
    const data = res.data.data || res.data || {}
    records.value = data.items || data || []
    total.value = data.total || records.value.length
    pages.value = data.pages || Math.ceil(total.value / pageSize.value) || 1
  } catch (e: any) {
    ElMessage.error(e.message)
    records.value = []
    total.value = 0
    pages.value = 1
  } finally { loading.value = false }
}

async function loadEntities() {
  try {
    const res = await fetch('/api/masterdata/entities').then(r => r.json())
    entities.value = res.data || []
  } catch (_) {}
}

onMounted(() => { loadEntities(); loadRecords() })
</script>

<template>
  <div class="report-page">
    <!-- ═══════ Section 1: Calculation Execution ═══════ -->
    <div class="section-card">
      <h2 class="section-title">⚡ {{ t('payroll.jp.calculate') }}</h2>
      <div class="calc-form">
        <div class="calc-field">
          <label>{{ t('field.payroll_month') }}</label>
          <el-input v-model="calcMonth" placeholder="2026-07" style="width:200px" />
        </div>
        <div class="calc-field">
          <label>{{ t('field.entity_id') }}</label>
          <el-select v-model="calcEntity" placeholder="All Entities" clearable style="width:260px">
            <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
          </el-select>
        </div>
        <div class="calc-field" style="align-self:flex-end">
          <el-button type="primary" :loading="calcRunning" @click="executeCalculation">
            <template v-if="calcRunning">{{ t('app.loading') }}...</template>
            <template v-else>⚡ {{ t('payroll.jp.calculate') }}</template>
          </el-button>
        </div>
      </div>

      <!-- Calc Result -->
      <div v-if="calcResult" class="calc-result" :class="calcResult.success ? 'result-success' : 'result-error'">
        <strong>{{ calcResult.success ? '✅' : '⚠️' }} {{ calcResult.success ? t('payroll.jp.calculated') : t('error.load_failed') }}</strong>
        <div class="result-meta">
          {{ t('field.payroll_month') }}: {{ calcResult.payroll_month || calcMonth }}
          <template v-if="calcResult.sheet_id">· Sheet: {{ calcResult.sheet_id }}</template>
          · {{ formatDateTime(calcResult.calculated_at) }}
        </div>
        <div v-if="calcResult.error" class="result-error-text">{{ calcResult.error }}</div>
      </div>
    </div>

    <!-- ═══════ Section 2: Historical Report ═══════ -->
    <div class="section-card">
      <h2 class="section-title">📊 {{ t('payroll.jp.calculation_summary') }}</h2>

      <!-- Filters -->
      <div class="filter-form">
        <div class="form-grid">
          <div class="form-field">
            <label>{{ t('field.payroll_month') }}</label>
            <el-input v-model="filters.payroll_month" placeholder="2026-07" clearable @change="applyFilters" style="width:100%" />
          </div>
          <div class="form-field">
            <label>{{ t('field.entity_id') }}</label>
            <el-select v-model="filters.entity" clearable style="width:100%" @change="applyFilters">
              <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
            </el-select>
          </div>
          <div class="form-field">
            <label>{{ t('field.status') }}</label>
            <el-select v-model="filters.status" clearable style="width:100%" @change="applyFilters">
              <el-option v-for="s in statusOptions" :key="s.value" :label="t(s.label)" :value="s.value" />
            </el-select>
          </div>
          <div class="form-field">
            <label>{{ t('action.search') }}</label>
            <el-input v-model="searchQuery" :placeholder="t('action.search')" clearable style="width:100%" @input="onSearchInput" />
          </div>
          <div class="form-field actions">
            <el-button type="primary" size="small" @click="applyFilters">{{ t('action.search') }}</el-button>
            <el-button size="small" @click="clearFilters">{{ t('action.clear') }}</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ Report Table ═══════ -->
    <div class="table-card">
      <!-- Toolbar -->
      <div class="table-toolbar">
        <div class="row-count">{{ t('action.showing_records', { shown: records.length, total: total }) }}</div>
        <div class="page-size">
          <label>{{ t('employee.list.per_page') }}</label>
          <el-select v-model="pageSize" style="width:80px" @change="onPerPageChange">
            <el-option :value="10" label="10" />
            <el-option :value="20" label="20" />
            <el-option :value="50" label="50" />
            <el-option :value="100" label="100" />
          </el-select>
        </div>
      </div>

      <el-table :data="records" v-loading="loading" border stripe size="small">
        <el-table-column :label="t('field.sheet_id')" min-width="220" show-overflow-tooltip>
          <template #default="{row}">{{ row.sheet_id || row.batch_id || '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.payroll_month')" width="110" prop="payroll_month" />
        <el-table-column :label="t('field.entity_id')" width="250" show-overflow-tooltip>
          <template #default="{row}">{{ entityLabel(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.employee_count')" width="80" align="center">
          <template #default="{row}">{{ row.employee_count ?? '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.gross_total')" width="130" align="right" sortable="custom">
          <template #default="{row}">{{ row.gross_total ? '¥' + Number(row.gross_total).toLocaleString() : '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.net_total')" width="130" align="right" sortable="custom">
          <template #default="{row}">{{ row.net_total ? '¥' + Number(row.net_total).toLocaleString() : '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.status')" width="110">
          <template #default="{row}">
            <el-tag :type="(statusBadgeTypes[row.status] || '') as any" size="small">
              {{ t(statusLabels[row.status] || row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div v-if="total > pageSize" class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          small
          @current-change="loadRecords"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-page { max-width: 1500px; margin: 0 auto; padding: 24px; font-size: 15px; }

.section-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 22px; margin-bottom: 18px; }
.section-title { margin: 0 0 14px; font-size: 1.15rem; font-weight: 700; color: #1d2a3a; }

.calc-form { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-end; }
.calc-field { display: flex; flex-direction: column; gap: 4px; }
.calc-field label { font-size: .78rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: .03em; }
.calc-result { margin-top: 16px; padding: 14px 18px; border-radius: 10px; font-size: .9rem; }
.calc-result strong { display: block; margin-bottom: 4px; }
.result-meta { font-size: .8rem; color: #6b7280; }
.result-success { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; }
.result-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.result-error-text { font-size: .78rem; margin-top: 4px; }

.filter-form { margin-bottom: 0; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px 16px; align-items: end; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: .75rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: .03em; }
.form-field.actions { flex-direction: row; gap: 6px; }

.table-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
.table-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid #e5e7eb; background: #f9fafb; }
.row-count { font-size: .85rem; font-weight: 700; color: #1d2a3a; }
.page-size { display: flex; align-items: center; gap: 8px; font-size: .85rem; color: #6b7280; }
.pagination-bar { display: flex; justify-content: center; padding: 12px; border-top: 1px solid #e5e7eb; }

@media (max-width: 760px) { .calc-form { flex-direction: column; align-items: stretch; } .form-grid { grid-template-columns: 1fr; } }
</style>
