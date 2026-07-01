<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const activeTab = ref('sg')

const countries = [
  { key: 'sg', label: 'payroll.sg.title', flag: '🇸🇬', desc: 'payroll.sg.desc' },
  { key: 'jp', label: 'payroll.jp.title', flag: '🇯🇵', desc: 'payroll.jp.desc' },
  { key: 'cn', label: 'payroll.cn.title', flag: '🇨🇳', desc: 'payroll.cn.desc' },
]

const sgModules = [
  { key: 'salary-master', label: 'payroll.sg.salary_master', desc: 'payroll.sg.salary_master_desc' },
  { key: 'batches', label: 'payroll.sg.batches', desc: 'payroll.sg.batches_desc' },
  { key: 'payslips', label: 'payroll.sg.payslips', desc: 'payroll.sg.payslips_desc' },
]

const jpModules = [
  { key: 'item-definitions', label: 'payroll.jp.item_definitions', desc: 'payroll.jp.item_definitions_desc' },
  { key: 'parameters', label: 'payroll.jp.parameters', desc: 'payroll.jp.parameters_desc' },
  { key: 'employees', label: 'payroll.jp.employees', desc: 'payroll.jp.employees_desc' },
  { key: 'batches', label: 'payroll.jp.batches', desc: 'payroll.jp.batches_desc' },
  { key: 'payslips', label: 'payroll.jp.payslips', desc: 'payroll.jp.payslips_desc' },
]

const cnModules = [
  { key: 'social-insurance-rules', label: 'payroll.cn.rules', desc: 'payroll.cn.rules_desc' },
  { key: 'tax-brackets', label: 'payroll.cn.tax_brackets', desc: 'payroll.cn.tax_brackets_desc' },
  { key: 'employees', label: 'payroll.cn.employees', desc: 'payroll.cn.employees_desc' },
  { key: 'batches', label: 'payroll.cn.batches', desc: 'payroll.cn.batches_desc' },
  { key: 'payslips', label: 'payroll.cn.payslips', desc: 'payroll.cn.payslips_desc' },
]

function navigate(country: string, module: string) {
  router.push(`/payroll/${country}/${module}`)
}
</script>

<template>
  <div class="payroll-landing">
    <div class="page-header">
      <h2>{{ t('nav.payroll') }}</h2>
      <p>{{ t('payroll.landing.description') }}</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="country-tabs">
      <el-tab-pane v-for="country in countries" :key="country.key" :name="country.key">
        <template #label>
          <span class="tab-label">
            <span class="country-flag">{{ country.flag }}</span>
            {{ t(country.label) }}
          </span>
        </template>

        <div class="country-section">
          <p class="country-desc">{{ t(country.desc) }}</p>

          <el-row :gutter="20">
            <el-col
              v-for="mod in (country.key === 'sg' ? sgModules : country.key === 'jp' ? jpModules : cnModules)"
              :key="mod.key"
              :xs="24" :sm="12" :md="8"
            >
              <el-card class="module-card" shadow="hover" @click="navigate(country.key, mod.key)">
                <h4>{{ t(mod.label) }}</h4>
                <p>{{ t(mod.desc) }}</p>
                <el-button size="small" type="primary" text>
                  {{ t('action.open') }} →
                </el-button>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.payroll-landing {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 8px;
}
.page-header p {
  color: var(--el-text-color-secondary);
  margin: 0;
}
.country-tabs {
  border-radius: 8px;
}
.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
}
.country-flag {
  font-size: 1.2rem;
}
.country-section {
  padding: 16px 0;
}
.country-desc {
  color: var(--el-text-color-secondary);
  margin: 0 0 20px;
}
.module-card {
  cursor: pointer;
  margin-bottom: 16px;
  border-radius: 8px;
  transition: transform 0.2s;
}
.module-card:hover {
  transform: translateY(-2px);
}
.module-card h4 {
  margin: 0 0 8px;
  font-size: 1.05rem;
}
.module-card p {
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
  font-size: 0.9rem;
}
</style>
