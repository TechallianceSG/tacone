<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testEmail = ref('')
const testResult = ref<'success' | 'error' | null>(null)
const smtpAvailable = ref(false)
const formRef = ref<any>(null)

// Form
const form = ref({
  country_code: 'JP',
  sender_name: '',
  sender_email: '',
  cc_recipients: [] as string[],
  email_subject_template: '',
  email_header_html: '',
  email_footer_html: '',
  payslip_visible_items: null as Record<string, boolean> | null,
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_use_tls: true,
  smtp_password_set: false,
})

const newCcEmail = ref('')
const smtpPanelOpen = ref(false)
const showPasswordInput = ref(false)

// ── Validation rules ──
const rules = {
  sender_name: [{ required: true, message: t('payroll.email.validate_sender_name_required'), trigger: 'blur' }],
  sender_email: [
    { required: true, message: t('payroll.email.validate_sender_email_required'), trigger: 'blur' },
    { type: 'email', message: t('payroll.email.validate_sender_email_format'), trigger: 'blur' },
  ],
}

function isSmtpOverrideActive(): boolean {
  return !!(form.value.smtp_host?.trim())
}

// ── Item definitions ──
interface ItemDef {
  code: string
  category: string
  labels: Record<string, string>
  payslip_visible: boolean
}
const allItems = ref<ItemDef[]>([])

const earningItems = computed(() => allItems.value.filter(i => i.category === 'earning'))
const deductionItems = computed(() => allItems.value.filter(i => i.category === 'deduction'))
const employerItems = computed(() => allItems.value.filter(i => i.category === 'employer_cost'))

// Merge item definitions defaults with email settings overrides
const visibleItems = computed(() => {
  const result: Record<string, boolean> = {}
  for (const item of allItems.value) {
    const code = item.code
    const overrides = form.value.payslip_visible_items
    if (overrides && code in overrides) {
      result[code] = overrides[code]
    } else {
      result[code] = item.payslip_visible !== false
    }
  }
  return result
})

function toggleItem(code: string) {
  const overrides = form.value.payslip_visible_items
  if (!overrides) {
    // First toggle: snapshot ALL current visibility into overrides
    form.value.payslip_visible_items = { ...visibleItems.value }
  }
  // Toggle the specific item
  const current = form.value.payslip_visible_items!
  current[code] = !visibleItems.value[code]
  // Trigger reactivity
  form.value.payslip_visible_items = { ...current }
}

function hasCustomOverrides(): boolean {
  const o = form.value.payslip_visible_items
  return o !== null && Object.keys(o).length > 0
}

function resetItemOverrides() {
  form.value.payslip_visible_items = null
}

function getItemLabel(item: ItemDef): string {
  const labels = item.labels || {}
  return labels.ja || labels.en || labels.zh || item.code
}

// ── Subject live preview ──
const subjectPreview = computed(() => {
  const tpl = form.value.email_subject_template
  if (!tpl) return '給与明細 / Payslip — 2026-07 — 山田 太郎 (System Default)'
  return tpl
    .replace('{{employee_name}}', '山田 太郎')
    .replace('{{payroll_month}}', '2026-07')
    .replace('{{entity_name}}', 'TAKK - Tech Alliance株式会社 (Japan)')
    .replace('{{default_subject}}', '給与明細 / Payslip — 2026-07 — 山田 太郎')
})

