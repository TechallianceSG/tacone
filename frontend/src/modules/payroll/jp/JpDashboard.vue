<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const socialInsurance = ref<any[]>([])
const remunerationGrades = ref<any[]>([])
const taxBrackets = ref<any[]>([])
const accidentInsurance = ref<any[]>([])

const healthGrades = computed(() => remunerationGrades.value.filter(r => r.grade_type === 'health_insurance'))
const pensionGrades = computed(() => remunerationGrades.value.filter(r => r.grade_type === 'pension_insurance'))
const monthlyTax = computed(() => taxBrackets.value.filter(r => r.table_type === 'monthly'))
const dailyTax = computed(() => taxBrackets.value.filter(r => r.table_type === 'daily'))

const rateTypeLabels: Record<string, string> = {
  health_insurance: '健康保険', pension: '厚生年金保険', pension_insurance: '厚生年金保険',
  nursing_care: '介護保険', care_insurance: '介護保険', employment: '雇用保険',
  employment_insurance: '雇用保険', child_allowance: '児童手当拠出金',
}

async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.parameters()
    const all = res.data.data?.items || res.data.data || []
    socialInsurance.value = all.filter((p: any) =>
      ['social_insurance','health_insurance','pension','pension_insurance','nursing_care','care_insurance','employment','employment_insurance','child_allowance'].includes(p.rate_type)
    )
    remunerationGrades.value = all.filter((p: any) =>
      p.grade_type === 'health_insurance' || p.grade_type === 'pension_insurance'
    ).sort((a: any, b: any) => (a.grade_type||'')>(b.grade_type||'')?1:-1||(a.grade_number||0)-(b.grade_number||0))
    taxBrackets.value = all.filter((p: any) =>
      p.table_type === 'monthly' || p.table_type === 'daily'
    ).sort((a: any, b: any) => (a.min_salary||0)-(b.min_salary||0))
    accidentInsurance.value = all.filter((p: any) =>
      p.industry_code !== undefined
    ).sort((a: any, b: any) => (a.industry_code||'')>(b.industry_code||'')?1:-1)
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function fmtPct(val: any): string { const n=Number(val); return isNaN(n)?'-':n.toFixed(2)+'%' }
function fmtPermille(val: any): string { const n=Number(val); return isNaN(n)?'-':(n*1000).toFixed(2)+'‰' }
function fmtNum(val: any): string { const n=Number(val); return isNaN(n)?'-':n.toLocaleString() }
function prefectureLabel(code: string): string { return code || t('payroll.jp.national') }

const navCards = [
  { icon:'👥', title:'payroll.jp.employees', desc:'payroll.jp.employees_desc', route:'/payroll/jp/employees', color:'#0f766e' },
  { icon:'📅', title:'payroll.jp.monthly_sheets', desc:'payroll.jp.batches_desc', route:'/payroll/jp/batches', color:'#e65100' },
  { icon:'📄', title:'payroll.jp.payslips', desc:'payroll.jp.payslips_desc', route:'/payroll/jp/payslips', color:'#6a1b9a' },
  { icon:'⚙️', title:'payroll.jp.parameters', desc:'payroll.jp.parameters_desc', route:'/payroll/jp/parameters', color:'#1565c0' },
]

