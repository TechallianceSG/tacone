<template>
  <div class="salary-report">
    <!-- ===== Section 1: 給与計算実行 ===== -->
    <div class="card">
      <h2 style="margin: 0 0 16px; color: var(--navy); font-size: 18px">
        ⚡ {{ t('calc.title') }}
      </h2>
      <div class="calc-form">
        <div class="calc-field">
          <label for="calc-month">{{ t('calc.payroll_month') }}</label>
          <input
            id="calc-month"
            type="month"
            v-model="calcForm.payrollMonth"
            style="max-width: 240px"
          />
        </div>
        <div class="calc-field">
          <label for="calc-entity">{{ t('field.entity') }}</label>
          <select id="calc-entity" v-model="calcForm.entity" style="max-width: 240px">
            <option value="">{{ t('filter.all') }}</option>
            <option v-for="e in entityOptions" :key="e" :value="e">{{ e }}</option>
          </select>
        </div>
        <div class="calc-field" style="align-self: flex-end">
          <button class="btn" :disabled="calcRunning" @click="executeCalculation">
            <template v-if="calcRunning">⏳ {{ t('calc.running') }}</template>
            <template v-else>⚡ {{ t('calc.execute') }}</template>
          </button>
        </div>
      </div>

      <!-- Calculation Result Message -->
      <div v-if="calcResult" :class="['message-strip', calcResult.success ? 'message-success' : 'message-warning']" style="margin-top: 14px">
        <strong>{{ calcResult.success ? '✅' : '⚠️' }} {{ calcResult.success ? t('calc.success') : t('calc.failed') }}</strong>
        <div style="font-size: 12px; margin-top: 4px">
          {{ t('calc.calc_time') }}: {{ calcResult.calculated_at || '—' }}
          <template v-if="calcResult.summary">
            · {{ t('calc.employees') }}: {{ calcResult.summary.employee_count || 0 }}
            · {{ t('calc.total_gross') }}: {{ fmt(calcResult.summary.total_gross || 0) }}
            · {{ t('calc.total_net') }}: {{ fmt(calcResult.summary.total_net || 0) }}
          </template>
        </div>
        <div v-if="!calcResult.success && calcResult.error" style="font-size: 12px; color: var(--red); margin-top: 4px">
          {{ calcResult.error }}
        </div>
      </div>
    </div>

    <!-- ===== Section 2: 工资明细报表 ===== -->
    <div class="card">
      <h2 style="margin: 0 0 16px; color: var(--navy); font-size: 18px">
        📊 {{ t('report.title') }}
      </h2>

      <!-- Filter Bar -->
      <form class="filter-form" @submit.prevent="applyFilters">
        <div class="form-grid">
          <div class="form-field">
            <label for="filter-month">{{ t('field.payroll_month') }}</label>
            <input id="filter-month" type="month" v-model="filters.payroll_month" @change="applyFilters" />
          </div>
          <div class="form-field">
            <label for="filter-entity">{{ t('field.entity') }}</label>
            <select id="filter-entity" v-model="filters.entity" @change="applyFilters">
              <option value="">{{ t('filter.all') }}</option>
              <option v-for="e in entityOptions" :key="e" :value="e">{{ e }}</option>
            </select>
          </div>
          <div class="form-field">
            <label for="filter-dept">{{ t('field.department') }}</label>
            <select id="filter-dept" v-model="filters.department" @change="applyFilters">
              <option value="">{{ t('filter.all') }}</option>
              <option v-for="d in departmentOptions" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="form-field">
            <label for="filter-status">{{ t('field.status') }}</label>
            <select id="filter-status" v-model="filters.status" @change="applyFilters">
              <option value="">{{ t('filter.all') }}</option>
              <option v-for="s in statusOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div class="form-field">
            <label for="filter-search">{{ t('action.search') }}</label>
            <input
              id="filter-search"
              v-model="searchQuery"
              type="text"
              :placeholder="t('report.search_placeholder')"
              @input="onSearchInput"
            />
          </div>
          <div class="form-field actions" style="align-self: flex-end">
            <button type="submit">{{ t('action.filter') }}</button>
            <button type="button" class="btn btn-secondary" @click="clearFilters">{{ t('action.clear') }}</button>
          </div>
        </div>
      </form>
    </div>

    <!-- Report Table Card -->
    <div class="card table-card">
      <!-- Toolbar -->
      <div class="table-toolbar">
        <div class="row-count">
          {{ t('report.total_records', { total: total }) }}
        </div>
        <div class="page-size">
          <label>{{ t('report.per_page') }}</label>
          <select v-model.number="perPage" @change="onPerPageChange">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('calculated_at')">
                {{ t('field.calc_datetime') }} <span class="sort-icon">{{ sortIcon('calculated_at') }}</span>
              </th>
              <th>{{ t('field.payroll_month') }}</th>
              <th>{{ t('field.entity') }}</th>
              <th class="sortable" @click="toggleSort('employee_count')">
                {{ t('field.employee_count') }} <span class="sort-icon">{{ sortIcon('employee_count') }}</span>
              </th>
              <th class="sortable" @click="toggleSort('total_gross')">
                {{ t('field.total_gross') }} <span class="sort-icon">{{ sortIcon('total_gross') }}</span>
              </th>
              <th class="sortable" @click="toggleSort('total_net')">
                {{ t('field.total_net') }} <span class="sort-icon">{{ sortIcon('total_net') }}</span>
              </th>
              <th>{{ t('field.status') }}</th>
              <th>{{ t('field.operator') }}</th>
              <th>{{ t('table.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="records.length === 0">
              <td colspan="9" class="empty-row">{{ t('report.empty') }}</td>
            </tr>
            <tr v-for="rec in records" :key="rec.id || rec.calculation_id">
              <td class="calc-time">{{ formatDateTime(rec.calculated_at) }}</td>
              <td>{{ rec.payroll_month || '—' }}</td>
              <td>{{ rec.entity_name || rec.entity || '—' }}</td>
              <td class="right">{{ rec.employee_count ?? '—' }}</td>
              <td class="right">{{ fmt(rec.total_gross) }}</td>
              <td class="right">{{ fmt(rec.total_net) }}</td>
              <td>
                <span :class="['badge', statusBadgeClass(rec.status)]">
                  {{ statusLabel(rec.status) }}
                </span>
              </td>
              <td>{{ rec.operator || '—' }}</td>
              <td class="actions-cell">
                <a v-if="rec.payslip_count" href="#" @click.prevent="viewDetail(rec)">
                  {{ t('action.view_details') }} ({{ rec.payslip_count }})
                </a>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="pages > 1" class="pagination">
        <button class="page-btn" :disabled="page <= 1" @click="goToPage(page - 1)">← {{ t('pagination.prev') }}</button>
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="page-ellipsis">…</span>
          <button v-else :class="['page-btn', { active: p === page }]" @click="goToPage(p)">{{ p }}</button>
        </template>
        <button class="page-btn" :disabled="page >= pages" @click="goToPage(page + 1)">{{ t('pagination.next') }} →</button>
      </div>
    </div>

    <!-- Loading overlay -->
    <div v-if="loading" class="card" style="text-align: center; padding: 32px">
      <p class="muted">⏳ {{ t('app.loading') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const lang = computed(() => route.query.lang || 'zh')
const loading = ref(false)

// ===== Translations =====
const translations = {
  zh: {
    'app.loading': '正在加载数据...',
    'calc.title': '給与計算実行 / Execute Salary Calculation',
    'calc.payroll_month': '计算月份',
    'calc.execute': '実行計算',
    'calc.running': '計算実行中...',
    'calc.success': '計算が完了しました',
    'calc.failed': '計算に失敗しました',
    'calc.calc_time': '計算時間',
    'calc.employees': '対象人数',
    'calc.total_gross': '支給総額',
    'calc.total_net': '差引総額',
    'report.title': '工资明细报表 / Salary Detail Report',
    'report.total_records': '共 {total} 条记录',
    'report.per_page': '每页',
    'report.empty': '暂无工资计算记录',
    'report.search_placeholder': '搜索计算批次、操作人...',
    'action.search': '搜索',
    'action.filter': '筛选',
    'action.clear': '清除',
    'action.view_details': '查看明细',
    'filter.all': '全部',
    'field.payroll_month': '工资月份',
    'field.calc_datetime': '计算日期时间',
    'field.entity': '法人实体',
    'field.department': '部门',
    'field.employee_count': '计算人数',
    'field.total_gross': '应发合计',
    'field.total_net': '实发合计',
    'field.status': '状态',
    'field.operator': '操作人',
    'table.actions': '操作',
    'pagination.prev': '上一页',
    'pagination.next': '下一页',
    'status.completed': '✅ 已完成',
    'status.running': '⏳ 执行中',
    'status.failed': '❌ 失败',
    'status.draft': '📝 草稿',
  },
  ja: {
    'app.loading': 'データ読み込み中...',
    'calc.title': '給与計算実行 / Execute Salary Calculation',
    'calc.payroll_month': '計算月',
    'calc.execute': '計算を実行',
    'calc.running': '計算実行中...',
    'calc.success': '計算が完了しました',
    'calc.failed': '計算に失敗しました',
    'calc.calc_time': '計算時刻',
    'calc.employees': '対象人数',
    'calc.total_gross': '支給総額',
    'calc.total_net': '差引総額',
    'report.title': '給与明細レポート / Salary Detail Report',
    'report.total_records': '合計 {total} 件',
    'report.per_page': '表示件数',
    'report.empty': '給与計算記録がありません',
    'report.search_placeholder': '計算バッチ、実行者で検索...',
    'action.search': '検索',
    'action.filter': '絞り込む',
    'action.clear': 'クリア',
    'action.view_details': '明細を見る',
    'filter.all': 'すべて',
    'field.payroll_month': '給与月',
    'field.calc_datetime': '計算日時',
    'field.entity': '法人',
    'field.department': '部署',
    'field.employee_count': '計算人数',
    'field.total_gross': '支給合計',
    'field.total_net': '差引合計',
    'field.status': 'ステータス',
    'field.operator': '実行者',
    'table.actions': '操作',
    'pagination.prev': '前へ',
    'pagination.next': '次へ',
    'status.completed': '✅ 完了',
    'status.running': '⏳ 実行中',
    'status.failed': '❌ 失敗',
    'status.draft': '📝 下書き',
  },
  en: {
    'app.loading': 'Loading data...',
    'calc.title': 'Execute Salary Calculation / 給与計算実行',
    'calc.payroll_month': 'Payroll Month',
    'calc.execute': 'Execute Calculation',
    'calc.running': 'Calculating...',
    'calc.success': 'Calculation completed successfully',
    'calc.failed': 'Calculation failed',
    'calc.calc_time': 'Calc Time',
    'calc.employees': 'Employees',
    'calc.total_gross': 'Total Gross',
    'calc.total_net': 'Total Net',
    'report.title': 'Salary Detail Report / 工资明细报表',
    'report.total_records': '{total} record(s) total',
    'report.per_page': 'Per page',
    'report.empty': 'No salary calculation records found',
    'report.search_placeholder': 'Search by batch, operator...',
    'action.search': 'Search',
    'action.filter': 'Filter',
    'action.clear': 'Clear',
    'action.view_details': 'View Details',
    'filter.all': 'All',
    'field.payroll_month': 'Payroll Month',
    'field.calc_datetime': 'Calc Date & Time',
    'field.entity': 'Entity',
    'field.department': 'Department',
    'field.employee_count': 'Employees',
    'field.total_gross': 'Total Gross',
    'field.total_net': 'Total Net',
    'field.status': 'Status',
    'field.operator': 'Operator',
    'table.actions': 'Actions',
    'pagination.prev': 'Prev',
    'pagination.next': 'Next',
    'status.completed': '✅ Completed',
    'status.running': '⏳ Running',
    'status.failed': '❌ Failed',
    'status.draft': '📝 Draft',
  },
}

function t(key, params = {}) {
  let text = translations[lang.value]?.[key] || translations.en[key] || key
  Object.entries(params).forEach(([k, v]) => { text = text.replace(`{${k}}`, v) })
  return text
}

function fmt(amount) {
  const num = typeof amount === 'number' ? amount : parseFloat(amount) || 0
  return `SGD ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDateTime(isoStr) {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`
  } catch {
    return isoStr.replace('T', ' ').substring(0, 19)
  }
}

function statusLabel(status) {
  const labels = {
    completed: t('status.completed'),
    running: t('status.running'),
    failed: t('status.failed'),
    draft: t('status.draft'),
  }
  return labels[status] || status || '—'
}

function statusBadgeClass(status) {
  const map = {
    completed: 'active',
    running: 'draft',
    failed: 'voided',
    draft: 'draft',
  }
  return map[status] || ''
}

// ===== Calculation Execution =====
const calcRunning = ref(false)
const calcResult = ref(null)
const calcForm = reactive({
  payrollMonth: new Date().toISOString().substring(0, 7),
  entity: '',
})

async function executeCalculation() {
  calcRunning.value = true
  calcResult.value = null
  try {
    const res = await fetch('/api/payroll/calculate', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        payroll_month: calcForm.payrollMonth,
        entity: calcForm.entity || undefined,
        lang: lang.value,
      }),
    })
    const json = await res.json()
    if (!res.ok || json.error) {
      calcResult.value = { success: false, error: json.error || `HTTP ${res.status}`, calculated_at: new Date().toISOString() }
    } else {
      calcResult.value = { success: true, ...json }
    }
  } catch (e) {
    calcResult.value = { success: false, error: `Network error: ${e.message}`, calculated_at: new Date().toISOString() }
  } finally {
    calcRunning.value = false
    // Refresh report list after calculation
    loadRecords()
  }
}

// ===== Report Table =====
const records = ref([])
const total = ref(0)
const page = ref(1)
const perPage = ref(20)
const pages = ref(1)
const sortBy = ref('calculated_at')
const sortDir = ref('desc')
const searchQuery = ref('')
const filters = reactive({
  payroll_month: '',
  entity: '',
  department: '',
  status: '',
})

// Filter options
const entityOptions = ref([])
const departmentOptions = ref([])
const statusOptions = [
  { value: 'completed', label: 'Completed' },
  { value: 'running', label: 'Running' },
  { value: 'failed', label: 'Failed' },
  { value: 'draft', label: 'Draft' },
]

let searchTimer = null

const visiblePages = computed(() => {
  const pgs = []
  const totalPages = pages.value
  const current = page.value
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pgs.push(i)
    return pgs
  }
  pgs.push(1)
  if (current > 3) pgs.push('...')
  const start = Math.max(2, current - 1)
  const end = Math.min(totalPages - 1, current + 1)
  for (let i = start; i <= end; i++) pgs.push(i)
  if (current < totalPages - 2) pgs.push('...')
  pgs.push(totalPages)
  return pgs
})