async function load() {
  loading.value = true
  try {
    // Check SMTP status
    try {
      const st = await payrollJpApi.getSmtpStatus()
      smtpAvailable.value = st.data?.data?.smtp_configured || st.data?.smtp_configured || false
    } catch { smtpAvailable.value = false }

    // Load item definitions
    try {
      const itemsRes = await payrollJpApi.itemDefinitions()
      allItems.value = (itemsRes.data?.data || itemsRes.data || []) as ItemDef[]
    } catch { allItems.value = [] }

    // Load saved settings
    const res = await payrollJpApi.emailSettings({ country_code: 'JP' })
    const data = res.data?.data || res.data || {}

    // Split body_template
    let headerHtml = '', footerHtml = ''
    const bodyTemplate = data.email_body_template || ''
    if (bodyTemplate) {
      const match = bodyTemplate.match(/^(.*)\{\{payslip_html\}\}(.*)$/s)
      if (match) { headerHtml = match[1].trim(); footerHtml = match[2].trim() }
      else { headerHtml = bodyTemplate }
    }

    // Parse payslip_visible_items
    let visibleOverrides: Record<string, boolean> | null = null
    const raw = data.payslip_visible_items
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      visibleOverrides = raw as Record<string, boolean>
    }

    form.value = {
      country_code: 'JP',
      sender_name: data.sender_name || '',
      sender_email: data.sender_email || '',
      cc_recipients: Array.isArray(data.cc_recipients) ? data.cc_recipients : [],
      email_subject_template: data.email_subject_template || '',
      email_header_html: headerHtml,
      email_footer_html: footerHtml,
      payslip_visible_items: visibleOverrides,
      smtp_host: data.smtp_host || '',
      smtp_port: data.smtp_port || 587,
      smtp_user: data.smtp_user || '',
      smtp_password: '',
      smtp_use_tls: data.smtp_use_tls !== false,
      smtp_password_set: data.smtp_password_set === true,
    }
    showPasswordInput.value = !data.smtp_password_set

    // Auto-expand SMTP panel if system SMTP is not configured
    if (!smtpAvailable.value && !isSmtpOverrideActive()) {
      smtpPanelOpen.value = true
    }

    // Restore test email from localStorage
    try {
      testEmail.value = localStorage.getItem('tacai_pay_jp_test_email') || ''
    } catch { testEmail.value = '' }
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally { loading.value = false }
}

function addCc() {
  const email = newCcEmail.value.trim()
  if (!email) return
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { ElMessage.warning(t('payroll.email.validate_email_format')); return }
  if (form.value.cc_recipients.includes(email)) { ElMessage.warning(t('payroll.email.cc_duplicate')); return }
  form.value.cc_recipients.push(email)
  newCcEmail.value = ''
}
function removeCc(index: number) { form.value.cc_recipients.splice(index, 1) }

function buildBodyTemplate(): string {
  const h = form.value.email_header_html.trim()
  const f = form.value.email_footer_html.trim()
  if (!h && !f) return ''
  return (h ? h + '\n' : '') + '{{payslip_html}}' + (f ? '\n' + f : '')
}

async function save() {
  // Validate sender
  if (!form.value.sender_name?.trim()) { ElMessage.warning(t('payroll.email.validate_sender_name_required')); return }
  if (!form.value.sender_email?.trim()) { ElMessage.warning(t('payroll.email.validate_sender_email_required')); return }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.value.sender_email.trim())) { ElMessage.warning(t('payroll.email.validate_sender_email_invalid')); return }

  // SMTP must be configured — either via env vars or via override
  if (!smtpAvailable.value && !isSmtpOverrideActive()) {
    ElMessage.warning(t('payroll.email.validate_smtp_required'))
    smtpPanelOpen.value = true
    return
  }
  // If using SMTP override, validate required fields
  if (isSmtpOverrideActive()) {
    if (!form.value.smtp_user?.trim()) { ElMessage.warning(t('payroll.email.validate_smtp_user_required')); smtpPanelOpen.value = true; return }
    if (!form.value.smtp_password?.trim() && !form.value.smtp_password_set) { ElMessage.warning(t('payroll.email.validate_smtp_password_required')); smtpPanelOpen.value = true; return }
  }

  saving.value = true
  try {
    const payload: Record<string, any> = {
      country_code: form.value.country_code,
      sender_name: form.value.sender_name,
      sender_email: form.value.sender_email,
      cc_recipients: form.value.cc_recipients,
      email_subject_template: form.value.email_subject_template,
      email_body_template: buildBodyTemplate(),
      payslip_visible_items: form.value.payslip_visible_items,
      smtp_host: form.value.smtp_host,
      smtp_port: form.value.smtp_port,
      smtp_user: form.value.smtp_user,
      smtp_password: form.value.smtp_password,
      smtp_use_tls: form.value.smtp_use_tls,
      smtp_password_set: form.value.smtp_password_set,
    }
    await payrollJpApi.saveEmailSettings(payload)
    ElMessage.success(t('payroll.jp.email_settings_saved'))
    await load()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally { saving.value = false }
}