function goTo(route: string) { router.push(route) }
function scrollTo(id: string) { document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'}) }

onMounted(load)
</script>

<template>
  <div class="fiori-page">
    <!-- Hero -->
    <div class="fiori-hero">
      <div>
        <h1>{{ t('payroll.jp.title') }}</h1>
        <p>{{ t('payroll.jp.desc') }}</p>
      </div>
      <el-tag type="info" size="large" effect="plain">FY2026 (Reiwa 8)</el-tag>
    </div>

    <!-- Module Cards -->
    <div class="fiori-tiles">
      <div v-for="card in navCards" :key="card.route" class="fiori-tile" :style="{borderLeftColor:card.color}" @click="goTo(card.route)">
        <span class="tile-icon">{{ card.icon }}</span>
        <div>
          <div class="tile-title">{{ t(card.title) }}</div>
          <div class="tile-desc">{{ t(card.desc) }}</div>
        </div>
      </div>
    </div>

    <!-- Quick Nav -->
    <div class="fiori-quicknav">
      <el-button text size="small" @click="scrollTo('social-insurance')">🏥 {{ t('payroll.jp.social_insurance') }}</el-button>
      <el-button text size="small" @click="scrollTo('grades')">📊 {{ t('payroll.jp.remuneration_grades') }}</el-button>
      <el-button text size="small" @click="scrollTo('tax')">📑 {{ t('payroll.jp.tax_brackets') }}</el-button>
      <el-button text size="small" @click="scrollTo('accident')">🏭 {{ t('payroll.jp.accident_insurance') }}</el-button>
    </div>

    <div v-loading="loading" element-loading-text="Loading...">
      <!-- 1. Social Insurance -->
      <div id="social-insurance" class="fiori-section">
        <div class="section-head">
          <h2>🏥 {{ t('payroll.jp.social_insurance') }}</h2>
          <span class="section-count">{{ socialInsurance.length }} {{ t('action.records_total') }}</span>
        </div>
        <div class="fiori-card">
          <el-table :data="socialInsurance" border stripe size="small" max-height="360" v-if="socialInsurance.length">
            <el-table-column :label="t('field.rate_type')" width="200">
              <template #default="{row}">{{ rateTypeLabels[row.rate_type] || row.rate_type }}</template>
            </el-table-column>
            <el-table-column :label="t('field.prefecture')" width="100">
              <template #default="{row}">{{ prefectureLabel(row.prefecture) }}</template>
            </el-table-column>
            <el-table-column :label="t('field.employee_rate')" width="120" align="right">
              <template #default="{row}">{{ fmtPct(row.employee_rate) }}</template>
            </el-table-column>
            <el-table-column :label="t('field.employer_rate')" width="120" align="right">
              <template #default="{row}">{{ fmtPct(row.employer_rate) }}</template>
            </el-table-column>
            <el-table-column prop="applicable_from" :label="t('field.applicable_from')" width="130" />
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
      </div>

      <!-- 2. Remuneration Grades -->
      <div id="grades" class="fiori-section">
        <div class="section-head">
          <h2>📊 {{ t('payroll.jp.remuneration_grades') }}</h2>
          <span class="section-count">{{ remunerationGrades.length }} grades</span>
        </div>
        <h3 class="subsection-title">🏥 健康保険 (Health) <span class="count-badge">{{ healthGrades.length }}</span></h3>
        <div class="fiori-card">
          <el-table :data="healthGrades.slice(0,50)" border stripe size="small" max-height="360" v-if="healthGrades.length">
            <el-table-column prop="grade_number" :label="t('field.grade_number')" width="70" align="center" />
            <el-table-column :label="t('field.min_monthly_amount')" width="150" align="right">
              <template #default="{row}">{{ row.min_monthly_amount?'¥'+fmtNum(row.min_monthly_amount):'-' }}</template>
            </el-table-column>
            <el-table-column :label="t('field.max_monthly_amount')" width="150" align="right">
              <template #default="{row}">{{ row.max_monthly_amount?'¥'+fmtNum(row.max_monthly_amount):'-' }}</template>
            </el-table-column>
            <el-table-column :label="t('field.standard_monthly_amount')" width="170" align="right">
              <template #default="{row}"><strong>{{ row.standard_monthly_amount?'¥'+fmtNum(row.standard_monthly_amount):'-' }}</strong></template>
            </el-table-column>
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
        <h3 class="subsection-title">🏦 厚生年金 (Pension) <span class="count-badge">{{ pensionGrades.length }}</span></h3>
        <div class="fiori-card">
          <el-table :data="pensionGrades.slice(0,50)" border stripe size="small" max-height="360" v-if="pensionGrades.length">
            <el-table-column prop="grade_number" :label="t('field.grade_number')" width="70" align="center" />
            <el-table-column :label="t('field.min_monthly_amount')" width="150" align="right">
              <template #default="{row}">{{ row.min_monthly_amount?'¥'+fmtNum(row.min_monthly_amount):'-' }}</template>
            </el-table-column>
            <el-table-column :label="t('field.max_monthly_amount')" width="150" align="right">
              <template #default="{row}">{{ row.max_monthly_amount?'¥'+fmtNum(row.max_monthly_amount):'-' }}</template>
            </el-table-column>
            <el-table-column :label="t('field.standard_monthly_amount')" width="170" align="right">
              <template #default="{row}"><strong>{{ row.standard_monthly_amount?'¥'+fmtNum(row.standard_monthly_amount):'-' }}</strong></template>
            </el-table-column>
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
      </div>

      <!-- 3. Tax Brackets -->
      <div id="tax" class="fiori-section">
        <div class="section-head">
          <h2>📑 {{ t('payroll.jp.tax_brackets') }}</h2>
          <span class="section-count">{{ taxBrackets.length }} brackets</span>
        </div>
        <h3 class="subsection-title">📅 月額表 (Monthly) <span class="count-badge">{{ monthlyTax.length }}</span></h3>
        <div class="fiori-card">
          <el-table :data="monthlyTax" border stripe size="small" max-height="420" v-if="monthlyTax.length">
            <el-table-column :label="t('field.min_salary')+' - '+t('field.max_salary')" width="200" fixed>
              <template #default="{row}">¥{{ fmtNum(row.min_salary) }} - ¥{{ fmtNum(row.max_salary) }}</template>
            </el-table-column>
            <el-table-column v-for="n in 8" :key="n" :label="t('field.tax_dep_'+(n-1))" width="95" align="right">
              <template #default="{row}">{{ row['tax_dep_'+(n-1)]!=null?'¥'+fmtNum(row['tax_dep_'+(n-1)]):'-' }}</template>
            </el-table-column>
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
        <h3 class="subsection-title">📆 日額表 (Daily) <span class="count-badge">{{ dailyTax.length }}</span></h3>
        <div class="fiori-card">
          <el-table :data="dailyTax" border stripe size="small" max-height="360" v-if="dailyTax.length">
            <el-table-column :label="t('field.min_salary')+' - '+t('field.max_salary')" width="200" fixed>
              <template #default="{row}">¥{{ fmtNum(row.min_salary) }} - ¥{{ fmtNum(row.max_salary) }}</template>
            </el-table-column>
            <el-table-column v-for="n in 8" :key="n" :label="t('field.tax_dep_'+(n-1))" width="95" align="right">
              <template #default="{row}">{{ row['tax_dep_'+(n-1)]!=null?'¥'+fmtNum(row['tax_dep_'+(n-1)]):'-' }}</template>
            </el-table-column>
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
      </div>

      <!-- 4. Accident Insurance -->
      <div id="accident" class="fiori-section">
        <div class="section-head">
          <h2>🏭 {{ t('payroll.jp.accident_insurance') }}</h2>
          <span class="section-count">{{ accidentInsurance.length }} {{ t('action.records_total') }}</span>
        </div>
        <div class="fiori-card">
          <el-table :data="accidentInsurance" border stripe size="small" max-height="360" v-if="accidentInsurance.length">
            <el-table-column prop="industry_code" :label="t('field.industry_code')" width="120">
              <template #default="{row}"><el-tag size="small" effect="dark" type="success">{{ row.industry_code }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="industry_name_ja" :label="t('payroll.jp.accident_insurance')+' (JA)'" min-width="260" show-overflow-tooltip />
            <el-table-column prop="industry_name_en" :label="t('field.industry_name_en')" min-width="230" show-overflow-tooltip>
              <template #default="{row}">{{ row.industry_name_en||'-' }}</template>
            </el-table-column>
            <el-table-column :label="t('field.rate')" width="110" align="right">
              <template #default="{row}">{{ fmtPermille(row.rate) }}</template>
            </el-table-column>
          </el-table>
          <div v-else class="fiori-empty">{{ t('payroll.jp.no_records') }}</div>
        </div>
      </div>
    </div>
    <div class="fiori-footer">{{ t('payroll.jp.title') }} — {{ t('payroll.jp.parameters_desc') }}</div>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1500px; margin: 0 auto; padding: 28px 24px; font-size: 15px; }
