<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const countries = [
  { key: 'sg', flag: '🇸🇬', title: 'payroll.sg.title', desc: 'payroll.sg.desc', color: '#e65100' },
  { key: 'jp', flag: '🇯🇵', title: 'payroll.jp.title', desc: 'payroll.jp.desc', color: '#1B6CB2' },
  { key: 'cn', flag: '🇨🇳', title: 'payroll.cn.title', desc: 'payroll.cn.desc', color: '#b91c1c' },
]

function navigate(key: string) {
  router.push(`/payroll/${key}`)
}
</script>

<template>
  <div class="launchpad">
    <!-- Hero -->
    <header class="lp-hero">
      <div>
        <h1>{{ t('module.payroll') }}</h1>
        <p>{{ t('dashboard.payroll_desc') }}</p>
      </div>
    </header>

    <!-- Body: 3-column grid of countries -->
    <div class="lp-body">
      <div
        v-for="c in countries"
        :key="c.key"
        class="lp-tile"
        :style="{ '--tile-color': c.color }"
        @click="navigate(c.key)"
      >
        <span class="lp-tile-dot" :style="{ background: c.color }"></span>
        <span class="lp-tile-flag">{{ c.flag }}</span>
        <div class="lp-tile-text">
          <div class="lp-tile-title">{{ t(c.title) }}</div>
          <div class="lp-tile-desc">{{ t(c.desc) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.launchpad { max-width: 1200px; margin: 0 auto; padding: 32px 24px; font-size: 15px; }

/* ── Hero ── */
.lp-hero {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 32px; padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}
.lp-hero h1 { margin: 0 0 4px; font-size: 1.5rem; font-weight: 700; color: #1d2a3a; }
.lp-hero p { margin: 0; font-size: .92rem; color: #6b7280; }

/* ── 3-column grid ── */
.lp-body {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
@media (max-width: 860px) { .lp-body { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 540px) { .lp-body { grid-template-columns: 1fr; } }

/* ── Tiles ── */
.lp-tile {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
  padding: 36px 20px 32px;
  cursor: pointer; transition: all .2s ease;
  position: relative; overflow: hidden;
  text-align: center;
}
.lp-tile:hover {
  border-color: var(--tile-color, #1B6CB2);
  box-shadow: 0 4px 20px rgba(0,0,0,.08);
  transform: translateY(-2px);
}
.lp-tile-dot {
  position: absolute; top: 0; left: 0; right: 0;
  height: 3px; border-radius: 0 0 3px 3px;
  opacity: 0; transition: opacity .2s;
}
.lp-tile:hover .lp-tile-dot { opacity: 1; }
.lp-tile-flag { font-size: 2.5rem; flex-shrink: 0; }
.lp-tile-text { min-width: 0; }
.lp-tile-title { font-size: 1.05rem; font-weight: 700; color: #1d2a3a; margin-bottom: 4px; }
.lp-tile-desc { font-size: .8rem; color: #9ca3af; line-height: 1.4; }
</style>
