<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePayroll } from '@/composables/usePayroll'
import { ElMessage, ElMessageBox } from 'element-plus'


const props = defineProps<{ countryCode: 'jp' | 'sg' }>()
const router = useRouter()
const { t } = useI18n()
const { api, baseRoute, STATUS_CONFIG, ACTION_LABELS, actionLabel, parseAuditValue, fmtCurrency, pk } = usePayroll(props.countryCode)

const loading = ref(false)
const sheets = ref<any[]>([])
const filterEntity = ref('')
const filterMonth = ref('')
const filterStatus = ref('')

// ── Pagination ──
const page = ref(1)
const pageSize = ref(20)

const createDialog = ref(false)
const creating = ref(false)
const createForm = ref({ payroll_month: new Date().toISOString().slice(0, 7), entity_id: '', working_days_in_month: 22, notes: '' })

const voidDialog = ref(false)
const voiding = ref(false)
const voidSheetId = ref('')
const voidReason = ref('')

// ── Global Audit Log Dialog ──
const auditDialog = ref(false)
const auditLogs = ref<any[]>([])
const auditLoading = ref(false)
const expandedAudit = ref<Set<number>>(new Set())

function toggleAuditDetail(idx: number) {
  if (expandedAudit.value.has(idx)) { expandedAudit.value.delete(idx) }
  else { expandedAudit.value.add(idx) }
}

// ── Auto working days calculation (Japan Mon-Fri) ──
function calcJpWorkingDays(yearMonth: string): number {
  if (!yearMonth || !/^\d{4}-\d{2}$/.test(yearMonth)) return 22
  const [y, m] = yearMonth.split('-').map(Number)
  const daysInMonth = new Date(y, m, 0).getDate()
  let count = 0
  for (let d = 1; d <= daysInMonth; d++) {
    const dow = new Date(y, m - 1, d).getDay()
    if (dow !== 0 && dow !== 6) count++
  }
  return count
}

// Auto-update working days when month changes
watch(() => createForm.value.payroll_month, (newMonth) => {
  if (newMonth) {
    createForm.value.working_days_in_month = calcJpWorkingDays(newMonth)
  }
})

const entities = ref<any[]>([])


// ── Manual filter (not auto-reactive) ──
const filtered = ref<any[]>([])

function applyFilter() {
  let result = sheets.value
  if (filterEntity.value) result = result.filter((s: any) => s.entity_id === filterEntity.value)
  if (filterMonth.value) result = result.filter((s: any) => s.payroll_month === filterMonth.value)
  if (filterStatus.value) result = result.filter((s: any) => s.status === filterStatus.value)
  filtered.value = result
  page.value = 1
}

function clearFilter() {
  filterEntity.value = ''
  filterMonth.value = ''
  filterStatus.value = ''
  filtered.value = [...sheets.value]
  page.value = 1
}

// ── Paged display ──
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

function handlePageChange(p: number) { page.value = p }
function handleSizeChange(s: number) { pageSize.value = s; page.value = 1 }

