<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="under-dev">
    <div class="under-dev-card">
      <span class="under-dev-icon">🚧</span>
      <h2>{{ t('common.coming_soon') }}</h2>
      <p>{{ t('payroll.under_development') }}</p>
    </div>
  </div>
</template>

<style scoped>
.under-dev {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
  padding: 32px 24px;
}
.under-dev-card {
  text-align: center;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 48px 40px;
  max-width: 420px;
  width: 100%;
}
.under-dev-icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 16px;
}
.under-dev-card h2 {
  margin: 0 0 8px;
  font-size: 1.25rem;
  font-weight: 700;
  color: #1d2a3a;
}
.under-dev-card p {
  margin: 0;
  font-size: .92rem;
  color: #9ca3af;
  line-height: 1.5;
}
</style>
