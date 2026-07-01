<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const flows = [
  { key: 'projects', icon: '⚙️', label: 'invoice.flow1.title', desc: 'invoice.flow1.desc', route: '/invoice/projects' },
  { key: 'pending', icon: '📋', label: 'invoice.flow2.title', desc: 'invoice.flow2.desc', route: '/invoice/pending' },
  { key: 'invoices', icon: '📄', label: 'invoice.flow3.title', desc: 'invoice.flow3.desc', route: '/invoice/invoices' },
  { key: 'approval', icon: '✅', label: 'invoice.flow4.title', desc: 'invoice.flow4.desc', route: '/invoice/invoices' },
  { key: 'overdue', icon: '⚠️', label: 'invoice.flow5.title', desc: 'invoice.flow5.desc', route: '/invoice/overdue' },
]
</script>

<template>
  <div class="invoice-landing">
    <div class="page-header">
      <h2>{{ t('nav.invoice') }}</h2>
      <p>{{ t('invoice.description') }}</p>
    </div>

    <el-row :gutter="20">
      <el-col v-for="flow in flows" :key="flow.key" :xs="24" :sm="12" :md="8" style="margin-bottom: 16px">
        <el-card class="flow-card" shadow="hover" @click="router.push(flow.route)">
          <div class="flow-icon">{{ flow.icon }}</div>
          <h4>{{ t(flow.label) }}</h4>
          <p>{{ t(flow.desc) }}</p>
          <el-button size="small" type="primary" text>{{ t('action.open') }} →</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.invoice-landing { padding: 24px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 1.5rem; font-weight: 700; margin: 0 0 8px; }
.page-header p { color: var(--el-text-color-secondary); margin: 0; }
.flow-card { cursor: pointer; text-align: center; padding: 24px 16px; border-radius: 10px; transition: transform 0.2s; }
.flow-card:hover { transform: translateY(-3px); }
.flow-icon { font-size: 2rem; margin-bottom: 12px; }
.flow-card h4 { margin: 0 0 8px; font-size: 1.05rem; }
.flow-card p { color: var(--el-text-color-secondary); font-size: 0.85rem; margin: 0 0 12px; }
</style>
