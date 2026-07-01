<template>
  <div class="employee-detail">
    <!-- Loading -->
    <div v-if="loading" class="card flex-center" style="padding: 48px">
      <div>
        <div style="font-size: 32px; margin-bottom: 12px">⏳</div>
        <p class="muted">{{ t('app.loading') }}</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card" style="text-align: center; padding: 48px">
      <div style="font-size: 48px; margin-bottom: 12px">⚠️</div>
      <h2 style="color: var(--red); margin: 0 0 8px">{{ t('error.not_found') }}</h2>
      <p class="muted">{{ error }}</p>
      <router-link :to="`/employees?lang=${lang}`" class="btn" style="margin-top: 16px">← {{ t('action.back') }}</router-link>
    </div>

    <!-- Detail Content -->
    <template v-else-if="employee">
      <!-- Header -->
      <div class="detail-header">
        <div class="header-content">
          <p class="eyebrow">{{ t('employee.detail.kicker') }}</p>
          <h2>{{ employee.profile?.name?.display_name || employee.employee_number || employee.employee_id }}</h2>
          <div class="header-actions">
            <router-link :to="`/employees/${employee.employee_id}/edit?lang=${lang}`" class="btn">{{ t('action.edit') }}</router-link>
            <router-link :to="`/employees?lang=${lang}`" class="btn btn-secondary">← {{ t('action.back') }}</router-link>
          </div>
        </div>
        <div class="meta-chips">
          <span class="meta-chip"><span class="meta-label">{{ t('field.employee_number') }}</span><span class="meta-value">{{ employee.employee_number || '—' }}</span></span>
          <span :class="['meta-chip', 'meta-status', employee.employment?.status]"><span class="meta-label">{{ t('field.status') }}</span><span class="meta-value">{{ t(`status.${employee.employment?.status}`) || employee.employment?.status || '—' }}</span></span>
          <span class="meta-chip"><span class="meta-label">{{ t('field.department') }}</span><span class="meta-value">{{ employee.department_display || '—' }}</span></span>
          <span class="meta-chip"><span class="meta-label">{{ t('field.employment_type') }}</span><span class="meta-value">{{ t(`employment_type.${employee.employment?.employment_type}`) || employee.employment?.employment_type || '—' }}</span></span>
        </div>
      </div>

      <div class="detail-body">
        <!-- Profile Section -->
        <section class="detail-section">
          <h3>👤 {{ t('section.profile') }}</h3>
          <div class="detail-grid">
            <div class="detail-field"><span class="detail-label">{{ t('field.name.display_name') }}</span><span class="detail-value">{{ employee.profile?.name?.display_name || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.name.family_name') }}</span><span class="detail-value">{{ employee.profile?.name?.family_name || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.name.given_name') }}</span><span class="detail-value">{{ employee.profile?.name?.given_name || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.name.romaji_name') }}</span><span class="detail-value">{{ employee.profile?.name?.romaji_name || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.gender') }}</span><span class="detail-value">{{ t(`gender.${employee.profile?.gender}`) || employee.profile?.gender || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.date_of_birth') }}</span><span class="detail-value">{{ employee.profile?.date_of_birth || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.nationality') }}</span><span class="detail-value">{{ employee.profile?.nationality || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.email') }}</span><span class="detail-value">{{ employee.profile?.email || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.phone') }}</span><span class="detail-value">{{ employee.profile?.phone || '—' }}</span></div>
            <div class="detail-field long"><span class="detail-label">{{ t('field.address') }}</span><span class="detail-value">{{ formatAddress(employee.profile?.address) }}</span></div>
          </div>
        </section>

        <!-- Employment Section -->
        <section class="detail-section">
          <h3>💼 {{ t('section.employment') }}</h3>
          <div class="detail-grid">
            <div class="detail-field"><span class="detail-label">{{ t('field.entity') }}</span><span class="detail-value">{{ employee.entity_display || employee.employment?.legal_entity || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.department') }}</span><span class="detail-value">{{ employee.department_display || employee.employment?.department || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.team') }}</span><span class="detail-value">{{ employee.team_display || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.position') }}</span><span class="detail-value">{{ employee.employment?.position || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.employment_type') }}</span><span class="detail-value">{{ t(`employment_type.${employee.employment?.employment_type}`) || employee.employment?.employment_type || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.status') }}</span><span class="detail-value">{{ t(`status.${employee.employment?.status}`) || employee.employment?.status || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.country_code') }}</span><span class="detail-value">{{ employee.employment?.country_code || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.work_country') }}</span><span class="detail-value">{{ employee.employment?.work_country || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.join_date') }}</span><span class="detail-value">{{ employee.employment?.join_date || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.business_line') }}</span><span class="detail-value">{{ employee.employment?.business_line || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.office_location') }}</span><span class="detail-value">{{ employee.employment?.office_location || '—' }}</span></div>
          </div>
        </section>

        <!-- Payroll Section -->
        <section class="detail-section">
          <h3>💰 {{ t('section.payroll') }}</h3>
          <div class="detail-grid">
            <div class="detail-field"><span class="detail-label">{{ t('field.salary_type') }}</span><span class="detail-value">{{ t(`salary_type.${employee.payroll?.salary_type}`) || employee.payroll?.salary_type || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.payroll_currency') }}</span><span class="detail-value">{{ employee.payroll?.payroll_currency || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.monthly_base_salary') }}</span><span class="detail-value">{{ employee.payroll?.monthly_base_salary || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.hourly_wage') }}</span><span class="detail-value">{{ employee.payroll?.hourly_wage || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.bank_name') }}</span><span class="detail-value">{{ employee.payroll?.bank?.bank_name || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.bank_account_number') }}</span><span class="detail-value">{{ employee.payroll?.bank?.account_number || '—' }}</span></div>
          </div>
        </section>

        <!-- Skills & Language -->
        <section class="detail-section">
          <h3>🎓 {{ t('section.skills_language') }}</h3>
          <div class="detail-grid">
            <div class="detail-field"><span class="detail-label">{{ t('field.japanese_level') }}</span><span class="detail-value">{{ employee.language_profile?.japanese_level || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.english_level') }}</span><span class="detail-value">{{ employee.language_profile?.english_level || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.primary_skill') }}</span><span class="detail-value">{{ employee.skills_profile?.primary_skill || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.secondary_skill') }}</span><span class="detail-value">{{ employee.skills_profile?.secondary_skill || '—' }}</span></div>
            <div class="detail-field long"><span class="detail-label">{{ t('field.native_languages') }}</span><span class="detail-value">{{ (employee.language_profile?.native_languages || []).join(', ') || '—' }}</span></div>
          </div>
        </section>

        <!-- Metadata -->
        <section class="detail-section muted-section">
          <h3>📋 {{ t('section.metadata') }}</h3>
          <div class="detail-grid">
            <div class="detail-field"><span class="detail-label">{{ t('field.created_at') }}</span><span class="detail-value">{{ employee.metadata?.created_at || '—' }}</span></div>
            <div class="detail-field"><span class="detail-label">{{ t('field.updated_at') }}</span><span class="detail-value">{{ employee.metadata?.updated_at || '—' }}</span></div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useEmployeeApi } from '../composables/useEmployeeApi.js'

const route = useRoute()
const { loading, error, fetchEmployee } = useEmployeeApi()

const employee = ref(null)

const lang = computed(() => route.query.lang || 'zh')

const translations = {
  zh: {
    'app.loading': '正在加载...',
    'error.not_found': '员工未找到',
    'employee.detail.kicker': '员工详情 / Employee Detail',
    'action.edit': '编辑',
    'action.back': '返回列表',
    'section.profile': '个人信息 / Profile',
    'section.employment': '雇佣信息 / Employment',
    'section.payroll': '薪资信息 / Payroll',
    'section.skills_language': '技能与语言 / Skills & Language',
    'section.metadata': '记录信息 / Metadata',
    'field.employee_number': '工号',
    'field.status': '状态',
    'field.department': '部门',
    'field.employment_type': '雇佣类型',
    'field.name.display_name': '显示姓名',
    'field.name.family_name': '姓',
    'field.name.given_name': '名',
    'field.name.romaji_name': '罗马字',
    'field.gender': '性别',
    'field.date_of_birth': '出生日期',
    'field.nationality': '国籍',
    'field.email': '邮箱',
    'field.phone': '电话',
    'field.address': '地址',
    'field.entity': '法人实体',
    'field.team': '团队',
    'field.position': '职位',
    'field.country_code': '国家代码',
    'field.work_country': '工作国家',
    'field.join_date': '入职日期',
    'field.business_line': '业务线',
    'field.office_location': '办公地点',
    'field.salary_type': '薪资类型',
    'field.payroll_currency': '薪资币种',
    'field.monthly_base_salary': '月基本工资',
    'field.hourly_wage': '时薪',
    'field.bank_name': '银行名称',
    'field.bank_account_number': '银行账号',
    'field.japanese_level': '日语水平',
    'field.english_level': '英语水平',
    'field.primary_skill': '主要技能',
    'field.secondary_skill': '次要技能',
    'field.native_languages': '母语',
    'field.created_at': '创建时间',
    'field.updated_at': '更新时间',
    'gender.male': '男',
    'gender.female': '女',
    'gender.other': '其他',
    'status.active': '在职',
    'status.probation': '试用期',
    'status.on_leave': '休假中',
    'status.resigned': '已离职',
    'status.suspended': '停职',
    'employment_type.employee': '正式员工',
    'employment_type.contractor': '合同工',
    'employment_type.dispatch': '派遣',
    'employment_type.part_time': '兼职',
    'employment_type.intern': '实习生',
    'salary_type.monthly': '月薪',
    'salary_type.hourly': '时薪',
    'salary_type.daily': '日薪',
  },
  en: {
    'app.loading': 'Loading...',
    'error.not_found': 'Employee not found',
    'employee.detail.kicker': 'Employee Detail',
    'action.edit': 'Edit',
    'action.back': 'Back to List',
    'section.profile': 'Profile',
    'section.employment': 'Employment',
    'section.payroll': 'Payroll',
    'section.skills_language': 'Skills & Language',
    'section.metadata': 'Metadata',
    'field.employee_number': 'Employee No',
    'field.status': 'Status',
    'field.department': 'Department',
    'field.employment_type': 'Emp. Type',
    'field.name.display_name': 'Display Name',
    'field.name.family_name': 'Family Name',
    'field.name.given_name': 'Given Name',
    'field.name.romaji_name': 'Romaji Name',
    'field.gender': 'Gender',
    'field.date_of_birth': 'Date of Birth',
    'field.nationality': 'Nationality',
    'field.email': 'Email',
    'field.phone': 'Phone',
    'field.address': 'Address',
    'field.entity': 'Entity',
    'field.team': 'Team',
    'field.position': 'Position',
    'field.country_code': 'Country Code',
    'field.work_country': 'Work Country',
    'field.join_date': 'Join Date',
    'field.business_line': 'Business Line',
    'field.office_location': 'Office Location',
    'field.salary_type': 'Salary Type',
    'field.payroll_currency': 'Currency',
    'field.monthly_base_salary': 'Monthly Base',
    'field.hourly_wage': 'Hourly Wage',
    'field.bank_name': 'Bank Name',
    'field.bank_account_number': 'Account No',
    'field.japanese_level': 'Japanese',
    'field.english_level': 'English',
    'field.primary_skill': 'Primary Skill',
    'field.secondary_skill': 'Secondary Skill',
    'field.native_languages': 'Native Languages',
    'field.created_at': 'Created',
    'field.updated_at': 'Updated',
    'gender.male': 'Male',
    'gender.female': 'Female',
    'gender.other': 'Other',
    'status.active': 'Active',
    'status.probation': 'Probation',
    'status.on_leave': 'On Leave',
    'status.resigned': 'Resigned',
    'status.suspended': 'Suspended',
    'employment_type.employee': 'Employee',
    'employment_type.contractor': 'Contractor',
    'employment_type.dispatch': 'Dispatch',
    'employment_type.part_time': 'Part-time',
    'employment_type.intern': 'Intern',
    'salary_type.monthly': 'Monthly',
    'salary_type.hourly': 'Hourly',
    'salary_type.daily': 'Daily',
  },
  ja: {
    'app.loading': '読み込み中...',
    'error.not_found': '従業員が見つかりません',
    'employee.detail.kicker': '従業員詳細',
    'action.edit': '編集',
    'action.back': '一覧に戻る',
    'section.profile': 'プロフィール',
    'section.employment': '雇用情報',
    'section.payroll': '給与情報',
    'section.skills_language': 'スキル・言語',
    'section.metadata': 'メタデータ',
    'field.employee_number': '社員番号',
    'field.status': 'ステータス',
    'field.department': '部署',
    'field.employment_type': '雇用形態',
    'field.name.display_name': '表示名',
    'field.name.family_name': '姓',
    'field.name.given_name': '名',
    'field.name.romaji_name': 'ローマ字',
    'field.gender': '性別',
    'field.date_of_birth': '生年月日',
    'field.nationality': '国籍',
    'field.email': 'メール',
    'field.phone': '電話',
    'field.address': '住所',
    'field.entity': '法人',
    'field.team': 'チーム',
    'field.position': '役職',
    'field.country_code': '国コード',
    'field.work_country': '勤務国',
    'field.join_date': '入社日',
    'field.business_line': '事業ライン',
    'field.office_location': '勤務地',
    'field.salary_type': '給与タイプ',
    'field.payroll_currency': '通貨',
    'field.monthly_base_salary': '月額基本給',
    'field.hourly_wage': '時給',
    'field.bank_name': '銀行名',
    'field.bank_account_number': '口座番号',
    'field.japanese_level': '日本語',
    'field.english_level': '英語',
    'field.primary_skill': '主スキル',
    'field.secondary_skill': '副スキル',
    'field.native_languages': '母国語',
    'field.created_at': '作成日',
    'field.updated_at': '更新日',
    'gender.male': '男性',
    'gender.female': '女性',
    'gender.other': 'その他',
    'status.active': '在職中',
    'status.probation': '試用期間',
    'status.on_leave': '休職中',
    'status.resigned': '退職済',
    'status.suspended': '停職中',
    'employment_type.employee': '正社員',
    'employment_type.contractor': '契約社員',
    'employment_type.dispatch': '派遣',
    'employment_type.part_time': 'パート',
    'employment_type.intern': 'インターン',
    'salary_type.monthly': '月給',
    'salary_type.hourly': '時給',
    'salary_type.daily': '日給',
  },
}

function t(key) {
  return translations[lang.value]?.[key] || translations.en[key] || key
}

function formatAddress(addr) {
  if (!addr) return '—'
  const parts = [addr.country, addr.postal_code, addr.prefecture, addr.city, addr.street, addr.building].filter(Boolean)
  return parts.join(' ') || '—'
}

async function loadEmployee() {
  const id = route.params.id
  if (!id) {
    error.value = 'Missing employee ID'
    return
  }
  const result = await fetchEmployee(id, lang.value)
  if (result && !result.error) {
    employee.value = result
  }
}

onMounted(() => {
  // Redirect to Python backend — list/detail served by backend, Vue only handles forms
  const id = route.params.id
  const queryStr = route.query.lang ? `?lang=${route.query.lang}` : ''
  if (id) window.location.replace(`http://127.0.0.1:8004/employees/${id}${queryStr}`)
})
</script>

<style scoped>
.employee-detail {
  max-width: 980px;
  margin: 0 auto;
}

/* Header */
.detail-header {
  background: linear-gradient(135deg, #14213d 0%, #1a3a5c 100%);
  color: white;
  padding: 28px 32px;
  border-radius: 14px 14px 0 0;
}

.header-content .eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
  margin: 0 0 4px;
}

.header-content h2 {
  margin: 0 0 16px;
  font-size: 24px;
  font-weight: 850;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.meta-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.12);
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 12px;
}

.meta-chip .meta-label {
  opacity: 0.7;
  font-size: 10px;
  text-transform: uppercase;
}

.meta-chip .meta-value {
  font-weight: 750;
}

.meta-status.active .meta-value { color: #86efac; }
.meta-status.probation .meta-value { color: #fde68a; }
.meta-status.on_leave .meta-value { color: #93c5fd; }
.meta-status.resigned .meta-value { color: #fda4af; }

/* Body */
.detail-body {
  background: white;
  border: 1px solid #e0e5ec;
  border-top: none;
  padding: 28px 32px;
  border-radius: 0 0 14px 14px;
}

.detail-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f0f2f5;
}

.detail-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.detail-section h3 {
  font-size: 15px;
  color: var(--navy);
  margin: 0 0 14px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--blue);
}

.muted-section h3 {
  border-bottom-color: var(--line);
  color: var(--muted);
}

.muted-section .detail-value {
  color: var(--muted);
  font-size: 12px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px 24px;
}

.detail-field {
  padding: 6px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-field.long {
  grid-column: 1 / -1;
}

.detail-label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.detail-value {
  font-size: 14px;
  font-weight: 650;
  color: var(--text);
}

@media (max-width: 760px) {
  .detail-header {
    padding: 20px 18px;
  }

  .detail-body {
    padding: 20px 18px;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