function sortIcon(field) {
  if (sortBy.value !== field) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(field) {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortDir.value = 'asc'
  }
  loadRecords()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadRecords() }, 350)
}

function applyFilters() { page.value = 1; loadRecords() }

function clearFilters() {
  filters.payroll_month = ''
  filters.entity = ''
  filters.department = ''
  filters.status = ''
  searchQuery.value = ''
  page.value = 1
  sortBy.value = 'calculated_at'
  sortDir.value = 'desc'
  loadRecords()
}

function onPerPageChange() { page.value = 1; loadRecords() }

function goToPage(p) {
  if (p < 1 || p > pages.value) return
  page.value = p
  loadRecords()
}

function viewDetail(record) {
  // Navigate to a filtered payslip list or open detail
  const payrollMonth = record.payroll_month || ''
  router.push({
    path: '/payslip/view',
    query: {
      payroll_month: payrollMonth,
      entity: record.entity || '',
      lang: lang.value,
    },
  })
}

async function loadRecords() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('page', page.value)
    params.set('per_page', perPage.value)
    params.set('sort_by', sortBy.value)
    params.set('sort_dir', sortDir.value)
    params.set('lang', lang.value)
    if (searchQuery.value) params.set('q', searchQuery.value)
    if (filters.payroll_month) params.set('payroll_month', filters.payroll_month)
    if (filters.entity) params.set('entity', filters.entity)
    if (filters.department) params.set('department', filters.department)
    if (filters.status) params.set('status', filters.status)

    const res = await fetch(`/api/payroll/report?${params.toString()}`, {
      credentials: 'same-origin',
    })
    const json = await res.json()
    if (!res.ok || json.error) {
      console.error('Failed to load report:', json.error)
      records.value = []
      total.value = 0
      pages.value = 1
    } else {
      records.value = json.records || json.data || []
      total.value = json.total || 0
      pages.value = json.pages || 1
      page.value = json.page || 1
    }
  } catch (e) {
    console.error('Network error loading report:', e)
  } finally {
    loading.value = false
  }
}

