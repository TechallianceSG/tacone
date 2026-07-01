<template>
  <div class="employee-form-page">
    <!-- Loading (edit mode only) -->
    <div v-if="loading && isEdit" class="card flex-center" style="padding: 48px">
      <div><div style="font-size: 32px; margin-bottom: 12px">⏳</div><p class="muted">{{ t('app.loading') }}</p></div>
    </div>

    <!-- Load error -->
    <div v-else-if="loadError && isEdit" class="card" style="text-align: center; padding: 48px">
      <div style="font-size: 48px; margin-bottom: 12px">⚠️</div>
      <h2 style="color: var(--red); margin: 0 0 8px">{{ t('error.load_failed') }}</h2>
      <p class="muted">{{ loadError }}</p>
      <a :href="`http://127.0.0.1:8004/employees?lang=${lang}`" class="btn" style="margin-top: 16px">← {{ t('action.back') }}</a>
    </div>

    <!-- Form -->
    <template v-else>
      <section class="object-page">
        <!-- Header -->
        <div class="form-header-section">
          <h2>{{ isEdit ? '✏️ ' + t('employee.edit.title') : '➕ ' + t('employee.create.title') }}</h2>
          <p class="muted">{{ isEdit ? t('employee.edit.description') : t('employee.create.description') }}</p>
          <p v-if="isEdit" class="muted">{{ t('employee.form.editing') }}: {{ form.employee_number || form.profile.name.display_name || employeeId }}</p>
        </div>

        <!-- Notices -->
        <div v-if="successMsg" class="success-strip" role="status">✅ {{ successMsg }}</div>
        <div v-if="apiError" class="error-strip" role="alert">
          ❌ {{ apiError }}
          <ul v-if="validationErrors.length"><li v-for="(ve, i) in validationErrors" :key="i">{{ ve }}</li></ul>
        </div>

        <form class="employee-form" method="post" @submit.prevent="handleSubmit">
          <p class="required-note">{{ t('employee.form.required_note') }}</p>

          <!-- Tab Nav -->
          <div class="form-tabs">
            <button v-for="tab in tabs" :key="tab.key" type="button" :class="['tab-btn', { active: activeTab === tab.key }]" @click="activeTab = tab.key">{{ tab.icon }} {{ tab.label }}</button>
          </div>

          <!-- === PROFILE TAB === -->
          <div v-show="activeTab === 'profile'" class="tab-content">
            <!-- Name group -->
            <h4 class="field-group-title">{{ t('form.group.name') }}</h4>
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.employee_number') }} <span class="required">*</span></label><input v-model="form.employee_number" class="form-input" /><span v-if="fieldErrors['employee_number']" class="field-err">{{ fieldErrors['employee_number'][0] }}</span></div>
              <div class="form-field"><label>{{ t('field.name.display_name') }} <span class="required">*</span></label><input v-model="form.profile.name.display_name" class="form-input" /><span v-if="fieldErrors['profile.name.display_name']" class="field-err">{{ fieldErrors['profile.name.display_name'][0] }}</span></div>
              <div class="form-field"><label>{{ t('field.name.family_name') }}</label><input v-model="form.profile.name.family_name" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.name.given_name') }}</label><input v-model="form.profile.name.given_name" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.name.family_name_kana') }}</label><input v-model="form.profile.name.family_name_kana" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.name.given_name_kana') }}</label><input v-model="form.profile.name.given_name_kana" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.name.romaji_name') }}</label><input v-model="form.profile.name.romaji_name" class="form-input" /></div>
            </div>

            <!-- Personal group -->
            <h4 class="field-group-title">{{ t('form.group.personal') }}</h4>
            <div class="form-grid compact">
              <div class="form-field"><label>{{ t('field.gender') }}</label><select v-model="form.profile.gender" class="form-input"><option value="">{{ t('action.select') }}</option><option value="male">{{ t('gender.male') }}</option><option value="female">{{ t('gender.female') }}</option><option value="other">{{ t('gender.other') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.date_of_birth') }}</label><input v-model="form.profile.date_of_birth" type="date" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.nationality') }}</label><input v-model="form.profile.nationality" class="form-input" /></div>
            </div>

            <!-- Contact group -->
            <h4 class="field-group-title">{{ t('form.group.contact') }}</h4>
            <div class="form-grid compact">
              <div class="form-field"><label>{{ t('field.email') }} <span class="required">*</span></label><input v-model="form.profile.email" type="email" class="form-input" /><span v-if="fieldErrors['profile.email']" class="field-err">{{ fieldErrors['profile.email'][0] }}</span></div>
              <div class="form-field"><label>{{ t('field.email_p') }}</label><input v-model="form.profile.email_p" type="email" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.phone') }}</label><input v-model="form.profile.phone" class="form-input" /></div>
            </div>

            <!-- Address group -->
            <h4 class="field-group-title">{{ t('form.group.address') }}</h4>
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.address.postal_code') }}</label><input v-model="form.profile.address.postal_code" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.address.prefecture') }}</label><input v-model="form.profile.address.prefecture" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.address.city') }}</label><input v-model="form.profile.address.city" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.address.street') }}</label><input v-model="form.profile.address.street" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.address.building') }}</label><input v-model="form.profile.address.building" class="form-input" /></div>
            </div>

            <!-- Emergency contact group -->
            <h4 class="field-group-title">{{ t('form.group.emergency_contact') }}</h4>
            <div class="form-grid compact">
              <div class="form-field"><label>{{ t('field.emergency_contact.name') }}</label><input v-model="form.profile.emergency_contact.name" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.emergency_contact.relationship') }}</label><input v-model="form.profile.emergency_contact.relationship" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.emergency_contact.phone') }}</label><input v-model="form.profile.emergency_contact.phone" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.emergency_contact.email') }}</label><input v-model="form.profile.emergency_contact.email" type="email" class="form-input" /></div>
            </div>
          </div>

          <!-- === EMPLOYMENT TAB === -->
          <div v-show="activeTab === 'employment'" class="tab-content">
            <h4 class="field-group-title">{{ t('form.group.employment_basics') }}</h4>
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.entity_id') }} <span class="required">*</span></label><input v-model="form.employment.entity_id" class="form-input" placeholder="ENT-0001" /><span v-if="fieldErrors['employment.entity_id']" class="field-err">{{ fieldErrors['employment.entity_id'][0] }}</span></div>
              <div class="form-field"><label>{{ t('field.department_id') }}</label><input v-model="form.employment.department_id" class="form-input" placeholder="DEP-0001" /></div>
              <div class="form-field"><label>{{ t('field.team_id') }}</label><input v-model="form.employment.team_id" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.country_code') }} <span class="required">*</span></label><select v-model="form.employment.country_code" class="form-input"><option value="">{{ t('action.select') }}</option><option v-for="c in countryCodes" :key="c" :value="c">{{ c }}</option></select></div>
              <div class="form-field"><label>{{ t('field.work_country') }} <span class="required">*</span></label><select v-model="form.employment.work_country" class="form-input"><option value="">{{ t('action.select') }}</option><option v-for="c in countryCodes" :key="c" :value="c">{{ c }}</option></select></div>
              <div class="form-field"><label>{{ t('field.business_line') }}</label><select v-model="form.employment.business_line" class="form-input"><option value="">{{ t('action.select') }}</option><option v-for="bl in businessLines" :key="bl" :value="bl">{{ bl }}</option></select></div>
              <div class="form-field"><label>{{ t('field.join_date') }} <span class="required">*</span></label><input v-model="form.employment.join_date" type="date" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.employment_type') }} <span class="required">*</span></label><select v-model="form.employment.employment_type" class="form-input"><option value="employee">{{ t('employment_type.employee') }}</option><option value="contractor">{{ t('employment_type.contractor') }}</option><option value="dispatch">{{ t('employment_type.dispatch') }}</option><option value="part_time">{{ t('employment_type.part_time') }}</option><option value="intern">{{ t('employment_type.intern') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.position') }}</label><input v-model="form.employment.position" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.manager_employee_id') }}</label><input v-model="form.employment.manager_employee_id" class="form-input" /></div>
            </div>

            <!-- Labor contract group -->
            <h4 class="field-group-title">{{ t('form.group.labor_contract') }}</h4>
            <div class="form-grid compact">
              <div class="form-field"><label>{{ t('field.contract.start_date') }}</label><input v-model="form.employment.contract.start_date" type="date" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.contract.end_date') }}</label><input v-model="form.employment.contract.end_date" type="date" class="form-input" /></div>
            </div>
            <p class="muted long">{{ t('employment.labor_contract_note') }}</p>

            <!-- Assignment group -->
            <h4 class="field-group-title">{{ t('form.group.assignment') }}</h4>
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.office_location') }}</label><input v-model="form.employment.office_location" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.assignment') }}</label><input v-model="form.employment.assignment" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.status') }} <span class="required">*</span></label><select v-model="form.employment.status" class="form-input"><option value="active">{{ t('status.active') }}</option><option value="probation">{{ t('status.probation') }}</option><option value="on_leave">{{ t('status.on_leave') }}</option><option value="resigned">{{ t('status.resigned') }}</option><option value="suspended">{{ t('status.suspended') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.profile_status') }}</label><select v-model="form.metadata.profile_status" class="form-input"><option value="draft">Draft</option><option value="complete">Complete</option><option value="needs_review">Needs Review</option></select></div>
              <div class="form-field"><label>{{ t('field.probation_end_date') }}</label><input v-model="form.employment.probation_end_date" type="date" class="form-input" /></div>
            </div>

            <!-- Resignation group -->
            <h4 class="field-group-title">{{ t('form.group.resignation') }}</h4>
            <div class="form-grid compact">
              <div class="form-field"><label>{{ t('field.resignation.resignation_date') }}</label><input v-model="form.employment.resignation.resignation_date" type="date" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.resignation.last_working_date') }}</label><input v-model="form.employment.resignation.last_working_date" type="date" class="form-input" /></div>
              <div class="form-field long"><label>{{ t('field.resignation.reason') }}</label><textarea v-model="form.employment.resignation.reason" class="form-input" rows="2"></textarea></div>
            </div>
          </div>

          <!-- === PAYROLL TAB === -->
          <div v-show="activeTab === 'payroll'" class="tab-content">
            <h4 class="field-group-title">{{ t('form.group.payroll_bank') }}</h4>
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.bank_name') }}</label><input v-model="form.payroll.bank.bank_name" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.bank_branch') }}</label><input v-model="form.payroll.bank.branch_name" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.swift_code') }}</label><input v-model="form.payroll.bank.swift_code" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.bank_account_type') }}</label><select v-model="form.payroll.bank.account_type" class="form-input"><option value="">{{ t('action.select') }}</option><option value="savings">{{ t('bank_account_type.savings') }}</option><option value="checking">{{ t('bank_account_type.checking') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.bank_account_number') }}</label><input v-model="form.payroll.bank.account_number" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.bank_account_holder') }}</label><input v-model="form.payroll.bank.account_holder" class="form-input" /></div>
            </div>
            <div class="form-grid compact" style="margin-top: 14px">
              <div class="form-field"><label>{{ t('field.salary_type') }}</label><select v-model="form.payroll.salary_type" class="form-input"><option value="monthly">{{ t('salary_type.monthly') }}</option><option value="hourly">{{ t('salary_type.hourly') }}</option><option value="daily">{{ t('salary_type.daily') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.payroll_currency') }}</label><select v-model="form.payroll.payroll_currency" class="form-input"><option value="SGD">SGD</option><option value="JPY">JPY</option><option value="CNY">CNY</option><option value="USD">USD</option></select></div>
              <div class="form-field"><label>{{ t('field.monthly_base_salary') }}</label><input v-model="form.payroll.monthly_base_salary" type="number" step="0.01" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.hourly_wage') }}</label><input v-model="form.payroll.hourly_wage" type="number" step="0.01" class="form-input" /></div>
            </div>
          </div>

          <!-- === SKILLS TAB === -->
          <div v-show="activeTab === 'skills'" class="tab-content">
            <div class="form-grid">
              <div class="form-field"><label>{{ t('field.japanese_level') }}</label><select v-model="form.language_profile.japanese_level" class="form-input"><option value="">{{ t('action.select') }}</option><option value="N1">N1</option><option value="N2">N2</option><option value="N3">N3</option><option value="N4">N4</option><option value="N5">N5</option><option value="native">{{ t('japanese_level.native') }}</option><option value="none">{{ t('japanese_level.none') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.english_level') }}</label><select v-model="form.language_profile.english_level" class="form-input"><option value="">{{ t('action.select') }}</option><option value="native">{{ t('english_level.native') }}</option><option value="business">{{ t('english_level.business') }}</option><option value="intermediate">{{ t('english_level.intermediate') }}</option><option value="basic">{{ t('english_level.basic') }}</option><option value="none">{{ t('english_level.none') }}</option></select></div>
              <div class="form-field"><label>{{ t('field.primary_skill') }}</label><input v-model="form.skills_profile.primary_skill" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.secondary_skill') }}</label><input v-model="form.skills_profile.secondary_skill" class="form-input" /></div>
              <div class="form-field"><label>{{ t('field.years_of_experience') }}</label><input v-model="form.skills_profile.years_of_experience" class="form-input" /></div>
            </div>
          </div>

          <!-- Form Actions -->
          <div class="form-actions">
            <button type="submit" class="btn" :disabled="submitting">
              <template v-if="submitting">⏳ {{ t('action.saving') }}...</template>
              <template v-else>💾 {{ isEdit ? t('action.save') : t('action.create_employee') }}</template>
            </button>
            <a :href="isEdit ? `http://127.0.0.1:8004/employees/${employeeId}?lang=${lang}` : `http://127.0.0.1:8004/employees?lang=${lang}`" class="btn btn-secondary">{{ t('action.cancel') }}</a>
            <a v-if="isEdit" :href="`http://127.0.0.1:8004/employees/${employeeId}?lang=${lang}`" class="btn btn-secondary">{{ t('action.detail_inquiry') }}</a>
          </div>
        </form>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useEmployeeApi } from '../composables/useEmployeeApi.js'

const route = useRoute()
const { loading, error: loadError, fetchEmployee, createEmployee, updateEmployee } = useEmployeeApi()

const isEdit = computed(() => !!route.params.id)
const employeeId = computed(() => route.params.id)
const lang = computed(() => route.query.lang || 'zh')

const submitting = ref(false)
const apiError = ref('')
const validationErrors = ref([])
const fieldErrors = ref({})
const successMsg = ref('')
const activeTab = ref('profile')

// Dropdown options
const countryCodes = ['JP', 'CN', 'SG', 'US', 'TW', 'HK', 'KR', 'VN', 'TH', 'MY', 'PH', 'ID', 'IN', 'AU', 'GB', 'DE', 'FR']
const businessLines = ['recruitment', 'rpo', 'payroll', 'internal', 'consulting', 'it', 'dispatch']
// backend base
const baseUrl = 'http://127.0.0.1:8004'

const defaultForm = () => ({
  employee_number: '',
  profile: {
    name: { display_name: '', family_name: '', given_name: '', family_name_kana: '', given_name_kana: '', romaji_name: '' },
    gender: '', date_of_birth: '', nationality: '',
    email: '', email_p: '', phone: '',
    address: { country: 'Japan', postal_code: '', prefecture: '', city: '', street: '', building: '' },
    emergency_contact: { name: '', relationship: '', phone: '', email: '' },
  },
  employment: {
    entity_id: '', department_id: '', team_id: '',
    country_code: '', work_country: '', business_line: '',
    join_date: '', employment_type: 'employee', position: '', manager_employee_id: '',
    contract: { start_date: '', end_date: '' },
    office_location: '', assignment: '',
    status: 'active', probation_end_date: '',
    resignation: { resignation_date: '', last_working_date: '', reason: '' },
  },
  payroll: {
    salary_type: 'monthly', payroll_currency: 'SGD', monthly_base_salary: '', hourly_wage: '',
    bank: { bank_name: '', branch_name: '', swift_code: '', account_type: '', account_number: '', account_holder: '' },
  },
  language_profile: { japanese_level: '', english_level: '' },
  skills_profile: { primary_skill: '', secondary_skill: '', years_of_experience: '' },
  metadata: { profile_status: 'draft' },
})

const form = reactive(defaultForm())

const tabs = computed(() => [
  { key: 'profile', icon: '👤', label: t('section.profile') },
  { key: 'employment', icon: '💼', label: t('section.employment') },
  { key: 'payroll', icon: '💰', label: t('section.payroll') },
  { key: 'skills', icon: '🎓', label: t('section.skills_language') },
])

const translations = {
  zh: {
    'app.loading': '正在加载...', 'error.load_failed': '数据加载失败',
    'employee.create.title': '新增员工 / New Employee', 'employee.create.description': '填写以下信息创建新员工记录',
    'employee.edit.title': '编辑员工 / Edit Employee', 'employee.edit.description': '修改员工信息并保存',
    'employee.form.editing': '编辑中', 'employee.form.required_note': '* 标记为必填字段',
    'section.profile': '个人信息', 'section.employment': '雇佣信息', 'section.payroll': '薪资信息', 'section.skills_language': '技能与语言',
    'form.group.name': '姓名', 'form.group.personal': '个人信息', 'form.group.contact': '联系方式', 'form.group.address': '地址', 'form.group.emergency_contact': '紧急联系人',
    'form.group.employment_basics': '雇佣基本信息', 'form.group.labor_contract': '劳动合同', 'form.group.assignment': '岗位分配', 'form.group.resignation': '离职信息', 'form.group.payroll_bank': '银行信息',
    'action.create_employee': '创建员工', 'action.save': '保存修改', 'action.cancel': '取消', 'action.saving': '保存中', 'action.select': '— 请选择 —', 'action.back': '返回列表', 'action.detail_inquiry': '查看详情',
    'field.employee_number': '工号', 'field.name.display_name': '显示姓名', 'field.name.family_name': '姓', 'field.name.given_name': '名',
    'field.name.romaji_name': '罗马字姓名', 'field.name.family_name_kana': '姓（假名）', 'field.name.given_name_kana': '名（假名）',
    'field.gender': '性别', 'field.date_of_birth': '出生日期', 'field.nationality': '国籍',
    'field.email': '邮箱', 'field.email_p': '私人邮箱', 'field.phone': '电话',
    'field.address.postal_code': '邮编', 'field.address.prefecture': '都道府县', 'field.address.city': '城市', 'field.address.street': '街道', 'field.address.building': '楼栋',
    'field.emergency_contact.name': '紧急联系人姓名', 'field.emergency_contact.relationship': '关系', 'field.emergency_contact.phone': '紧急电话', 'field.emergency_contact.email': '紧急邮箱',
    'field.entity_id': '法人实体', 'field.department_id': '部门', 'field.team_id': '团队', 'field.position': '职位',
    'field.employment_type': '雇佣类型', 'field.status': '状态',
    'field.country_code': '国家代码', 'field.work_country': '工作国家', 'field.business_line': '业务线',
    'field.join_date': '入职日期', 'field.office_location': '办公地点', 'field.assignment': '岗位', 'field.manager_employee_id': '直属上级工号',
    'field.profile_status': '档案状态', 'field.probation_end_date': '试用期结束日',
    'field.contract.start_date': '合同开始日', 'field.contract.end_date': '合同结束日',
    'field.resignation.resignation_date': '离职日期', 'field.resignation.last_working_date': '最后工作日', 'field.resignation.reason': '离职原因',
    'field.salary_type': '薪资类型', 'field.payroll_currency': '薪资币种', 'field.monthly_base_salary': '月基本工资', 'field.hourly_wage': '时薪',
    'field.bank_name': '银行名称', 'field.bank_branch': '分行', 'field.bank_account_number': '银行账号', 'field.bank_account_holder': '账户持有人', 'field.bank_account_type': '账户类型', 'field.swift_code': 'SWIFT代码',
    'field.japanese_level': '日语水平', 'field.english_level': '英语水平', 'field.primary_skill': '主要技能', 'field.secondary_skill': '次要技能', 'field.years_of_experience': '经验年数',
    'gender.male': '男', 'gender.female': '女', 'gender.other': '其他',
    'status.active': '在职', 'status.probation': '试用期', 'status.on_leave': '休假中', 'status.resigned': '已离职', 'status.suspended': '停职',
    'employment_type.employee': '正式员工', 'employment_type.contractor': '合同工', 'employment_type.dispatch': '派遣', 'employment_type.part_time': '兼职', 'employment_type.intern': '实习生',
    'salary_type.monthly': '月薪', 'salary_type.hourly': '时薪', 'salary_type.daily': '日薪',
    'bank_account_type.savings': '储蓄账户', 'bank_account_type.checking': '支票账户',
    'japanese_level.native': '母语', 'japanese_level.none': '无',
    'english_level.native': 'Native', 'english_level.business': 'Business', 'english_level.intermediate': 'Intermediate', 'english_level.basic': 'Basic', 'english_level.none': 'None',
    'employment.labor_contract_note': '劳动合同日期为非必填，用于合同续签提醒。默认隐藏已离职员工。',
  },
  en: {
    'app.loading': 'Loading...', 'error.load_failed': 'Failed to load data',
    'employee.create.title': 'New Employee', 'employee.create.description': 'Fill in information to create a new employee record',
    'employee.edit.title': 'Edit Employee', 'employee.edit.description': 'Modify employee information',
    'employee.form.editing': 'Editing', 'employee.form.required_note': '* indicates required field',
    'section.profile': 'Profile', 'section.employment': 'Employment', 'section.payroll': 'Payroll', 'section.skills_language': 'Skills & Language',
    'form.group.name': 'Name', 'form.group.personal': 'Personal', 'form.group.contact': 'Contact', 'form.group.address': 'Address', 'form.group.emergency_contact': 'Emergency Contact',
    'form.group.employment_basics': 'Employment Basics', 'form.group.labor_contract': 'Labor Contract', 'form.group.assignment': 'Assignment', 'form.group.resignation': 'Resignation', 'form.group.payroll_bank': 'Bank Info',
    'action.create_employee': 'Create Employee', 'action.save': 'Save Changes', 'action.cancel': 'Cancel', 'action.saving': 'Saving', 'action.select': '— Select —', 'action.back': 'Back to List', 'action.detail_inquiry': 'View Detail',
    'field.employee_number': 'Employee No', 'field.name.display_name': 'Display Name', 'field.name.family_name': 'Family Name', 'field.name.given_name': 'Given Name',
    'field.name.romaji_name': 'Romaji Name', 'field.name.family_name_kana': 'Family Name (Kana)', 'field.name.given_name_kana': 'Given Name (Kana)',
    'field.gender': 'Gender', 'field.date_of_birth': 'Date of Birth', 'field.nationality': 'Nationality',
    'field.email': 'Email', 'field.email_p': 'Personal Email', 'field.phone': 'Phone',
    'field.address.postal_code': 'Postal Code', 'field.address.prefecture': 'Prefecture', 'field.address.city': 'City', 'field.address.street': 'Street', 'field.address.building': 'Building',
    'field.emergency_contact.name': 'Emergency Contact Name', 'field.emergency_contact.relationship': 'Relationship', 'field.emergency_contact.phone': 'Emergency Phone', 'field.emergency_contact.email': 'Emergency Email',
    'field.entity_id': 'Entity', 'field.department_id': 'Department', 'field.team_id': 'Team', 'field.position': 'Position',
    'field.employment_type': 'Emp. Type', 'field.status': 'Status',
    'field.country_code': 'Country Code', 'field.work_country': 'Work Country', 'field.business_line': 'Business Line',
    'field.join_date': 'Join Date', 'field.office_location': 'Office Location', 'field.assignment': 'Assignment', 'field.manager_employee_id': 'Manager ID',
    'field.profile_status': 'Profile Status', 'field.probation_end_date': 'Probation End',
    'field.contract.start_date': 'Contract Start', 'field.contract.end_date': 'Contract End',
    'field.resignation.resignation_date': 'Resignation Date', 'field.resignation.last_working_date': 'Last Working Date', 'field.resignation.reason': 'Reason',
    'field.salary_type': 'Salary Type', 'field.payroll_currency': 'Currency', 'field.monthly_base_salary': 'Monthly Base', 'field.hourly_wage': 'Hourly Wage',
    'field.bank_name': 'Bank Name', 'field.bank_branch': 'Branch', 'field.bank_account_number': 'Account No', 'field.bank_account_holder': 'Account Holder', 'field.bank_account_type': 'Account Type', 'field.swift_code': 'SWIFT',
    'field.japanese_level': 'Japanese', 'field.english_level': 'English', 'field.primary_skill': 'Primary Skill', 'field.secondary_skill': 'Secondary Skill', 'field.years_of_experience': 'Years of Exp.',
    'gender.male': 'Male', 'gender.female': 'Female', 'gender.other': 'Other',
    'status.active': 'Active', 'status.probation': 'Probation', 'status.on_leave': 'On Leave', 'status.resigned': 'Resigned', 'status.suspended': 'Suspended',
    'employment_type.employee': 'Employee', 'employment_type.contractor': 'Contractor', 'employment_type.dispatch': 'Dispatch', 'employment_type.part_time': 'Part-time', 'employment_type.intern': 'Intern',
    'salary_type.monthly': 'Monthly', 'salary_type.hourly': 'Hourly', 'salary_type.daily': 'Daily',
    'bank_account_type.savings': 'Savings', 'bank_account_type.checking': 'Checking',
    'japanese_level.native': 'Native', 'japanese_level.none': 'None',
    'english_level.native': 'Native', 'english_level.business': 'Business', 'english_level.intermediate': 'Intermediate', 'english_level.basic': 'Basic', 'english_level.none': 'None',
    'employment.labor_contract_note': 'Labor contract dates are optional and used for renewal reminders. Resigned employees are hidden by default.',
  },
  ja: {
    'app.loading': '読み込み中...', 'error.load_failed': 'データの読み込みに失敗しました',
    'employee.create.title': '新規従業員登録', 'employee.create.description': '以下を入力して新しい従業員を登録',
    'employee.edit.title': '従業員編集', 'employee.edit.description': '従業員情報を修正',
    'employee.form.editing': '編集中', 'employee.form.required_note': '* 必須項目',
    'section.profile': 'プロフィール', 'section.employment': '雇用情報', 'section.payroll': '給与情報', 'section.skills_language': 'スキル・言語',
    'form.group.name': '氏名', 'form.group.personal': '個人情報', 'form.group.contact': '連絡先', 'form.group.address': '住所', 'form.group.emergency_contact': '緊急連絡先',
    'form.group.employment_basics': '雇用基本情報', 'form.group.labor_contract': '労働契約', 'form.group.assignment': '配属', 'form.group.resignation': '退職情報', 'form.group.payroll_bank': '銀行情報',
    'action.create_employee': '登録する', 'action.save': '保存する', 'action.cancel': 'キャンセル', 'action.saving': '保存中', 'action.select': '— 選択 —', 'action.back': '一覧に戻る', 'action.detail_inquiry': '詳細を見る',
    'field.employee_number': '社員番号', 'field.name.display_name': '表示名', 'field.name.family_name': '姓', 'field.name.given_name': '名',
    'field.name.romaji_name': 'ローマ字', 'field.name.family_name_kana': '姓（カナ）', 'field.name.given_name_kana': '名（カナ）',
    'field.gender': '性別', 'field.date_of_birth': '生年月日', 'field.nationality': '国籍',
    'field.email': 'メール', 'field.email_p': '個人メール', 'field.phone': '電話',
    'field.address.postal_code': '郵便番号', 'field.address.prefecture': '都道府県', 'field.address.city': '市区町村', 'field.address.street': '番地', 'field.address.building': '建物',
    'field.emergency_contact.name': '緊急連絡先氏名', 'field.emergency_contact.relationship': '続柄', 'field.emergency_contact.phone': '緊急電話', 'field.emergency_contact.email': '緊急メール',
    'field.entity_id': '法人', 'field.department_id': '部署', 'field.team_id': 'チーム', 'field.position': '役職',
    'field.employment_type': '雇用形態', 'field.status': 'ステータス',
    'field.country_code': '国コード', 'field.work_country': '勤務国', 'field.business_line': '事業ライン',
    'field.join_date': '入社日', 'field.office_location': '勤務地', 'field.assignment': '配属先', 'field.manager_employee_id': '上司社員番号',
    'field.profile_status': 'プロフィール状態', 'field.probation_end_date': '試用期間終了日',
    'field.contract.start_date': '契約開始日', 'field.contract.end_date': '契約終了日',
    'field.resignation.resignation_date': '退職日', 'field.resignation.last_working_date': '最終勤務日', 'field.resignation.reason': '退職理由',
    'field.salary_type': '給与タイプ', 'field.payroll_currency': '通貨', 'field.monthly_base_salary': '月額基本給', 'field.hourly_wage': '時給',
    'field.bank_name': '銀行名', 'field.bank_branch': '支店', 'field.bank_account_number': '口座番号', 'field.bank_account_holder': '口座名義', 'field.bank_account_type': '口座種類', 'field.swift_code': 'SWIFTコード',
    'field.japanese_level': '日本語', 'field.english_level': '英語', 'field.primary_skill': '主スキル', 'field.secondary_skill': '副スキル', 'field.years_of_experience': '経験年数',
    'gender.male': '男性', 'gender.female': '女性', 'gender.other': 'その他',
    'status.active': '在職中', 'status.probation': '試用期間', 'status.on_leave': '休職中', 'status.resigned': '退職済', 'status.suspended': '停職中',
    'employment_type.employee': '正社員', 'employment_type.contractor': '契約社員', 'employment_type.dispatch': '派遣', 'employment_type.part_time': 'パート', 'employment_type.intern': 'インターン',
    'salary_type.monthly': '月給', 'salary_type.hourly': '時給', 'salary_type.daily': '日給',
    'bank_account_type.savings': '普通', 'bank_account_type.checking': '当座',
    'japanese_level.native': '母国語', 'japanese_level.none': 'なし',
    'english_level.native': 'Native', 'english_level.business': 'Business', 'english_level.intermediate': 'Intermediate', 'english_level.basic': 'Basic', 'english_level.none': 'None',
    'employment.labor_contract_note': '労働契約日は任意項目です。契約更新リマインダーに使用されます。退職者はデフォルトで非表示です。',
  },
}

function t(key) { return translations[lang.value]?.[key] || translations.en[key] || key }

function populateForm(data) {
  if (!data) return
  form.employee_number = data.employee_number || ''
  if (data.profile) {
    if (data.profile.name) form.profile.name = { ...form.profile.name, ...data.profile.name }
    form.profile.gender = data.profile.gender || ''
    form.profile.date_of_birth = data.profile.date_of_birth || ''
    form.profile.nationality = data.profile.nationality || ''
    form.profile.email = data.profile.email || ''
    form.profile.email_p = data.profile.email_p || ''
    form.profile.phone = data.profile.phone || ''
    if (data.profile.address) form.profile.address = { ...form.profile.address, ...data.profile.address }
    if (data.profile.emergency_contact) form.profile.emergency_contact = { ...form.profile.emergency_contact, ...data.profile.emergency_contact }
  }
  if (data.employment) {
    form.employment.country_code = data.employment.country_code || ''
    form.employment.work_country = data.employment.work_country || ''
    form.employment.business_line = data.employment.business_line || ''
    form.employment.join_date = data.employment.join_date || ''
    form.employment.entity_id = data.employment.entity_id || ''
    form.employment.department_id = data.employment.department_id || ''
    form.employment.team_id = data.employment.team_id || ''
    form.employment.position = data.employment.position || ''
    form.employment.manager_employee_id = data.employment.manager_employee_id || ''
    form.employment.employment_type = data.employment.employment_type || 'employee'
    form.employment.status = data.employment.status || 'active'
    form.employment.office_location = data.employment.office_location || ''
    form.employment.assignment = data.employment.assignment || ''
    form.employment.probation_end_date = data.employment.probation_end_date || ''
    if (data.employment.contract) form.employment.contract = { ...form.employment.contract, ...data.employment.contract }
    if (data.employment.resignation) form.employment.resignation = { ...form.employment.resignation, ...data.employment.resignation }
  }
  if (data.payroll) {
    form.payroll.salary_type = data.payroll.salary_type || 'monthly'
    form.payroll.payroll_currency = data.payroll.payroll_currency || 'SGD'
    form.payroll.monthly_base_salary = data.payroll.monthly_base_salary || ''
    form.payroll.hourly_wage = data.payroll.hourly_wage || ''
    if (data.payroll.bank) form.payroll.bank = { ...form.payroll.bank, ...data.payroll.bank }
  }
  if (data.language_profile) form.language_profile = { ...form.language_profile, ...data.language_profile }
  if (data.skills_profile) form.skills_profile = { ...form.skills_profile, ...data.skills_profile }
  if (data.metadata) form.metadata = { ...form.metadata, ...data.metadata }
}

async function handleSubmit() {
  submitting.value = true; apiError.value = ''; validationErrors.value = []; fieldErrors.value = {}; successMsg.value = ''

  const payload = {
    employee_number: form.employee_number,
    profile: {
      name: { ...form.profile.name },
      gender: form.profile.gender, date_of_birth: form.profile.date_of_birth, nationality: form.profile.nationality,
      email: form.profile.email, email_p: form.profile.email_p, phone: form.profile.phone,
      address: { ...form.profile.address },
      emergency_contact: { ...form.profile.emergency_contact },
    },
    employment: {
      ...form.employment,
      contract: { ...form.employment.contract },
      resignation: { ...form.employment.resignation },
    },
    payroll: { salary_type: form.payroll.salary_type, payroll_currency: form.payroll.payroll_currency, monthly_base_salary: form.payroll.monthly_base_salary, hourly_wage: form.payroll.hourly_wage, bank: { ...form.payroll.bank } },
    language_profile: { ...form.language_profile },
    skills_profile: { ...form.skills_profile },
    metadata: { ...form.metadata },
  }

  const result = isEdit.value ? await updateEmployee(employeeId.value, payload) : await createEmployee(payload)

  if (result.error) {
    apiError.value = result.error; validationErrors.value = result.validation_errors || []
    if (result.field_errors) fieldErrors.value = result.field_errors
    submitting.value = false; return
  }

  successMsg.value = result.message || (isEdit.value ? 'Employee updated' : 'Employee created')
  submitting.value = false
  setTimeout(() => {
    const targetUrl = isEdit.value
      ? `http://127.0.0.1:8004/employees/${employeeId.value}?lang=${lang.value}`
      : `http://127.0.0.1:8004/employees?lang=${lang.value}`
    window.location.href = targetUrl
  }, 1500)
}

onMounted(async () => {
  if (isEdit.value) {
    const result = await fetchEmployee(employeeId.value, lang.value)
    if (result && !result.error) populateForm(result)
  }
})
</script>

<style scoped>
.employee-form-page { max-width: 900px; margin: 0 auto; }

.object-page { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 24px 28px; }

.form-header-section { margin-bottom: 12px; }
.form-header-section h2 { margin: 0 0 4px; font-size: 20px; color: var(--navy); }
.form-header-section .muted { margin: 0; font-size: 13px; }

.success-strip { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; padding: 12px 18px; border-radius: 10px; margin-bottom: 16px; font-weight: 650; }
.error-strip { background: #fff5f5; border: 1px solid #fecaca; color: #991b1b; padding: 12px 18px; border-radius: 10px; margin-bottom: 16px; }
.error-strip ul { margin: 4px 0 0; padding-left: 20px; font-size: 13px; }

.required-note { color: var(--muted); font-size: 12px; margin: 0 0 14px; }

.form-tabs { display: flex; gap: 4px; margin-bottom: 16px; background: #f8fafc; border: 1px solid var(--line); border-radius: 10px; padding: 5px; }
.tab-btn { flex: 1; padding: 9px 14px; border: none; border-radius: 7px; background: transparent; font-size: 13px; font-weight: 650; color: var(--muted); cursor: pointer; transition: all 0.15s; }
.tab-btn:hover { background: #eef2f7; color: var(--text); }
.tab-btn.active { background: var(--blue); color: #fff; }

.tab-content { margin-bottom: 8px; }

.field-group-title { font-size: 13px; color: var(--navy); margin: 16px 0 8px; padding-bottom: 6px; border-bottom: 1px solid #f0f2f5; font-weight: 750; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px 18px; }
.form-grid.compact { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }

.form-field { display: flex; flex-direction: column; gap: 3px; }
.form-field label { font-size: 13px; font-weight: 650; color: var(--navy); }
.form-field .required { color: var(--red); }
.form-field .field-err { font-size: 12px; color: var(--red); margin-top: 2px; }
.form-field.long { grid-column: 1 / -1; }

.form-input { width: 100%; padding: 8px 12px; border: 1px solid var(--line); border-radius: 7px; font-size: 14px; background: #fff; font-family: inherit; }
.form-input:focus { outline: none; border-color: var(--blue); box-shadow: 0 0 0 3px var(--primary-light); }
textarea.form-input { resize: vertical; }

.long.muted { grid-column: 1 / -1; font-size: 12px; margin-top: 4px; }

.form-actions { display: flex; gap: 10px; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--line); }

@media (max-width: 760px) {
  .object-page { padding: 16px; }
  .form-tabs { flex-wrap: wrap; }
  .tab-btn { flex: 1 1 45%; font-size: 12px; }
  .form-grid, .form-grid.compact { grid-template-columns: 1fr; }
}
</style>
