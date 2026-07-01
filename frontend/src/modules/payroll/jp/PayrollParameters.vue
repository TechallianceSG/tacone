<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

// ── Tab state ──
const activeTab = ref('social-insurance')
const loading = ref(false)
const allParams = ref<any[]>([])

// ── Social Insurance ──
const siLoading = ref(false)
const siDialog = ref(false)
const siForm = ref<Record<string, any>>({ is_current: true })
const siSaving = ref(false)
const siPage = ref(1)
const siPageSize = ref(20)

const socialInsuranceData = computed(() => {
  return allParams.value.filter((p: any) => p.param_type === 'social_insurance_rate')
})

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

const taxBracketData = computed(() => {
  return allParams.value.filter((p: any) => p.param_type === 'withholding_tax_bracket')
})

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

const remunerationGradeData = computed(() => {
  return allParams.value.filter((p: any) => p.param_type === 'standard_remuneration_grade')
})

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

const accidentInsuranceData = computed(() => {
  return allParams.value.filter((p: any) => p.param_type === 'accident_insurance_rate')
})

const aiPaged = computed(() => {
  const start = (aiPage.value - 1) * aiPageSize.value
  return accidentInsuranceData.value.slice(start, start + aiPageSize.value)
})

// ── Methods ──
async function load() {
  loading.value = true
  try {
    const res = await payrollJpApi.parameters()
    allParams.value = res.data.data?.items || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

// ── Social Insurance CRUD ──
function openSiCreate() {
  siForm.value = {
    param_type: 'social_insurance_rate',
    rate_type: '',
    prefecture: '',
    employee_rate: '',
    employer_rate: '',
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
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { siSaving.value = false }
}

// ── Tax Bracket CRUD ──
function openTbCreate() {
  tbForm.value = {
    param_type: 'withholding_tax_bracket',
    table_type: '',
    min_salary: 0,
    max_salary: 0,
    tax_dep_0: 0,
    tax_dep_1: 0,
    tax_dep_2: 0,
    tax_dep_3: 0,
    tax_dep_4: 0,
    tax_dep_5: 0,
    tax_dep_6: 0,
    tax_dep_7: 0,
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
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { tbSaving.value = false }
}

// ── Remuneration Grade CRUD ──
function openRgCreate() {
  rgForm.value = {
    param_type: 'standard_remuneration_grade',
    grade_type: '',
    grade_number: 0,
    min_monthly_amount: 0,
    max_monthly_amount: 0,
    standard_monthly_amount: 0,
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
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { rgSaving.value = false }
}

// ── Accident Insurance CRUD ──
function openAiCreate() {
  aiForm.value = {
    param_type: 'accident_insurance_rate',
    industry_code: '',
    industry_name_en: '',
    rate: '',
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
    load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { aiSaving.value = false }
}

onMounted(load)
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
          <span class="helper-text">{{ socialInsuranceData.length }} {{ t('action.records_total') }}</span>
          <el-button type="primary" size="small" @click="openSiCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="siPaged" v-loading="loading" border stripe size="small">
          <el-table-column prop="rate_type" :label="t('field.rate_type')" width="160" />
          <el-table-column prop="prefecture" :label="t('field.prefecture')" width="120" />
          <el-table-column prop="employee_rate" :label="t('field.employee_rate')" width="120" align="right">
            <template #default="{row}">{{ row.employee_rate ? (Number(row.employee_rate) * 100).toFixed(2) + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="employer_rate" :label="t('field.employer_rate')" width="120" align="right">
            <template #default="{row}">{{ row.employer_rate ? (Number(row.employer_rate) * 100).toFixed(2) + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="applicable_from" :label="t('field.applicable_from')" width="110" />
          <el-table-column prop="is_current" :label="t('field.is_current')" width="90" align="center">
            <template #default="{row}">
              <el-tag :type="row.is_current ? 'success' : 'info'" size="small">
                {{ row.is_current ? t('field.yes') : t('field.no') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('action.actions')" width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openSiEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <div></div>
          <el-pagination v-model:current-page="siPage" :page-size="siPageSize" :total="socialInsuranceData.length" layout="prev, pager, next" small />
        </div>

        <el-dialog v-model="siDialog" :title="t('payroll.jp.social_insurance')" width="500px">
          <el-form :model="siForm" label-width="160px">
            <el-form-item :label="t('field.rate_type')">
              <el-select v-model="siForm.rate_type" style="width:100%">
                <el-option label="Health Insurance" value="health_insurance" />
                <el-option label="Pension Insurance" value="pension_insurance" />
                <el-option label="Care Insurance" value="care_insurance" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('field.prefecture')">
              <el-input v-model="siForm.prefecture" />
            </el-form-item>
            <el-form-item :label="t('field.employee_rate')">
              <el-input-number v-model="siForm.employee_rate" :min="0" :max="1" :step="0.001" :precision="6" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_decimal_hint') }}</div>
            </el-form-item>
            <el-form-item :label="t('field.employer_rate')">
              <el-input-number v-model="siForm.employer_rate" :min="0" :max="1" :step="0.001" :precision="6" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_decimal_hint') }}</div>
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
          <span class="helper-text">{{ taxBracketData.length }} {{ t('action.records_total') }}</span>
          <el-button type="primary" size="small" @click="openTbCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="tbPaged" v-loading="loading" border stripe size="small">
          <el-table-column prop="table_type" :label="t('field.table_type')" width="120" />
          <el-table-column prop="min_salary" :label="t('field.min_salary')" width="100" align="right">
            <template #default="{row}">{{ row.min_salary ? Number(row.min_salary).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="max_salary" :label="t('field.max_salary')" width="100" align="right">
            <template #default="{row}">{{ row.max_salary ? Number(row.max_salary).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_0" :label="t('field.tax_dep_0')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_0 ? Number(row.tax_dep_0).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_1" :label="t('field.tax_dep_1')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_1 ? Number(row.tax_dep_1).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_2" :label="t('field.tax_dep_2')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_2 ? Number(row.tax_dep_2).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_3" :label="t('field.tax_dep_3')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_3 ? Number(row.tax_dep_3).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_4" :label="t('field.tax_dep_4')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_4 ? Number(row.tax_dep_4).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_5" :label="t('field.tax_dep_5')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_5 ? Number(row.tax_dep_5).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_6" :label="t('field.tax_dep_6')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_6 ? Number(row.tax_dep_6).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="tax_dep_7" :label="t('field.tax_dep_7')" width="90" align="right">
            <template #default="{row}">{{ row.tax_dep_7 ? Number(row.tax_dep_7).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('action.actions')" width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openTbEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <div></div>
          <el-pagination v-model:current-page="tbPage" :page-size="tbPageSize" :total="taxBracketData.length" layout="prev, pager, next" small />
        </div>

        <el-dialog v-model="tbDialog" :title="t('payroll.jp.tax_brackets')" width="650px">
          <el-form :model="tbForm" label-width="160px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('field.table_type')">
                  <el-select v-model="tbForm.table_type" style="width:100%">
                    <el-option label="Monthly" value="monthly" />
                    <el-option label="Yearly" value="yearly" />
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
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_0')">
                  <el-input-number v-model="tbForm.tax_dep_0" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_1')">
                  <el-input-number v-model="tbForm.tax_dep_1" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_2')">
                  <el-input-number v-model="tbForm.tax_dep_2" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_3')">
                  <el-input-number v-model="tbForm.tax_dep_3" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_4')">
                  <el-input-number v-model="tbForm.tax_dep_4" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_5')">
                  <el-input-number v-model="tbForm.tax_dep_5" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_6')">
                  <el-input-number v-model="tbForm.tax_dep_6" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item :label="t('field.tax_dep_7')">
                  <el-input-number v-model="tbForm.tax_dep_7" :min="0" :precision="0" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
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
          <span class="helper-text">{{ remunerationGradeData.length }} {{ t('action.records_total') }}</span>
          <el-button type="primary" size="small" @click="openRgCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="rgPaged" v-loading="loading" border stripe size="small">
          <el-table-column prop="grade_type" :label="t('field.grade_type')" width="120" />
          <el-table-column prop="grade_number" :label="t('field.grade_number')" width="100" align="center" />
          <el-table-column prop="min_monthly_amount" :label="t('field.min_monthly_amount')" width="140" align="right">
            <template #default="{row}">{{ row.min_monthly_amount ? Number(row.min_monthly_amount).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="max_monthly_amount" :label="t('field.max_monthly_amount')" width="140" align="right">
            <template #default="{row}">{{ row.max_monthly_amount ? Number(row.max_monthly_amount).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="standard_monthly_amount" :label="t('field.standard_monthly_amount')" width="160" align="right">
            <template #default="{row}">{{ row.standard_monthly_amount ? Number(row.standard_monthly_amount).toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('action.actions')" width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openRgEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <div></div>
          <el-pagination v-model:current-page="rgPage" :page-size="rgPageSize" :total="remunerationGradeData.length" layout="prev, pager, next" small />
        </div>

        <el-dialog v-model="rgDialog" :title="t('payroll.jp.remuneration_grades')" width="550px">
          <el-form :model="rgForm" label-width="200px">
            <el-form-item :label="t('field.grade_type')">
              <el-select v-model="rgForm.grade_type" style="width:100%">
                <el-option label="Health Insurance" value="health_insurance" />
                <el-option label="Pension Insurance" value="pension_insurance" />
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
          <span class="helper-text">{{ accidentInsuranceData.length }} {{ t('action.records_total') }}</span>
          <el-button type="primary" size="small" @click="openAiCreate">{{ t('action.create') }}</el-button>
        </div>
        <el-table :data="aiPaged" v-loading="loading" border stripe size="small">
          <el-table-column prop="industry_code" :label="t('field.industry_code')" width="100" />
          <el-table-column prop="industry_name_en" :label="t('field.industry_name_en')" min-width="300" show-overflow-tooltip />
          <el-table-column prop="rate" :label="t('field.rate')" width="120" align="right">
            <template #default="{row}">{{ row.rate ? (Number(row.rate) * 1000).toFixed(2) + '/1000' : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('action.actions')" width="80" fixed="right">
            <template #default="{row}">
              <el-button size="small" text @click="openAiEdit(row)">{{ t('action.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <div></div>
          <el-pagination v-model:current-page="aiPage" :page-size="aiPageSize" :total="accidentInsuranceData.length" layout="prev, pager, next" small />
        </div>

        <el-dialog v-model="aiDialog" :title="t('payroll.jp.accident_insurance')" width="500px">
          <el-form :model="aiForm" label-width="160px">
            <el-form-item :label="t('field.industry_code')">
              <el-input v-model="aiForm.industry_code" />
            </el-form-item>
            <el-form-item :label="t('field.industry_name_en')">
              <el-input v-model="aiForm.industry_name_en" />
            </el-form-item>
            <el-form-item :label="t('field.rate')">
              <el-input-number v-model="aiForm.rate" :min="0" :max="1" :step="0.0001" :precision="6" style="width:100%" />
              <div class="form-hint">{{ t('field.rate_as_decimal_hint') }}</div>
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
.page-container { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; font-size: 1.2rem; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.helper-text { color: var(--el-text-color-secondary); font-size: 0.85rem; }
.form-hint { font-size: 0.78rem; color: var(--el-text-color-secondary); margin-top: 4px; }
</style>
