<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { useDictOptions } from '@/composables/useDictOptions'
import { ElMessage } from 'element-plus'
import { prefectures, prefectureLabel } from '@/constants/prefectures'
import { usePayrollJpConstants } from '@/composables/usePayrollJpConstants'

const { t } = useI18n()
const { rateTypeLabelMap, parameterTypes, init: initConstants } = usePayrollJpConstants()

// ── Tab state ──
const activeTab = ref('social-insurance')
const loading = ref(false)
const allParams = ref<any[]>([])

// ── Data Dictionary ──
const CAT = { TAX_TABLE: 'tax_table_type' }
const { loadOptions, getOptions } = useDictOptions()
const FALLBACK_DD: Record<string, string[]> = {
  [CAT.TAX_TABLE]: ['monthly', 'daily', 'bonus'],
}
function ddValues(catCode: string): string[] {
  const dd = getOptions(catCode).value.map(o => o.value)
  return dd.length > 0 ? dd : FALLBACK_DD[catCode] || []
}
function ddLabel(catCode: string, val: string): string {
  const opt = getOptions(catCode).value.find(o => o.value === val)
  return opt?.label || val
}

// ── Social Insurance ──
const siLoading = ref(false)
const siDialog = ref(false)
const siForm = ref<Record<string, any>>({ is_current: true })
const siSaving = ref(false)
const siPage = ref(1)
const siPageSize = ref(20)

const socialInsuranceData = computed(() =>
  allParams.value.filter((p: any) =>
    p.param_type === parameterTypes.value.SOCIAL_INSURANCE_RATE || p.rate_type !== undefined
  )
)

const siPaged = computed(() => {
  const start = (siPage.value - 1) * siPageSize.value
  return socialInsuranceData.value.slice(start, start + siPageSize.value)
})

// ── Tax Brackets ──
const tbLoading = ref(false)
const tbDialog = ref(false)
const tbForm = ref<Record<string, any>>({})
const tbSaving = ref(false)
const tbPage = ref(1)
const tbPageSize = ref(20)

const taxBracketData = computed(() =>
  allParams.value.filter((p: any) =>
    p.param_type === parameterTypes.value.WITHHOLDING_TAX_BRACKET || (p.table_type && p.min_salary !== undefined)
  )
)

const tbPaged = computed(() => {
  const start = (tbPage.value - 1) * tbPageSize.value
  return taxBracketData.value.slice(start, start + tbPageSize.value)
})

// ── Remuneration Grades ──
const rgLoading = ref(false)
const rgDialog = ref(false)
const rgForm = ref<Record<string, any>>({})
const rgSaving = ref(false)
const rgPage = ref(1)
const rgPageSize = ref(20)

const remunerationGradeData = computed(() =>
  allParams.value.filter((p: any) =>
    p.param_type === parameterTypes.value.STANDARD_REMUNERATION_GRADE || p.grade_type !== undefined
  )
)

const rgPaged = computed(() => {
  const start = (rgPage.value - 1) * rgPageSize.value
  return remunerationGradeData.value.slice(start, start + rgPageSize.value)
})

// ── Accident Insurance ──
const aiLoading = ref(false)
const aiDialog = ref(false)
const aiForm = ref<Record<string, any>>({})
const aiSaving = ref(false)
const aiPage = ref(1)
const aiPageSize = ref(20)

const accidentInsuranceData = computed(() =>
  allParams.value.filter((p: any) =>
    p.param_type === parameterTypes.value.ACCIDENT_INSURANCE_RATE || p.industry_code !== undefined
  )
)

const aiPaged = computed(() => {
  const start = (aiPage.value - 1) * aiPageSize.value
  return accidentInsuranceData.value.slice(start, start + aiPageSize.value)
})

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.parameters()
    allParams.value = res.data.data || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

// Helper: format rate as percentage
function fmtPct(val: any, decimals = 2): string {
  const n = Number(val)
  if (isNaN(n)) return '-'
  return n.toFixed(decimals) + '%'
}