async function loadMasterdata() {
  try {
    const res = await fetch('/api/masterdata/entities', { credentials: 'same-origin' })
    const json = await res.json()
    const data = Array.isArray(json) ? json : (json.entities || json.data || [])
    entityOptions.value = data.map(e => e.entity_id || e.id || '').filter(Boolean).sort()
  } catch { /* silently fail */ }

  try {
    const res = await fetch('/api/masterdata/departments', { credentials: 'same-origin' })
    const json = await res.json()
    const data = Array.isArray(json) ? json : (json.departments || json.data || [])
    departmentOptions.value = data.map(d => d.department_id || d.id || '').filter(Boolean).sort()
  } catch { /* silently fail */ }
}

onMounted(() => {
  loadMasterdata()
  loadRecords()
})

watch(lang, () => {
  loadRecords()
})
</script>

<style scoped>
.salary-report {
  max-width: 1400px;
  margin: 0 auto;
}

/* ===== Calculation Form ===== */
.calc-form {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.calc-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.calc-field label {
  font-size: 12px;
  font-weight: 700;
  color: var(--navy);
  text-transform: uppercase;
}

.calc-field input,
.calc-field select {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}

.calc-field input:focus,
.calc-field select:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(10, 110, 209, .18);
}

/* ===== Filter Form ===== */
.filter-form {
  margin-bottom: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 10px 14px;
  align-items: end;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-field label {
  font-size: 12px;
  font-weight: 700;
  color: var(--navy);
  text-transform: uppercase;
}

.form-field input,
.form-field select {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  width: 100%;
}

.form-field input:focus,
.form-field select:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(10, 110, 209, .18);
}