async function sendTest() {
  if (!testEmail.value.trim()) { ElMessage.warning(t('payroll.email.validate_test_recipient_required')); return }
  // Persist test email
  try { localStorage.setItem('tacai_pay_jp_test_email', testEmail.value.trim()) } catch {}

  testing.value = true; testResult.value = null
  try {
    await payrollJpApi.testEmailSettings({ test_to: testEmail.value.trim(), country_code: 'JP' })
    testResult.value = 'success'
    ElMessage.success(t('payroll.jp.test_email_sent'))
  } catch (e: any) {
    testResult.value = 'error'
    ElMessage.error(e.message)
  } finally { testing.value = false }
}

function resetSubject() { form.value.email_subject_template = '' }
function resetHeader() { form.value.email_header_html = '' }
function resetFooter() { form.value.email_footer_html = '' }

// ── Preview ──
const previewDialog = ref(false)
const previewLoading = ref(false)
const previewData = ref({ subject: '', html: '', employee_name: '', payroll_month: '', entity_name: '', is_sample: true })

async function previewTemplate() {
  previewLoading.value = true; previewDialog.value = true
  try {
    // Build current visibility state (merge defaults + user overrides)
    const currentVisibility: Record<string, boolean> = {}
    for (const item of allItems.value) {
      currentVisibility[item.code] = !!visibleItems.value[item.code]
    }
    const res = await payrollJpApi.previewEmailTemplate({
      email_subject_template: form.value.email_subject_template,
      email_body_template: buildBodyTemplate(),
      payslip_visible_items: currentVisibility,
      payslip_id: '',
    })
    previewData.value = res.data?.data || res.data || {}
  } catch (e: any) { ElMessage.error(e.message) }
  finally { previewLoading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>📧 {{ t('payroll.jp.email_settings') }}</h2>
        <span class="toolbar-desc">{{ t('payroll.jp.email_settings_desc') }}</span>
      </div>
      <div class="toolbar-right">
        <el-tag v-if="smtpAvailable" type="success" size="large">✅ SMTP Connected</el-tag>
        <el-tag v-else type="danger" size="large">⚠️ SMTP Not Configured</el-tag>
      </div>
    </div>

    <div v-loading="loading" style="max-width:860px;margin:0 auto;">

      <!-- ═══ 1. SENDER ═══ -->
      <div class="settings-card">
        <div class="card-header">
          <span class="card-icon">👤</span>
          <div>
            <h3 class="card-title">{{ t('payroll.jp.sender_settings') }}</h3>
            <p class="card-hint">{{ t('payroll.email.sender_info_hint') }}</p>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label><span class="required">*</span> {{ t('payroll.jp.sender_name') }}</label>
            <el-input v-model="form.sender_name" maxlength="200" :placeholder="t('payroll.email.placeholder_sender_name')" />
          </div>
          <div class="form-group">
            <label><span class="required">*</span> {{ t('payroll.jp.sender_email') }}</label>
            <el-input v-model="form.sender_email" maxlength="200" :placeholder="t('payroll.email.placeholder_sender_email')" />
          </div>
        </div>
      </div>

      <!-- ═══ 2. CC ═══ -->
      <div class="settings-card">
        <div class="card-header">
          <span class="card-icon">📋</span>
          <div>
            <h3 class="card-title">{{ t('payroll.jp.cc_recipients') }}</h3>
            <p class="card-hint">{{ t('payroll.email.cc_hint') }}</p>
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:10px;">
          <el-input v-model="newCcEmail" placeholder="email@example.com" style="flex:1" @keyup.enter="addCc" />
          <el-button type="primary" plain @click="addCc">{{ t('payroll.email.add_cc') }}</el-button>
        </div>
        <div v-if="form.cc_recipients.length" style="display:flex;flex-wrap:wrap;gap:6px;">
          <el-tag v-for="(email, idx) in form.cc_recipients" :key="idx" closable @close="removeCc(idx)" size="default">{{ email }}</el-tag>
        </div>
        <div v-else style="color:#9ca3af;font-size:13px;">{{ t('payroll.email.no_cc') }}</div>
      </div>

      <!-- ═══ 3. EMAIL TEMPLATE ═══ -->
      <div class="settings-card">
        <div class="card-header">
          <span class="card-icon">✉️</span>
          <div style="flex:1;">
            <h3 class="card-title">{{ t('payroll.email.email_template') }}</h3>
            <p class="card-hint">{{ t('payroll.email.template_hint') }}</p>
          </div>
          <el-button type="primary" plain size="small" @click="previewTemplate">{{ t('payroll.email.preview_button') }}</el-button>
        </div>

        <!-- Subject -->
        <div class="template-section">
          <label class="section-label">📌 {{ t('payroll.email.subject_label') }}</label>
          <el-input v-model="form.email_subject_template" maxlength="500" placeholder="留空{{ t('payroll.email.using_default') }}格式：給与明細 / Payslip — 月份 — 员工姓名" />
          <div class="live-preview" v-if="form.email_subject_template">{{ t('payroll.email.preview_label') }}<strong>{{ subjectPreview }}</strong></div>
          <button class="reset-link" @click="resetSubject" v-if="form.email_subject_template">{{ t('payroll.email.reset_default') }}</button>
        </div>

        <!-- Header -->
        <div class="template-section">
          <label class="section-label">{{ t('payroll.email.email_header_label') }}</label>
          <el-input v-model="form.email_header_html" type="textarea" :rows="2"
            :placeholder="t('payroll.email.header_placeholder')" />
          <button class="reset-link" @click="resetHeader" v-if="form.email_header_html">{{ t('payroll.email.clear') }}</button>
        </div>

        <!-- ── Payslip Items ── -->
        <div class="template-section">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <label class="section-label" style="margin-bottom:0;">📄 {{ t('payroll.email.payslip_items_label') }}</label>
            <div style="display:flex;gap:8px;align-items:center;">
              <el-tag v-if="hasCustomOverrides()" size="small" type="warning">{{ t('payroll.email.customized') }}</el-tag>
              <el-tag v-else size="small" type="info">{{ t('payroll.email.using_default') }}</el-tag>
              <button class="reset-link" @click="resetItemOverrides" v-if="hasCustomOverrides()">{{ t('payroll.email.reset_default') }}</button>
            </div>
          </div>
          <p style="font-size:.8rem;color:#9ca3af;margin:0 0 10px;">
            {{ t('payroll.email.items_hint', { url: '/payroll/jp/item-definitions' }) }}<a href="/payroll/jp/item-definitions" target="_blank" style="color:#1B6CB2;">{{ t('payroll.email.items_hint', { url: '/payroll/jp/item-definitions' }) }}</a>。
          </p>

          <div class="items-grid">
            <div class="item-group" v-if="earningItems.length">
              <div class="item-group-title">💰 {{ t('payroll.email.earnings_group') }}</div>
              <label v-for="item in earningItems" :key="item.code" class="item-row">
                <el-checkbox :model-value="!!visibleItems[item.code]" @change="() => toggleItem(item.code)" />
                <span class="item-label">{{ getItemLabel(item) }}</span>
                <code class="item-code">{{ item.code }}</code>
              </label>
            </div>
            <div class="item-group" v-if="deductionItems.length">
              <div class="item-group-title">📉 {{ t('payroll.email.deductions_group') }}</div>
              <label v-for="item in deductionItems" :key="item.code" class="item-row">
                <el-checkbox :model-value="!!visibleItems[item.code]" @change="() => toggleItem(item.code)" />
                <span class="item-label">{{ getItemLabel(item) }}</span>
                <code class="item-code">{{ item.code }}</code>
              </label>
            </div>
            <div class="item-group" v-if="employerItems.length">
              <div class="item-group-title">🏢 {{ t('payroll.email.employer_cost_group') }}</div>
              <label v-for="item in employerItems" :key="item.code" class="item-row">
                <el-checkbox :model-value="!!visibleItems[item.code]" @change="() => toggleItem(item.code)" />
                <span class="item-label">{{ getItemLabel(item) }}</span>
                <code class="item-code">{{ item.code }}</code>
              </label>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="template-section">
          <label class="section-label">{{ t('payroll.email.email_footer_label') }}</label>
          <el-input v-model="form.email_footer_html" type="textarea" :rows="2"
            :placeholder="t('payroll.email.footer_placeholder')" />
          <button class="reset-link" @click="resetFooter" v-if="form.email_footer_html">{{ t('payroll.email.clear') }}</button>
        </div>
      </div>

      <!-- ═══ 4. SMTP ═══ -->
      <div class="settings-card smtp-card">
        <el-collapse v-model="smtpPanelOpen">
          <el-collapse-item name="smtp">
            <template #title>
              <div class="card-header" style="margin-bottom:0;">
                <span class="card-icon">🔧</span>
                <div>
                  <h3 class="card-title" style="margin-bottom:0;">
                    {{ t('payroll.email.smtp_settings') }}
                    <span v-if="!smtpAvailable && !isSmtpOverrideActive()" style="color:#dc2626;font-size:.8rem;">{{ t('payroll.email.smtp_required_warning') }}</span>
                    <span v-else-if="smtpAvailable" style="color:#059669;font-size:.8rem;">{{ t('payroll.email.system_configured') }}</span>
                    <span v-else style="color:#1B6CB2;font-size:.8rem;">{{ t('payroll.email.password_filled') }}</span>
                  </h3>
                  <p class="card-hint" style="margin-bottom:0;">
                    <template v-if="smtpAvailable">当前使用系统SMTP服务器发送邮件，一般无需{{ t('payroll.email.change_password') }}。</template>
                    <template v-else>{{ t('payroll.email.smtp_not_configured') }}</template>
                  </p>
                </div>
              </div>
            </template>
            <div class="smtp-body">
              <div class="form-row">
                <div class="form-group" style="flex:2;">
                  <label>{{ t('payroll.email.smtp_server_addr') }}</label>
                  <el-input v-model="form.smtp_host" placeholder="smtp.qq.com / smtp.gmail.com / smtp.office365.com" />
                  <span class="field-hint">{{ t('payroll.email.smtp_server_hint') }}</span>
                </div>
                <div class="form-group" style="max-width:130px;">
                  <label>{{ t('payroll.email.smtp_port') }}</label>
                  <el-input-number v-model="form.smtp_port" :min="1" :max="65535" style="width:100%" />
                  <span class="field-hint">{{ t('payroll.email.smtp_port_hint') }}</span>
                </div>
              </div>
              <div class="form-row" style="margin-top:12px;">
                <div class="form-group">
                  <label>{{ t('payroll.email.smtp_user') }}</label>
                  <el-input v-model="form.smtp_user" placeholder="notify@yourcompany.com" />
                  <span class="field-hint">{{ t('payroll.email.smtp_user_hint') }}</span>
                </div>
                <div class="form-group">
                  <label>{{ t('payroll.email.smtp_password') }}</label>
                  <div style="display:flex;gap:8px;align-items:center;">
                    <template v-if="!showPasswordInput && form.smtp_password_set">
                      <el-tag type="success" size="default">{{ t('payroll.email.password_set') }}</el-tag>
                      <el-button text size="small" type="primary" @click="showPasswordInput = true">{{ t('payroll.email.change_password') }}</el-button>
                    </template>
                    <el-input v-else v-model="form.smtp_password" type="password" show-password :placeholder="t('payroll.email.smtp_password_hint')" style="flex:1" />
                  </div>
                  <span class="field-hint">{{ t('payroll.email.password_hint') }}</span>
                </div>
              </div>
              <div style="margin-top:12px;">
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                  <el-switch v-model="form.smtp_use_tls" size="small" />
                  <span>{{ t('payroll.email.tls_encryption') }}</span>
                </label>
                <span class="field-hint" style="margin-left:44px;">{{ t('payroll.email.smtp_port') }} 587 时通常开启，{{ t('payroll.email.smtp_port') }} 465 时{{ t('payroll.payslip.close') }}（用SSL）</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- ═══ 5. TEST ═══ -->
      <div class="settings-card">
        <div class="card-header">
          <span class="card-icon">🧪</span>
          <div style="flex:1;">
            <h3 class="card-title">{{ t('payroll.email.test_email_title') }}</h3>
            <p class="card-hint">{{ t('payroll.email.test_email_hint') }}</p>
          </div>
        </div>
        <div style="display:flex;gap:8px;align-items:flex-end;">
          <div class="form-group" style="flex:1;margin-bottom:0;">
            <label>{{ t('payroll.email.recipient_email') }}</label>
            <el-input v-model="testEmail" placeholder="your@email.com" @keyup.enter="sendTest" />
          </div>
          <el-button type="warning" :loading="testing" :disabled="!testEmail.trim()" @click="sendTest">{{ t('payroll.email.send_test') }}</el-button>
        </div>
        <div v-if="testResult === 'success'" class="test-msg success">{{ t('payroll.email.test_sent') }}</div>
        <div v-if="testResult === 'error'" class="test-msg error">{{ t('payroll.email.test_failed') }}</div>
      </div>

      <!-- Save -->
      <div style="text-align:center;margin-top:24px;padding-bottom:40px;">
        <el-button type="primary" size="large" :loading="saving" @click="save">{{ t('payroll.email.save_settings') }}</el-button>
      </div>
    </div>

    <!-- ═══ Preview Dialog ═══ -->
    <el-dialog v-model="previewDialog" title="📧 {{ t('payroll.email.preview') }}" width="1000px" top="2vh" destroy-on-close class="preview-dialog">
      <div v-loading="previewLoading" style="min-height:300px;">
        <template v-if="!previewLoading && previewData.html">
          <div class="preview-subject-line">
            <span class="preview-label">Subject:</span>
            <span>{{ previewData.subject }}</span>
          </div>
          <div v-if="previewData.is_sample" style="margin-bottom:8px;text-align:center;">
            <el-tag size="small" type="warning">⚠️ 示例数据 — {{ previewData.employee_name }} / {{ previewData.payroll_month }}</el-tag>
          </div>
          <iframe :srcdoc="previewData.html" class="preview-iframe" sandbox="allow-same-origin" />
        </template>
        <div v-if="!previewLoading && !previewData.html" style="text-align:center;padding:60px;color:#9ca3af;"><p>{{ t('payroll.email.preview_unavailable') }}</p></div>
      </div>
      <template #footer><el-button @click="previewDialog = false">{{ t('payroll.payslip.close') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width: 1200px; margin: 0 auto; padding: 24px; font-size: 15px; }
.fiori-toolbar { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; flex-direction: column; gap: 4px; }
.toolbar-left h2 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #1d2a3a; }
.toolbar-desc { font-size: .88rem; color: #6b7280; }

.settings-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; }
.card-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
.card-icon { font-size: 1.25rem; flex-shrink: 0; margin-top: 1px; }
.card-title { margin: 0 0 2px; font-size: 1rem; font-weight: 700; color: #1d2a3a; }
.card-hint { margin: 0; font-size: .82rem; color: #9ca3af; line-height: 1.4; }

.required { color: #dc2626; font-weight: 700; margin-right: 2px; }

.form-row { display: flex; gap: 16px; flex-wrap: wrap; }
.form-group { flex: 1; min-width: 200px; margin-bottom: 8px; }
.form-group label { display: block; margin-bottom: 4px; font-size: .85rem; font-weight: 600; color: #374151; }

.template-section { margin-bottom: 18px; }
.section-label { display: block; margin-bottom: 6px; font-size: .9rem; font-weight: 700; color: #1d2a3a; }
.live-preview { margin-top: 6px; padding: 6px 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; font-size: .85rem; color: #166534; }
.reset-link { display: inline-block; margin-top: 4px; background: none; border: none; color: #1B6CB2; cursor: pointer; font-size: .78rem; padding: 0; text-decoration: underline; }

.items-grid { display: flex; flex-direction: column; gap: 10px; }
.item-group { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; background: #fafafa; }
.item-group-title { font-size: .82rem; font-weight: 700; color: #374151; margin-bottom: 6px; }
.item-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; cursor: pointer; font-size: .85rem; }
.item-row :deep(.el-checkbox) { margin-right: 0; }
.item-label { flex: 1; }
.item-code { font-size: .7rem; color: #9ca3af; }

.smtp-card { padding: 12px 16px; }
.smtp-card :deep(.el-collapse-item__header) { border: none; font-size: inherit; background: transparent; }
.smtp-card :deep(.el-collapse-item__wrap) { border: none; background: transparent; }
.smtp-card :deep(.el-collapse-item__content) { padding: 16px 0 0; }
.smtp-body { padding: 16px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; }
.field-hint { display: block; margin-top: 3px; font-size: .75rem; color: #9ca3af; }

.test-msg { margin-top: 8px; font-size: .85rem; font-weight: 600; }
.test-msg.success { color: #059669; }
.test-msg.error { color: #dc2626; }

.preview-subject-line { margin-bottom: 12px; padding: 10px 14px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px; }
.preview-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; display: block; }
.preview-iframe { width: 100%; height: 70vh; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); background: #fff; }
</style>