.fiori-hero { background: linear-gradient(135deg,#0f2b46,#1a4a7a); color:#fff; padding: 24px 28px; border-radius: 12px 12px 0 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }
.fiori-hero h1 { margin:0; font-size: 1.4rem; font-weight: 700; }
.fiori-hero p { margin:4px 0 0; opacity:.85; font-size: .92rem; }

.fiori-tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; padding-top:18px; margin-bottom:22px; }
.fiori-tile { display:flex; align-items:flex-start; gap:14px; background:#fff; border:1px solid #e5e7eb; border-left:4px solid #1B6CB2; border-radius:10px; padding:18px 20px; cursor:pointer; transition:all .15s; }
.fiori-tile:hover { border-color:#1B6CB2; box-shadow:0 2px 12px rgba(27,108,178,.1); transform:translateY(-1px); }
.tile-icon { font-size:1.7rem; flex-shrink:0; margin-top:2px; }
.tile-title { font-size:1rem; font-weight:700; color:#1d2a3a; margin-bottom:3px; }
.tile-desc { font-size:.85rem; color:#6b7280; }

.fiori-quicknav { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:24px; padding:10px 16px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; }

.fiori-section { margin-bottom:32px; }
.section-head { display:flex; align-items:center; gap:12px; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid #1B6CB2; }
.section-head h2 { margin:0; font-size:1.15rem; font-weight:700; color:#1d2a3a; }
.section-count { font-size:.85rem; color:#6b7280; }
.subsection-title { font-size:.95rem; font-weight:700; margin:16px 0 8px; color:#1d2a3a; }
.count-badge { display:inline-block; background:#e8f0fe; color:#1B6CB2; padding:1px 8px; border-radius:10px; font-size:.78rem; font-weight:600; margin-left:6px; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.fiori-empty { text-align:center; color:#9ca3af; padding:28px; font-size:.9rem; }
.fiori-footer { text-align:center; color:#9ca3af; font-size:.82rem; padding:14px; margin-top:20px; border-top:1px solid #e5e7eb; }
</style>