function fmtPermille(val: any): string {
  const n = Number(val)
  if (isNaN(n)) return '-'
  return (n * 1000).toFixed(2) + '‰'
}

// ── Social Insurance CRUD ──
function openSiCreate() {
  siForm.value = {
    param_type: parameterTypes.value.SOCIAL_INSURANCE_RATE,
    rate_type: 'health_insurance',
    prefecture: '',
    employee_rate: 0,
    employer_rate: 0,
    applicable_from: '',
    is_current: true,
  }
  siDialog.value = true
}

function openSiEdit(row: any) {
  siForm.value = { ...row }
  siDialog.value = true
}

async function saveSi() {
  siSaving.value = true
  try {
    await payrollJpApi.saveParameter(siForm.value)
    siDialog.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { siSaving.value = false }
}

// ── Tax Bracket CRUD ──
function openTbCreate() {
  tbForm.value = {
    param_type: parameterTypes.value.WITHHOLDING_TAX_BRACKET,
    table_type: 'monthly',
    min_salary: 0,
    max_salary: 0,
    tax_dep_0: 0, tax_dep_1: 0, tax_dep_2: 0, tax_dep_3: 0,
    tax_dep_4: 0, tax_dep_5: 0, tax_dep_6: 0, tax_dep_7: 0,
    is_current: true,
  }
  tbDialog.value = true
}

function openTbEdit(row: any) {
  tbForm.value = { ...row }
  tbDialog.value = true
}

async function saveTb() {
  tbSaving.value = true
  try {
    await payrollJpApi.saveParameter(tbForm.value)
    tbDialog.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { tbSaving.value = false }
}

// ── Remuneration Grade CRUD ──
function openRgCreate() {
  rgForm.value = {
    param_type: parameterTypes.value.STANDARD_REMUNERATION_GRADE,
    grade_type: '',
    grade_number: 0,
    min_monthly_amount: 0,
    max_monthly_amount: 0,
    standard_monthly_amount: 0,
    is_current: true,
  }
  rgDialog.value = true
}

function openRgEdit(row: any) {
  rgForm.value = { ...row }
  rgDialog.value = true
}

async function saveRg() {
  rgSaving.value = true
  try {
    await payrollJpApi.saveParameter(rgForm.value)
    rgDialog.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { rgSaving.value = false }
}

// ── Accident Insurance CRUD ──
function openAiCreate() {
  aiForm.value = {
    param_type: parameterTypes.value.ACCIDENT_INSURANCE_RATE,
    industry_code: '',
    industry_name_en: '',
    industry_name_ja: '',
    rate: 0,
    is_current: true,
  }
  aiDialog.value = true
}

function openAiEdit(row: any) {
  aiForm.value = { ...row }
  aiDialog.value = true
}

async function saveAi() {
  aiSaving.value = true
  try {
    await payrollJpApi.saveParameter(aiForm.value)
    aiDialog.value = false
    ElMessage.success(t('action.saved'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { aiSaving.value = false }
}

onMounted(() => { initConstants(); load(); loadOptions([CAT.TAX_TABLE]) })
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h3>{{ t('payroll.jp.parameters') }}</h3>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Tab 1: Social Insurance -->
      <el-tab-pane :label="t('payroll.jp.social_insurance')" name="social-insurance">
        <div class="tab-header">
          <el-button type="primary" size="small" @click="openSiCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="siPaged" v-loading="loading" border stripe size="small" style="width:100%">
          <el-table-column :label="t('field.rate_type')" min-width="180">
            <template #default="{row}">{{ rateTypeLabelMap[row.rate_type] || row.rate_type }}</template>
          </el-table-column>
          <el-table-column :label="t('field.prefecture')" min-width="220">
            <template #default="{row}">{{ prefectureLabel(row.prefecture) }}</template>
          </el-table-column>
          <el-table-column :label="t('field.employee_rate')" min-width="130" align="right">
            <template #default="{row}">{{ fmtPct(row.employee_rate) }}</template>
          </el-table-column>
          <el-table-column :label="t('field.employer_rate')" min-width="130" align="right">
            <template #default="{row}">{{ fmtPct(row.employer_rate) }}</template>
          </el-table-column>
          <el-table-column prop="applicable_from" :label="t('field.applicable_from')" min-width="120" />
          <el-table-column :label="t('field.is_current')" min-width="80" align="center">
            <template #default="{row}">
              <el-tag :type="row.is_current ? 'success' : 'info'" size="small">
                {{ row.is_current ? t('field.yes') : t('field.no') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('field.actions')" min-width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openSiEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
          <span class="helper-text">{{ socialInsuranceData.length }} {{ t('action.records_total') }}</span>
          <el-pagination v-if="socialInsuranceData.length > siPageSize" v-model:current-page="siPage" v-model:page-size="siPageSize" :page-sizes="[10, 20, 50, 100]" :total="socialInsuranceData.length" layout="total, sizes, prev, pager, next, jumper" background small @size-change="(s:number)=>{siPage=1;siPageSize=s}" />
        </div>

        <el-dialog v-model="siDialog" :title="t('payroll.jp.social_insurance')" width="520px">
          <el-form :model="siForm" label-width="160px">
            <el-form-item :label="t('field.rate_type')">
              <el-select v-model="siForm.rate_type" style="width:100%">
                <el-option v-for="(label, key) in rateTypeLabelMap" :key="key" :label="label" :value="key" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('field.prefecture')">
              <el-select v-model="siForm.prefecture" style="width:100%" clearable filterable :placeholder="t('field.prefecture')">
                <el-option v-for="p in prefectures" :key="p.code" :label="`${p.code} - ${p.name_ja} (${p.name_en})`" :value="p.code" />
                <el-option label="全国 - National (全国一律)" value="" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('field.employee_rate')">
              <el-input-number v-model="siForm.employee_rate" :min="0" :max="100" :step="0.01" :precision="2" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_pct_hint') }}</div>
            </el-form-item>
            <el-form-item :label="t('field.employer_rate')">
              <el-input-number v-model="siForm.employer_rate" :min="0" :max="100" :step="0.01" :precision="2" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_pct_hint') }}</div>
            </el-form-item>
            <el-form-item :label="t('field.applicable_from')">
              <el-input v-model="siForm.applicable_from" placeholder="2026-04" />
            </el-form-item>
            <el-form-item :label="t('field.is_current')">
              <el-switch v-model="siForm.is_current" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="siDialog = false">{{ t('action.cancel') }}</el-button>
            <el-button type="primary" :loading="siSaving" @click="saveSi">{{ t('action.save') }}</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 2: Tax Brackets -->
      <el-tab-pane :label="t('payroll.jp.tax_brackets')" name="tax-brackets">
        <div class="tab-header">
          <el-button type="primary" size="small" @click="openTbCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="tbPaged" v-loading="loading" border stripe size="small" style="width:100%">
          <el-table-column prop="table_type" :label="t('field.table_type')" min-width="100" />
          <el-table-column :label="t('field.min_salary')" min-width="110" align="right">
            <template #default="{row}">{{ row.min_salary ? '¥' + Number(row.min_salary).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('field.max_salary')" min-width="110" align="right">
            <template #default="{row}">{{ row.max_salary ? '¥' + Number(row.max_salary).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_0" :label="t('field.tax_dep_0')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_0 != null ? '¥' + Number(row.tax_dep_0).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_1" :label="t('field.tax_dep_1')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_1 != null ? '¥' + Number(row.tax_dep_1).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_2" :label="t('field.tax_dep_2')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_2 != null ? '¥' + Number(row.tax_dep_2).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_3" :label="t('field.tax_dep_3')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_3 != null ? '¥' + Number(row.tax_dep_3).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_4" :label="t('field.tax_dep_4')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_4 != null ? '¥' + Number(row.tax_dep_4).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_5" :label="t('field.tax_dep_5')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_5 != null ? '¥' + Number(row.tax_dep_5).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_6" :label="t('field.tax_dep_6')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_6 != null ? '¥' + Number(row.tax_dep_6).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_7" :label="t('field.tax_dep_7')" min-width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_7 != null ? '¥' + Number(row.tax_dep_7).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('field.actions')" min-width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openTbEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
          <span class="helper-text">{{ taxBracketData.length }} {{ t('action.records_total') }}</span>
          <el-pagination v-if="taxBracketData.length > tbPageSize" v-model:current-page="tbPage" v-model:page-size="tbPageSize" :page-sizes="[10, 20, 50, 100]" :total="taxBracketData.length" layout="total, sizes, prev, pager, next, jumper" background small @size-change="(s:number)=>{tbPage=1;tbPageSize=s}" />
        </div>

        <el-dialog v-model="tbDialog" :title="t('payroll.jp.tax_brackets')" width="680px">
          <el-form :model="tbForm" label-width="160px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('field.table_type')">
                  <el-select v-model="tbForm.table_type" style="width:100%">
                    <el-option v-for="tt in ddValues(CAT.TAX_TABLE)" :key="tt" :label="ddLabel(CAT.TAX_TABLE, tt)" :value="tt" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item :label="t('field.min_salary')">
                  <el-input-number v-model="tbForm.min_salary" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item :label="t('field.max_salary')">
                  <el-input-number v-model="tbForm.max_salary" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider>{{ t('payroll.jp.tax_amount_by_dependents') }}</el-divider>
            <el-row :gutter="16">
              <el-col :span="12" v-for="n in 8" :key="n">
                <el-form-item :label="t('field.tax_dep_' + (n - 1))">
                  <el-input-number v-model="tbForm['tax_dep_' + (n - 1)]" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="t('field.is_current')">
              <el-switch v-model="tbForm.is_current" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="tbDialog = false">{{ t('action.cancel') }}</el-button>
            <el-button type="primary" :loading="tbSaving" @click="saveTb">{{ t('action.save') }}</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 3: Remuneration Grades -->
      <el-tab-pane :label="t('payroll.jp.remuneration_grades')" name="remuneration-grades">
        <div class="tab-header">
          <el-button type="primary" size="small" @click="openRgCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="rgPaged" v-loading="loading" border stripe size="small" style="width:100%">
          <el-table-column prop="grade_type" :label="t('field.grade_type')" min-width="180">
            <template #default="{row}">{{ row.grade_type === 'health_insurance' ? '健康保険 (Health)' : row.grade_type === 'pension_insurance' ? '厚生年金 (Pension)' : row.grade_type }}</template>
          </el-table-column>
          <el-table-column prop="grade_number" :label="t('field.grade_number')" min-width="80" align="center" />
          <el-table-column :label="t('field.min_monthly_amount')" min-width="150" align="right">
            <template #default="{row}">{{ row.min_monthly_amount ? '¥' + Number(row.min_monthly_amount).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('field.max_monthly_amount')" min-width="150" align="right">
            <template #default="{row}">{{ row.max_monthly_amount ? '¥' + Number(row.max_monthly_amount).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('field.standard_monthly_amount')" min-width="170" align="right">
            <template #default="{row}">
              <strong>{{ row.standard_monthly_amount ? '¥' + Number(row.standard_monthly_amount).toLocaleString() : '-' }}</strong>
            </template>
          </el-table-column>
          <el-table-column :label="t('field.actions')" min-width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openRgEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
          <span class="helper-text">{{ remunerationGradeData.length }} {{ t('action.records_total') }}</span>
          <el-pagination v-if="remunerationGradeData.length > rgPageSize" v-model:current-page="rgPage" v-model:page-size="rgPageSize" :page-sizes="[10, 20, 50, 100]" :total="remunerationGradeData.length" layout="total, sizes, prev, pager, next, jumper" background small @size-change="(s:number)=>{rgPage=1;rgPageSize=s}" />
        </div>

        <el-dialog v-model="rgDialog" :title="t('payroll.jp.remuneration_grades')" width="550px">
          <el-form :model="rgForm" label-width="200px">
            <el-form-item :label="t('field.grade_type')">
              <el-select v-model="rgForm.grade_type" style="width:100%">
                <el-option label="健康保険 (Health Insurance)" value="health_insurance" />
                <el-option label="厚生年金保険 (Pension Insurance)" value="pension_insurance" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('field.grade_number')">
              <el-input-number v-model="rgForm.grade_number" :min="1" :max="100" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('field.min_monthly_amount')">
              <el-input-number v-model="rgForm.min_monthly_amount" :min="0" :precision="0" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('field.max_monthly_amount')">
              <el-input-number v-model="rgForm.max_monthly_amount" :min="0" :precision="0" style="width:100%" />
            </el-form-item>
            <el-form-item :label="t('field.standard_monthly_amount')">
              <el-input-number v-model="rgForm.standard_monthly_amount" :min="0" :precision="0" style="width:100%" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="rgDialog = false">{{ t('action.cancel') }}</el-button>
            <el-button type="primary" :loading="rgSaving" @click="saveRg">{{ t('action.save') }}</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 4: Accident Insurance -->
      <el-tab-pane :label="t('payroll.jp.accident_insurance')" name="accident-insurance">
        <div class="tab-header">
          <el-button type="primary" size="small" @click="openAiCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="aiPaged" v-loading="loading" border stripe size="small" style="width:100%">
          <el-table-column prop="industry_code" :label="t('field.industry_code')" />
          <el-table-column prop="industry_name_ja" :label="t('payroll.jp.accident_insurance') + ' (JA)'" min-width="200" show-overflow-tooltip />
          <el-table-column prop="industry_name_en" :label="t('field.industry_name_en')" min-width="200" show-overflow-tooltip />
          <el-table-column :label="t('field.rate')"  align="right">
            <template #default="{row}">{{ fmtPermille(row.rate) }}</template>
          </el-table-column>
          <el-table-column :label="t('field.is_current')"  align="center">
            <template #default="{row}">
              <el-tag :type="row.is_current ? 'success' : 'info'" size="small">
                {{ row.is_current ? t('field.yes') : t('field.no') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('field.actions')"  fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openAiEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
          <span class="helper-text">{{ accidentInsuranceData.length }} {{ t('action.records_total') }}</span>
          <el-pagination v-if="accidentInsuranceData.length > aiPageSize" v-model:current-page="aiPage" v-model:page-size="aiPageSize" :page-sizes="[10, 20, 50, 100]" :total="accidentInsuranceData.length" layout="total, sizes, prev, pager, next, jumper" background small @size-change="(s:number)=>{aiPage=1;aiPageSize=s}" />
        </div>

        <el-dialog v-model="aiDialog" :title="t('payroll.jp.accident_insurance')" width="550px">
          <el-form :model="aiForm" label-width="180px">
            <el-form-item :label="t('field.industry_code')">
              <el-input v-model="aiForm.industry_code" />
            </el-form-item>
            <el-form-item :label="t('payroll.jp.accident_insurance') + ' (JA)'">
              <el-input v-model="aiForm.industry_name_ja" />
            </el-form-item>
            <el-form-item :label="t('field.industry_name_en')">
              <el-input v-model="aiForm.industry_name_en" />
            </el-form-item>
            <el-form-item :label="t('field.rate')">
              <el-input-number v-model="aiForm.rate" :min="0" :max="1" :step="0.0001" :precision="6" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_decimal_hint') }} (例: 0.0035 = 3.5‰)</div>
            </el-form-item>
            <el-form-item :label="t('field.is_current')">
              <el-switch v-model="aiForm.is_current" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="aiDialog = false">{{ t('action.cancel') }}</el-button>
            <el-button type="primary" :loading="aiSaving" @click="saveAi">{{ t('action.save') }}</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page-container { max-width: 1500px; margin: 0 auto; padding: 24px; font-size: 15px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #1d2a3a; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.helper-text { color: #6b7280; font-size: .85rem; }
.form-hint { font-size: .78rem; color: #6b7280; margin-top: 4px; }
</style>
