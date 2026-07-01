<template>
  <div class="employee-list">
    <!-- Loading State -->
    <div v-if="loading && !employees.length" class="card flex-center" style="padding: 48px">
      <div>
        <div style="font-size: 32px; margin-bottom: 12px">⏳</div>
        <p class="muted">{{ t('app.loading') }}</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="apiError && !employees.length" class="card" style="text-align: center; padding: 48px">
      <div style="font-size: 48px; margin-bottom: 12px">⚠️</div>
      <h2 style="color: var(--red); margin: 0 0 8px">{{ t('error.load_failed') }}</h2>
      <p class="muted">{{ apiError }}</p>
      <button class="btn" style="margin-top: 16px" @click="loadEmployees">{{ t('action.retry') }}</button>
    </div>

    <!-- Main Content -->
    <template v-else>
      <!-- Header Card -->
      <div class="card">
        <div class="actions">
          <h2>{{ t('employee.list.title') }}</h2>
          <router-link v-if="canEdit" :to="`/employees/new?lang=${lang}`" class="btn">
            ＋ {{ t('action.create_employee') }}
          </router-link>
          <a v-if="canEdit" :href="`${baseUrl}/employees/import?lang=${lang}`" class="btn btn-secondary">
            📥 {{ t('import.title') }}
          </a>
        </div>
        <p v-if="masterdataWarning" class="muted">{{ masterdataWarning }}</p>

        <!-- Filter Form -->
        <form class="filter-form" @submit.prevent="applyFilters">
          <input type="hidden" name="lang" :value="lang" />
          <div class="form-grid">
            <div class="form-field">
              <label for="q">{{ t('action.search') }}</label>
              <input id="q" v-model="searchQuery" type="text" :placeholder="t('employee.search_placeholder')" @input="onSearchInput" />
            </div>
            <div class="form-field">
              <label for="entity">{{ t('field.entity_id') }}</label>
              <select id="entity" v-model="filters.entity_id" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="e in entityOptions" :key="e" :value="e">{{ e }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="country_code">{{ t('field.country_code') }}</label>
              <select id="country_code" v-model="filters.country_code" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="c in countryOptions" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="department">{{ t('field.department_id') }}</label>
              <select id="department" v-model="filters.department_id" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="d in departmentOptions" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="team">{{ t('field.team_id') }}</label>
              <select id="team" v-model="filters.team_id" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="tm in teamOptions" :key="tm" :value="tm">{{ tm }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="status">{{ t('field.status') }}</label>
              <select id="status" v-model="filters.status" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="s in statusOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
            <div class="form-field checkbox-field">
              <label><input type="checkbox" v-model="filters.show_resigned" @change="applyFilters" /> {{ t('filter.show_resigned') }}</label>
            </div>
            <div class="form-field">
              <label for="employment_type">{{ t('field.employment_type') }}</label>
              <select id="employment_type" v-model="filters.employment_type" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="et in employmentTypeOptions" :key="et.value" :value="et.value">{{ et.label }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="japanese_level">{{ t('field.japanese_level') }}</label>
              <select id="japanese_level" v-model="filters.japanese_level" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="jl in japaneseLevelOptions" :key="jl" :value="jl">{{ jl || t('filter.all') }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="english_level">{{ t('field.english_level') }}</label>
              <select id="english_level" v-model="filters.english_level" @change="applyFilters">
                <option value="">{{ t('filter.all') }}</option>
                <option v-for="el in englishLevelOptions" :key="el" :value="el">{{ el || t('filter.all') }}</option>
              </select>
            </div>
            <div class="form-field">
              <label for="skill">{{ t('filter.skill') }}</label>
              <input id="skill" v-model="filters.skill" type="text" :placeholder="t('filter.skill_placeholder')" @input="onSkillInput" />
            </div>
            <div class="form-field actions" style="align-self: flex-end">
              <button type="submit">{{ t('action.filter') }}</button>
              <button type="button" class="btn btn-secondary" @click="clearFilters">{{ t('action.clear') }}</button>
            </div>
          </div>
        </form>
      </div>

      <!-- Table Card -->
      <div class="card table-card">
        <p class="muted">{{ t('employee.list.sensitive_note') }}</p>
        <p class="muted">{{ t('employee.list.resigned_hidden_note') }}</p>

        <!-- Toolbar: row count + page size -->
        <div class="table-toolbar">
          <div class="row-count">
            <template v-if="hasActiveFilters">
              {{ t('employee.list.showing_filtered', { shown: employees.length, total: total }) }}
            </template>
            <template v-else>
              {{ t('employee.list.showing_total', { total: total }) }}
            </template>
          </div>
          <div class="page-size">
            <label>{{ t('employee.list.per_page') }}</label>
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
                <th class="sortable" @click="toggleSort('employee_number')">
                  {{ t('field.employee_number') }} <span class="sort-icon">{{ sortIcon('employee_number') }}</span>
                </th>
                <th class="sortable" @click="toggleSort('display_name')">
                  {{ t('field.display_name') }} <span class="sort-icon">{{ sortIcon('display_name') }}</span>
                </th>
                <th>{{ t('field.email') }}</th>
                <th>{{ t('field.entity') }}</th>
                <th>{{ t('field.department') }}</th>
                <th>{{ t('field.team') }}</th>
                <th class="sortable" @click="toggleSort('position')">
                  {{ t('field.position') }} <span class="sort-icon">{{ sortIcon('position') }}</span>
                </th>
                <th>{{ t('field.employment_type') }}</th>
                <th>{{ t('field.status') }}</th>
                <th>{{ t('field.japanese_level') }}</th>
                <th>{{ t('field.english_level') }}</th>
                <th>{{ t('field.primary_skill') }}</th>
                <th>{{ t('table.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="employees.length === 0">
                <td colspan="13" class="empty-row">{{ t('employee.list.empty') }}</td>
              </tr>
              <tr v-for="emp in employees" :key="emp.employee_id">
                <td class="employee-number">
                  <router-link :to="`/employees/${emp.employee_id}?lang=${lang}`">{{ emp.employee_number || emp.employee_id }}</router-link>
                </td>
                <td class="display-name">{{ emp.display_name || '—' }}</td>
                <td class="email">{{ emp.email || '—' }}</td>
                <td>{{ emp.entity_display || '—' }}</td>
                <td>{{ emp.department_display || '—' }}</td>
                <td>{{ emp.team_display || '—' }}</td>
                <td>{{ emp.position || '—' }}</td>
                <td><span :class="['badge', 'type-badge', emp.employment_type]">{{ t(`employment_type.${emp.employment_type}`) || emp.employment_type }}</span></td>
                <td><span :class="['badge', 'status-badge', emp.status]">{{ t(`status.${emp.status}`) || emp.status }}</span></td>
                <td>{{ emp.japanese_level || '—' }}</td>
                <td>{{ emp.english_level || '—' }}</td>
                <td>{{ emp.primary_skill || '—' }}</td>
                <td class="actions-cell">
                  <router-link :to="`/employees/${emp.employee_id}?lang=${lang}`">{{ t('action.view') }}</router-link>
                  <template v-if="canEdit"> | <router-link :to="`/employees/${emp.employee_id}/edit?lang=${lang}`">{{ t('action.edit') }}</router-link></template>
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
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useEmployeeApi } from '../composables/useEmployeeApi.js'

const route = useRoute()
const { loading, error: apiError, fetchEmployees, fetchMasterdata } = useEmployeeApi()

const lang = computed(() => route.query.lang || 'zh')
const canEdit = ref(true) // User permissions should come from auth
const masterdataWarning = ref('')

const translations = {
  zh: {
    'app.loading': '正在加载数据...', 'error.load_failed': '数据加载失败', 'action.retry': '重试',
    'employee.list.title': '员工管理 / Employee Management',
    'employee.list.empty': '未找到匹配的员工记录',
    'employee.list.per_page': '每页',
    'employee.list.showing_total': '共 {total} 条员工记录',
    'employee.list.showing_filtered': '显示 {shown} 条，共 {total} 条（已筛选）',
    'employee.list.sensitive_note': '⚠️ 薪资与银行信息不在列表页展示，查看详情可获取完整信息。',
    'employee.list.resigned_hidden_note': '默认隐藏已离职员工，勾选「显示离职」可查看。',
    'employee.search_placeholder': '搜索姓名、工号、邮箱、部门、法人...',
    'action.create_employee': '新增员工',
    'action.search': '搜索',
    'action.filter': '筛选',
    'action.clear': '清除',
    'action.view': '查看',
    'action.edit': '编辑',
    'import.title': '导入',
    'filter.all': '全部',
    'filter.show_resigned': '显示离职',
    'filter.skill': '技能',
    'filter.skill_placeholder': '搜索技能...',
    'table.actions': '操作',
    'field.employee_number': '工号',
    'field.display_name': '姓名',
    'field.email': '邮箱',
    'field.entity': '法人实体',
    'field.entity_id': '法人实体',
    'field.department': '部门',
    'field.department_id': '部门',
    'field.team': '团队',
    'field.team_id': '团队',
    'field.position': '职位',
    'field.employment_type': '雇佣类型',
    'field.status': '状态',
    'field.country_code': '国家',
    'field.japanese_level': '日语',
    'field.english_level': '英语',
    'field.primary_skill': '主要技能',
    'pagination.prev': '上一页', 'pagination.next': '下一页',
    'status.active': '在职', 'status.probation': '试用期', 'status.on_leave': '休假中', 'status.resigned': '已离职', 'status.suspended': '停职',
    'employment_type.employee': '正式员工', 'employment_type.contractor': '合同工', 'employment_type.dispatch': '派遣', 'employment_type.part_time': '兼职', 'employment_type.intern': '实习生',
  },
  ja: {
    'app.loading': 'データ読み込み中...', 'error.load_failed': 'データの読み込みに失敗しました', 'action.retry': '再試行',
    'employee.list.title': '従業員管理 / Employee Management',
    'employee.list.empty': '該当する従業員が見つかりません',
    'employee.list.per_page': '表示件数',
    'employee.list.showing_total': '全 {total} 件',
    'employee.list.showing_filtered': '{shown} 件表示 / 全 {total} 件（フィルター中）',
    'employee.list.sensitive_note': '⚠️ 給与・銀行情報は一覧に表示されません。詳細をご確認ください。',
    'employee.list.resigned_hidden_note': '退職者はデフォルトで非表示です。「退職者を表示」をチェックで表示。',
    'employee.search_placeholder': '名前、社員番号、メール、部署で検索...',
    'action.create_employee': '新規登録', 'action.search': '検索', 'action.filter': '絞り込む', 'action.clear': 'クリア', 'action.view': '表示', 'action.edit': '編集',
    'import.title': 'インポート',
    'filter.all': 'すべて', 'filter.show_resigned': '退職者を表示', 'filter.skill': 'スキル', 'filter.skill_placeholder': 'スキル検索...',
    'table.actions': '操作',
    'field.employee_number': '社員番号', 'field.display_name': '氏名', 'field.email': 'メール', 'field.entity': '法人', 'field.entity_id': '法人', 'field.department': '部署', 'field.department_id': '部署', 'field.team': 'チーム', 'field.team_id': 'チーム', 'field.position': '役職', 'field.employment_type': '雇用形態', 'field.status': 'ステータス', 'field.country_code': '国', 'field.japanese_level': '日本語', 'field.english_level': '英語', 'field.primary_skill': '主スキル',
    'pagination.prev': '前へ', 'pagination.next': '次へ',
    'status.active': '在職中', 'status.probation': '試用期間', 'status.on_leave': '休職中', 'status.resigned': '退職済', 'status.suspended': '停職中',
    'employment_type.employee': '正社員', 'employment_type.contractor': '契約社員', 'employment_type.dispatch': '派遣', 'employment_type.part_time': 'パート', 'employment_type.intern': 'インターン',
  },
  en: {
    'app.loading': 'Loading data...', 'error.load_failed': 'Failed to load data', 'action.retry': 'Retry',
    'employee.list.title': 'Employee Management / 员工管理',
    'employee.list.empty': 'No matching employees found',
    'employee.list.per_page': 'Per page',
    'employee.list.showing_total': '{total} employee(s) total',
    'employee.list.showing_filtered': 'Showing {shown} of {total} employees (filtered)',
    'employee.list.sensitive_note': '⚠️ Payroll and bank information is not displayed in the list. View details for full information.',
    'employee.list.resigned_hidden_note': 'Resigned employees are hidden by default. Check "Show Resigned" to display.',
    'employee.search_placeholder': 'Search name, ID, email, department, entity...',
    'action.create_employee': 'New Employee',
    'action.search': 'Search', 'action.filter': 'Filter', 'action.clear': 'Clear',
    'action.view': 'View', 'action.edit': 'Edit',
    'import.title': 'Import',
    'filter.all': 'All', 'filter.show_resigned': 'Show Resigned', 'filter.skill': 'Skill', 'filter.skill_placeholder': 'Search skills...',
    'table.actions': 'Actions',
    'field.employee_number': 'Employee No', 'field.display_name': 'Name', 'field.email': 'Email', 'field.entity': 'Entity', 'field.entity_id': 'Entity', 'field.department': 'Department', 'field.department_id': 'Department', 'field.team': 'Team', 'field.team_id': 'Team', 'field.position': 'Position', 'field.employment_type': 'Emp. Type', 'field.status': 'Status', 'field.country_code': 'Country', 'field.japanese_level': 'Japanese', 'field.english_level': 'English', 'field.primary_skill': 'Primary Skill',
    'pagination.prev': 'Prev', 'pagination.next': 'Next',
    'status.active': 'Active', 'status.probation': 'Probation', 'status.on_leave': 'On Leave', 'status.resigned': 'Resigned', 'status.suspended': 'Suspended',
    'employment_type.employee': 'Employee', 'employment_type.contractor': 'Contractor', 'employment_type.dispatch': 'Dispatch', 'employment_type.part_time': 'Part-time', 'employment_type.intern': 'Intern',
  },
}

function t(key, params = {}) {
  let text = translations[lang.value]?.[key] || translations.en[key] || key
  Object.entries(params).forEach(([k, v]) => { text = text.replace(`{${k}}`, v) })
  return text
}

// Backend base URL for import link
const baseUrl = computed(() => 'http://127.0.0.1:8004')

// State
const employees = ref([])
const total = ref(0)
const page = ref(1)
const perPage = ref(20)
const pages = ref(1)
const sortBy = ref('employee_number')
const sortDir = ref('asc')
const searchQuery = ref('')
const filters = reactive({
  entity_id: '', country_code: '', department_id: '', team_id: '',
  status: '', show_resigned: false, employment_type: '',
  japanese_level: '', english_level: '', skill: '',
})

// Filter options from API data
const entityOptions = ref([])
const countryOptions = ref([])
const departmentOptions = ref([])
const teamOptions = ref([])
const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'probation', label: 'Probation' },
  { value: 'on_leave', label: 'On Leave' },
  { value: 'resigned', label: 'Resigned' },
  { value: 'suspended', label: 'Suspended' },
]
const employmentTypeOptions = [
  { value: 'employee', label: 'Employee' },
  { value: 'contractor', label: 'Contractor' },
  { value: 'dispatch', label: 'Dispatch' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'intern', label: 'Intern' },
]
const japaneseLevelOptions = ['', 'N1', 'N2', 'N3', 'N4', 'N5', 'native']
const englishLevelOptions = ['', 'native', 'business', 'intermediate', 'basic']

let searchTimer = null
let skillTimer = null

const hasActiveFilters = computed(() => {
  return !!(filters.entity_id || filters.country_code || filters.department_id || filters.team_id ||
    filters.status || filters.show_resigned || filters.employment_type ||
    filters.japanese_level || filters.english_level || filters.skill || searchQuery.value)
})

// Pagination
const visiblePages = computed(() => {
  const pgs = []
  const totalPages = pages.value
  const current = page.value
  if (totalPages <= 7) { for (let i = 1; i <= totalPages; i++) pgs.push(i); return pgs }
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
  if (sortBy.value === field) { sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc' }
  else { sortBy.value = field; sortDir.value = 'asc' }
  loadEmployees()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadEmployees() }, 350)
}

function onSkillInput() {
  clearTimeout(skillTimer)
  skillTimer = setTimeout(() => { page.value = 1; loadEmployees() }, 500)
}

function applyFilters() { page.value = 1; loadEmployees() }

function clearFilters() {
  filters.entity_id = ''; filters.country_code = ''; filters.department_id = ''; filters.team_id = ''
  filters.status = ''; filters.show_resigned = false; filters.employment_type = ''
  filters.japanese_level = ''; filters.english_level = ''; filters.skill = ''
  searchQuery.value = ''; page.value = 1; sortBy.value = 'employee_number'; sortDir.value = 'asc'
  loadEmployees()
}

function onPerPageChange() { page.value = 1; loadEmployees() }

function goToPage(p) { if (p < 1 || p > pages.value) return; page.value = p; loadEmployees() }

async function loadEmployees() {
  const result = await fetchEmployees({
    page: page.value,
    per_page: perPage.value,
    q: searchQuery.value,
    entity_id: filters.entity_id,
    department_id: filters.department_id,
    team_id: filters.team_id,
    country_code: filters.country_code,
    status: filters.status,
    employment_type: filters.employment_type,
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    lang: lang.value,
  })
  if (result && !result.error) {
    employees.value = result.employees || []
    total.value = result.total || 0
    pages.value = result.pages || 1
    page.value = result.page || 1
  }
}

async function loadMasterdata() {
  try {
    const ent = await fetchMasterdata('entities')
    entityOptions.value = (ent || []).map(e => e.entity_id || e.id || '').filter(Boolean).sort()
  } catch { masterdataWarning.value = 'Masterdata temporarily unavailable' }
  try {
    const dept = await fetchMasterdata('departments')
    departmentOptions.value = (dept || []).map(d => d.department_id || d.id || '').filter(Boolean).sort()
  } catch {}
}

onMounted(() => {
  // Redirect to Python backend — list/detail served by backend, Vue only handles forms
  const queryStr = route.query.lang ? `?lang=${route.query.lang}` : ''
  window.location.replace(`http://127.0.0.1:8004/employees${queryStr}`)
})
</script>

<style scoped>
.employee-list { max-width: 1400px; margin: 0 auto; }

.actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.actions h2 { margin: 0; font-size: 20px; color: var(--navy); flex: 1; }

.filter-form { margin-top: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px 14px; align-items: end; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-size: 12px; font-weight: 700; color: var(--navy); text-transform: uppercase; }
.form-field input, .form-field select { padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; font-size: 13px; background: #fff; }
.form-field input:focus, .form-field select:focus { outline: none; border-color: var(--blue); box-shadow: 0 0 0 3px var(--primary-light); }
.form-field.actions { flex-direction: row; gap: 6px; }
.form-field.actions button { white-space: nowrap; }
.checkbox-field label { display: flex; align-items: center; gap: 6px; font-weight: 650; cursor: pointer; }
.checkbox-field input[type=checkbox] { width: auto; }

.table-card { padding: 0; overflow: hidden; }
.table-card > .muted { padding: 12px 20px 0; margin: 0; font-size: 12px; }

.table-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; border-bottom: 1px solid var(--line); background: #fafbfc; }
.row-count { font-size: 13px; font-weight: 700; color: var(--navy); }
.page-size { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.page-size select { padding: 5px 8px; border: 1px solid var(--line); border-radius: 6px; font-size: 13px; background: #fff; }

.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead { background: #f1f5f9; }
th { padding: 10px 14px; text-align: left; font-weight: 750; color: var(--navy); border-bottom: 2px solid var(--line); white-space: nowrap; user-select: none; }
th.sortable { cursor: pointer; }
th.sortable:hover { background: #e2e8f0; }
.sort-icon { margin-left: 4px; font-size: 11px; color: var(--muted); }
td { padding: 9px 14px; border-bottom: 1px solid #f0f2f5; white-space: nowrap; }
tr:hover td { background: #f8fafc; }
.empty-row { text-align: center; padding: 32px 14px !important; color: var(--muted); font-size: 14px; }
.employee-number { font-weight: 700; color: var(--navy); }
.employee-number a { color: var(--blue); text-decoration: none; }
.display-name { font-weight: 650; }
.email { color: var(--blue); font-size: 12px; }
.actions-cell { font-size: 12px; white-space: nowrap; }
.actions-cell a { color: var(--blue); }

.badge { display: inline-block; border-radius: 14px; padding: 3px 8px; font-size: 11px; font-weight: 750; }
.status-badge.active { background: #e4f7e7; color: #107e3e; }
.status-badge.probation { background: #fef3c7; color: #92400e; }
.status-badge.on_leave { background: #dbeafe; color: #1e40af; }
.status-badge.resigned { background: #fce7f3; color: #9d174d; }
.status-badge.suspended { background: #f3f4f6; color: #6b7280; }
.type-badge.employee { background: #e0e7ff; color: #3730a3; }
.type-badge.contractor { background: #fef3c7; color: #92400e; }
.type-badge.dispatch { background: #d1fae5; color: #065f46; }
.type-badge.part_time { background: #fce7f3; color: #9d174d; }
.type-badge.intern { background: #e0f2fe; color: #075985; }

.pagination { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 14px 20px; border-top: 1px solid var(--line); background: #fafbfc; }
.page-btn { display: inline-flex; align-items: center; justify-content: center; min-width: 34px; height: 34px; padding: 0 10px; border: 1px solid var(--line); border-radius: 7px; background: #fff; font-size: 13px; font-weight: 650; color: var(--text); cursor: pointer; transition: all 0.15s; }
.page-btn:hover:not(:disabled) { border-color: var(--blue); color: var(--blue); background: #e8f0fe; }
.page-btn.active { background: var(--blue); color: #fff; border-color: var(--blue); }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-ellipsis { padding: 0 6px; color: var(--muted); }

@media (max-width: 760px) {
  .actions { flex-direction: column; align-items: stretch; }
  .form-grid { grid-template-columns: 1fr; }
  table { font-size: 12px; }
  th, td { padding: 6px 8px; }
}
</style>