.form-field.actions {
  flex-direction: row;
  gap: 6px;
}

.form-field.actions button {
  white-space: nowrap;
}

/* ===== Table ===== */
.table-card {
  padding: 0;
  overflow: hidden;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--line);
  background: #fafbfc;
}

.row-count {
  font-size: 13px;
  font-weight: 700;
  color: var(--navy);
}

.page-size {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.page-size select {
  padding: 5px 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}

.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead {
  background: #f1f5f9;
}

th {
  padding: 10px 14px;
  text-align: left;
  font-weight: 750;
  color: var(--navy);
  border-bottom: 2px solid var(--line);
  white-space: nowrap;
  user-select: none;
}

th.sortable {
  cursor: pointer;
}

th.sortable:hover {
  background: #e2e8f0;
}

.sort-icon {
  margin-left: 4px;
  font-size: 11px;
  color: var(--muted);
}

td {
  padding: 9px 14px;
  border-bottom: 1px solid #f0f2f5;
  white-space: nowrap;
}

tr:hover td {
  background: #f8fafc;
}

.empty-row {
  text-align: center;
  padding: 32px 14px !important;
  color: var(--muted);
  font-size: 14px;
}

.calc-time {
  font-weight: 650;
  color: var(--navy);
  font-variant-numeric: tabular-nums;
}

.actions-cell {
  font-size: 12px;
  white-space: nowrap;
}

.actions-cell a {
  color: var(--blue);
  text-decoration: none;
}

/* ===== Pagination ===== */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 20px;
  border-top: 1px solid var(--line);
  background: #fafbfc;
}

.page-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
  font-size: 13px;
  font-weight: 650;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--blue);
  color: var(--blue);
  background: #e8f0fe;
}

.page-btn.active {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-ellipsis {
  padding: 0 6px;
  color: var(--muted);
}

@media (max-width: 760px) {
  .calc-form {
    flex-direction: column;
    align-items: stretch;
  }
  .calc-field input,
  .calc-field select {
    max-width: 100% !important;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  table {
    font-size: 12px;
  }
  th, td {
    padding: 6px 8px;
  }
}
</style>