async function load() {
  loading.value = true
  try {
    const res = await api.batches()
    sheets.value = res.data.data || []
    filtered.value = [...sheets.value]
  } catch (e: any) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

async function loadEntities() { try { const res = await api.entities(); entities.value = res.data?.data || [] } catch (_) {} }

function entityLabel(id: string) {
  const f = entities.value.find((e: any) => e.entity_id === id || e.entity_code === id)
  if (!f) return id
  const name = f.entity_name_en || f.entity_name || ''
  const extra = f.country ? ` (${f.country})` : ''
  return `${f.entity_code || id} - ${name}${extra}`
}

async function createSheet() {
  if (!createForm.value.entity_id) { ElMessage.warning(t('field.entity_id') + ' required'); return }

  const duplicate = sheets.value.find((s: any) =>
    s.entity_id === createForm.value.entity_id &&
    s.payroll_month === createForm.value.payroll_month &&
    s.status !== 'voided'
  )
  if (duplicate) {
    // Block confirmed batches — must rollback first
    if (duplicate.status === 'confirmed') {
      const dupStatus = t(STATUS_CONFIG[duplicate.status]?.label || duplicate.status)
      ElMessage.warning(t('payroll.jp.confirmed_block_hint', {
        entity: entityLabel(createForm.value.entity_id),
        month: createForm.value.payroll_month,
        status: dupStatus,
      }))
      return
    }
    // draft / calculated → auto-void with confirmation
    const dupStatus = t(STATUS_CONFIG[duplicate.status]?.label || duplicate.status)
    const msg = `${t('payroll.jp.duplicate_batch_warning')}\n\n${t('field.entity_id')}: ${entityLabel(createForm.value.entity_id)}\n${t('field.payroll_month')}: ${createForm.value.payroll_month}\n${t('field.status')}: ${dupStatus}\n\n${t('payroll.jp.auto_void_hint')}`
    try {
      await ElMessageBox.confirm(
        msg,
        t('payroll.jp.duplicate_batch_title'),
        { confirmButtonText: t('payroll.jp.void_and_create'), cancelButtonText: t('action.cancel'), type: 'warning' }
      )
    } catch { return }
  }

  creating.value = true
  try {
    const res = await api.createBatch(createForm.value)
    const data = res.data.data || {}
    createDialog.value = false
    if (data.auto_voided) {
      ElMessage.success(t('payroll.jp.sheet_created_with_void', { n: data.auto_voided }))
    } else {
      ElMessage.success(t('payroll.jp.sheet_created'))
    }
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { creating.value = false }
}

function viewDetail(id: string) { router.push(`${baseRoute}/batches/${id}`) }
function openVoid(id: string) { voidSheetId.value = id; voidReason.value = ''; voidDialog.value = true }

async function confirmVoid() {
  voiding.value = true
  try {
    await api.voidSheet(voidSheetId.value, { reason: voidReason.value })
    voidDialog.value = false
    ElMessage.success(t('payroll.jp.voided'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
  finally { voiding.value = false }
}

async function deleteSheet(id: string) {
  try {
    await ElMessageBox.confirm(t('payroll.jp.delete_confirm_msg'), t('action.delete'),
      { confirmButtonText: t('action.delete'), cancelButtonText: t('action.cancel'), type: 'warning' })
  } catch { return }
  try {
    // Auto-void if not already voided
    const batch = sheets.value.find((s: any) => s.batch_id === id)
    if (batch && batch.status !== 'voided') {
      await api.voidSheet(id, { reason: 'Auto-void before delete' })
    }
    await api.deleteSheet(id)
    ElMessage.success(t('payroll.jp.sheet_deleted'))
    await load()
  } catch (e: any) { ElMessage.error(e.message) }
}

// ── Global Audit Log ──
async function openGlobalAuditLogs() {
  auditDialog.value = true
  auditLoading.value = true
  expandedAudit.value = new Set()
  try {
    const res = await api.auditLogs()
    auditLogs.value = res.data.data || []
  } catch (e: any) { ElMessage.error(e.message) }
  finally { auditLoading.value = false }
}

onMounted(() => { load(); loadEntities() })
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.monthly_sheets') }}</h2>
      </div>
      <div class="toolbar-right">
        <el-button @click="openGlobalAuditLogs">{{ t('payroll.jp.audit_log') }}</el-button>
        <el-button type="primary" @click="createDialog = true">{{ t('payroll.jp.create_sheet') }}</el-button>
      </div>
    </div>

    <div class="fiori-filters">
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:260px">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
      </el-select>
      <el-date-picker v-model="filterMonth" type="month" value-format="YYYY-MM" :placeholder="t('field.payroll_month')" clearable style="width:170px" />
      <el-select v-model="filterStatus" :placeholder="t('field.status')" clearable style="width:140px">
        <el-option v-for="(cfg, key) in STATUS_CONFIG" :key="key" :label="t(cfg.label)" :value="key" />
      </el-select>
      <el-button type="primary" @click="applyFilter">{{ t('action.filter') }}</el-button>
      <el-button @click="clearFilter">{{ t('action.clear') }}</el-button>
    </div>

    <div class="fiori-card">
      <el-table :data="paged" v-loading="loading" border stripe size="small" style="width:100%">
        <el-table-column type="index" min-width="50" :index="(idx: number) => (page - 1) * pageSize + idx + 1" />
        <el-table-column prop="batch_id" :label="t('field.sheet_id')" min-width="230" show-overflow-tooltip />
        <el-table-column prop="payroll_month" :label="t('field.payroll_month')" min-width="110" />
        <el-table-column :label="t('field.entity_id')" min-width="270" show-overflow-tooltip>
          <template #default="{row}">{{ entityLabel(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.status')" min-width="120">
          <template #default="{row}"><el-tag :type="(STATUS_CONFIG[row.status]?.type||'') as any" size="small">{{ t(STATUS_CONFIG[row.status]?.label||row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="employee_count" :label="t('field.employee_count')" min-width="80" align="center" />
        <el-table-column prop="gross_total" :label="t('field.gross_total')" min-width="130" align="right">
          <template #default="{row}">{{ row.gross_total ? fmtCurrency(row.gross_total) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="deduction_total" :label="t('field.deduction_total')" min-width="130" align="right">
          <template #default="{row}">{{ row.deduction_total ? fmtCurrency(row.deduction_total) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="net_total" :label="t('field.net_total')" min-width="130" align="right">
          <template #default="{row}">{{ row.net_total ? fmtCurrency(row.net_total) : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" min-width="200" fixed="right">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="viewDetail(row.batch_id)">{{ t('action.detail') }}</el-button>
            <el-button v-if="row.status==='draft'" size="small" text type="danger" @click="openVoid(row.batch_id)">{{ t('payroll.jp.void') }}</el-button>
            <el-button v-if="row.status!=='confirmed'" size="small" text type="danger" @click="deleteSheet(row.batch_id)">{{ t('action.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding:0 4px">
        <span class="helper-text">{{ filtered.length }} {{ t('action.records_total') }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filtered.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
          small
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <el-dialog v-model="createDialog" :title="t('payroll.jp.create_sheet')" width="480px">
      <el-form :model="createForm" label-width="140px">
        <el-form-item :label="t('field.payroll_month')">
          <el-date-picker v-model="createForm.payroll_month" type="month" value-format="YYYY-MM" :placeholder="t('field.payroll_month')" style="width:100%" />
          <div class="form-hint">{{ t('payroll.sg.create_sheet_hint') }}</div>
        </el-form-item>
        <el-form-item :label="t('field.entity_id')">
          <el-select v-model="createForm.entity_id" style="width:100%">
            <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('field.working_days_in_month')">
          <el-input-number v-model="createForm.working_days_in_month" :min="1" :max="31" :precision="1" style="width:100%" />
          <div class="form-hint">{{ t('payroll.jp.working_days_hint') }}</div>
        </el-form-item>
        <el-form-item :label="t('field.notes')">
          <el-input v-model="createForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog=false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="createSheet">{{ t('action.create') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="voidDialog" :title="t('payroll.jp.void_sheet')" width="420px">
      <p>{{ t('payroll.jp.void_confirm') }}</p>
      <el-input v-model="voidReason" :placeholder="t('field.void_reason')" type="textarea" :rows="2" />
      <template #footer>
        <el-button @click="voidDialog=false">{{ t('action.cancel') }}</el-button>
        <el-button type="danger" :loading="voiding" @click="confirmVoid">{{ t('payroll.jp.void') }}</el-button>
      </template>
    </el-dialog>

    <!-- ═══ Global Audit Log Dialog ═══ -->
    <el-dialog v-model="auditDialog" :title="t('payroll.jp.audit_log')" width="780px" top="3vh">
      <div v-loading="auditLoading" style="max-height:560px;overflow-y:auto">
        <div v-if="auditLogs.length === 0 && !auditLoading" style="text-align:center;padding:40px;color:#9ca3af">
          {{ t('payroll.jp.no_records') }}
        </div>
        <div v-for="(log, idx) in auditLogs" :key="idx" class="audit-item" @click="toggleAuditDetail(idx)">
          <div class="audit-line">
            <div class="audit-body">
              <div class="audit-head">
                <el-tag size="small" :color="actionLabel(log.action).color" effect="dark" style="color:#fff">
                  {{ actionLabel(log.action).label }}
                </el-tag>
                <span class="audit-user">{{ log.user_name }}</span>
                <span class="audit-time">{{ (log.created_at || '').replace('T', ' ').substring(0, 19) }}</span>
              </div>
              <div class="audit-summary">
                <span class="audit-record-id">{{ log.record_id }}</span>
                <span v-if="log.table_name" class="audit-table">[{{ log.table_name }}]</span>
                {{ parseAuditValue(log.after_value) || parseAuditValue(log.before_value) || '—' }}
              </div>
              <div v-if="expandedAudit.has(idx)" class="audit-expand">
                <div v-if="log.before_value" class="audit-json-label">Before:</div>
                <pre v-if="log.before_value" class="audit-json">{{ typeof log.before_value === 'string' ? log.before_value : JSON.stringify(log.before_value, null, 2) }}</pre>
                <div v-if="log.after_value" class="audit-json-label">After:</div>
                <pre v-if="log.after_value" class="audit-json">{{ typeof log.after_value === 'string' ? log.after_value : JSON.stringify(log.after_value, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="helper-text" style="margin-top:8px">{{ auditLogs.length }} {{ t('action.records_total') }}</div>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width:1500px; margin:0 auto; padding:24px; font-size:15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.toolbar-right { display:flex; gap:8px; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; padding:16px; }
.fiori-card :deep(.el-table) { width: 100% !important; }
.fiori-card :deep(.el-table__body-wrapper) { overflow-x: auto !important; }
.form-hint { font-size:.78rem; color:#6b7280; margin-top:4px; }
.helper-text { color:#6b7280; font-size:.85rem; }

/* ── Audit Timeline ── */
.audit-item { cursor:pointer; padding:8px 0; border-bottom:1px solid #f3f4f6; transition:background .15s; }
.audit-item:hover { background:#fafbfc; }
.audit-line { display:flex; gap:12px; align-items:flex-start; }
.audit-body { flex:1; min-width:0; }
.audit-head { display:flex; align-items:center; gap:10px; margin-bottom:3px; flex-wrap:wrap; }
.audit-user { font-weight:600; color:#1d2a3a; font-size:.9rem; }
.audit-time { color:#9ca3af; font-size:.8rem; margin-left:auto; }
.audit-summary { color:#6b7280; font-size:.85rem; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.audit-record-id { font-family:monospace; font-size:.78rem; color:#9ca3af; background:#f3f4f6; padding:1px 6px; border-radius:4px; }
.audit-table { font-size:.75rem; color:#9ca3af; }
.audit-expand { margin-top:8px; padding:8px 10px; background:#f9fafb; border-radius:6px; }
.audit-json-label { font-size:.75rem; font-weight:700; color:#6b7280; margin:4px 0 2px; }
.audit-json { font-size:.75rem; color:#1d2a3a; white-space:pre-wrap; word-break:break-all; margin:0; }
</style>
