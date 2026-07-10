<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const modules = [
  { key: 'item-definitions', label: 'payroll.jp.item_definitions', desc: 'payroll.jp.item_definitions_desc', icon: '📋', color: '#6366f1' },
  { key: 'employees', label: 'payroll.sg.salary_master', desc: 'payroll.sg.salary_master_desc', icon: '👥', color: '#0f766e' },
  { key: 'batches', label: 'payroll.sg.batches', desc: 'payroll.sg.batches_desc', icon: '📅', color: '#e65100' },
  { key: 'payslips', label: 'payroll.sg.payslips', desc: 'payroll.sg.payslips_desc', icon: '📄', color: '#7c3aed' },
  { key: 'email-settings', label: 'payroll.jp.email_settings', desc: 'payroll.jp.email_settings_desc', icon: '📧', color: '#0891b2' },
]

function navigate(module: string) {
  router.push(`/payroll/sg/${module}`)
}
</script>

<template>
  <div class="launchpad">
    <header class="lp-hero">
      <div>
        <h1>{{ t('payroll.sg.title') }}</h1>
        <p>{{ t('payroll.sg.desc') }}</p>
      </div>
      <span class="lp-badge">{{ t('payroll.sg.fy2026') }}</span>
    </header>

    <div class="lp-body">
      <div
        v-for="mod in modules"
        :key="mod.key"
        class="lp-tile"
        :style="{ '--tile-color': mod.color }"
        @click="navigate(mod.key)"
      >
        <span class="lp-tile-dot" :style="{ background: mod.color }"></span>
        <span class="lp-tile-icon">{{ mod.icon }}</span>
        <div class="lp-tile-text">
          <div class="lp-tile-title">{{ t(mod.label) }}</div>
          <div class="lp-tile-desc">{{ t(mod.desc) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.launchpad { max-width: 1200px; margin: 0 auto; padding: 32px 24px; font-size: 15px; }
.lp-hero {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 32px; padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}
.lp-hero h1 { margin: 0 0 4px; font-size: 1.5rem; font-weight: 700; color: #1d2a3a; }
.lp-hero p { margin: 0; font-size: .92rem; color: #6b7280; }
.lp-badge {
  flex-shrink: 0; background: #eff6ff; color: #1B6CB2;
  padding: 4px 14px; border-radius: 14px; font-size: .82rem; font-weight: 600;
}
.lp-body { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
@media (max-width: 860px) { .lp-body { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 540px) { .lp-body { grid-template-columns: 1fr; } }
.lp-tile {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 28px 20px 24px; cursor: pointer; transition: all .2s ease;
  position: relative; overflow: hidden; text-align: center;
}
.lp-tile:hover {
  border-color: var(--tile-color, #1B6CB2);
  box-shadow: 0 4px 20px rgba(0,0,0,.08); transform: translateY(-2px);
}
.lp-tile-dot {
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  border-radius: 0 0 3px 3px; opacity: 0; transition: opacity .2s;
}
.lp-tile:hover .lp-tile-dot { opacity: 1; }
.lp-tile-icon { font-size: 2rem; flex-shrink: 0; }
.lp-tile-text { min-width: 0; }
.lp-tile-title { font-size: .95rem; font-weight: 700; color: #1d2a3a; margin-bottom: 4px; }
.lp-tile-desc { font-size: .8rem; color: #9ca3af; line-height: 1.4; }
</style>
