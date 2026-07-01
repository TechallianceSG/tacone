<template>
  <div>
    <div class="card" style="text-align: center; padding: 48px 24px">
      <h1 style="margin: 0 0 8px; color: var(--navy); font-size: 24px">
        📄 TACAI Pay SG — Payslip Viewer
      </h1>
      <p class="muted" style="font-size: 16px">
        Enter a payslip ID to view the detailed payslip.
      </p>
      <div style="margin-top: 24px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap">
        <input
          v-model="payslipId"
          placeholder="e.g. PS-PAYSG-202606-ENT-0002-EMP-0043"
          style="max-width: 420px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 8px; font-size: 14px"
          @keyup.enter="goToPayslip"
        />
        <button class="btn" @click="goToPayslip">View Payslip / 查看工资条</button>
      </div>
    </div>

    <div class="card">
      <h2 style="margin: 0 0 16px; color: var(--navy); font-size: 16px">
        📋 Quick Links / 快捷链接
      </h2>
      <div style="display: flex; gap: 12px; flex-wrap: wrap">
        <router-link
          v-for="link in quickLinks.filter(l => l.internal)"
          :key="link.id"
          :to="link.url"
          class="btn btn-secondary"
        >
          {{ link.label }}
        </router-link>
        <a
          v-for="link in quickLinks.filter(l => !l.internal && !l.newTab)"
          :key="link.id"
          :href="link.url"
          class="btn btn-secondary"
        >
          {{ link.label }}
        </a>
        <a
          v-for="link in quickLinks.filter(l => !l.internal && l.newTab)"
          :key="link.id"
          :href="link.url"
          target="_blank"
          class="btn btn-secondary"
        >
          {{ link.label }}
        </a>
      </div>
    </div>

    <div class="card">
      <h2 style="margin: 0 0 16px; color: var(--navy); font-size: 16px">
        📖 About / 关于
      </h2>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px">
        <div v-for="item in features" :key="item.title" style="padding: 16px; background: #f8fafc; border-radius: 10px; border: 1px solid #edf0f4">
          <div style="font-size: 24px; margin-bottom: 8px">{{ item.icon }}</div>
          <div style="font-weight: 800; margin-bottom: 4px">{{ item.title }}</div>
          <div class="muted" style="font-size: 13px">{{ item.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const payslipId = ref('')

function goToPayslip() {
  const id = payslipId.value.trim()
  if (!id) return
  router.push({ path: '/payslip/view', query: { payslip_id: id, lang: 'zh' } })
}

const quickLinks = [
  { id: 1, label: '👥 Employee Management', url: 'http://127.0.0.1:8004/employees?lang=zh', internal: false, newTab: false },
  { id: 2, label: '⬅ Back to Portal', url: 'http://127.0.0.1:8005', internal: false, newTab: true },
  { id: 3, label: '📊 Payroll SG', url: 'http://127.0.0.1:8016?lang=zh', internal: false, newTab: true },
  { id: 4, label: '💰 Payroll JP / 日本給与', url: 'http://127.0.0.1:8017/salary-master?lang=zh', internal: false, newTab: true },
  { id: 5, label: '⚡ Salary Report / 給与計算', url: '/salary-report', internal: true, newTab: false },
]

const features = [
  { icon: '💰', title: 'Salary Calculation', desc: 'Advanced payroll computation with multi-currency and salary type support.' },
  { icon: '📋', title: 'Payslip View', desc: 'Modern Vue 3 payslip viewer with bilingual labels for HR review.' },
  { icon: '📄', title: 'PDF Generation', desc: 'Downloadable PDF payslips with professional formatting.' },
  { icon: '📊', title: 'Payroll Release', desc: 'Structured release workflow from calculation to payment confirmation.' },
  { icon: '📈', title: 'Salary Report / 給与計算レポート', desc: 'Execute payroll calculation and view detailed salary reports with filtering, timestamped to the second.' },
]
</script>
