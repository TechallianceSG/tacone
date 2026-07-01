<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { payrollJpApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const sheets = ref<any[]>([])
const filterEntity = ref('')
const filterMonth = ref('')
const filterStatus = ref('')

const createDialog = ref(false)
const creating = ref(false)
const createForm = ref({ payroll_month: new Date().toISOString().slice(0, 7), entity_id: '', notes: '' })

const voidDialog = ref(false)
const voiding = ref(false)
const voidSheetId = ref('')
const voidReason = ref('')

const entities = ref<any[]>([])

const statusConfig: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.jp.status_draft' },
  calculated: { type: 'warning', label: 'payroll.jp.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.jp.status_confirmed' },
  voided: { type: 'danger', label: 'payroll.jp.status_voided' },
}

const filtered = computed(() => {
  let result = sheets.value
  if (filterEntity.value) result = result.filter((s: any) => s.entity_id === filterEntity.value)
  if (filterMonth.value) result = result.filter((s: any) => s.payroll_month === filterMonth.value)
  if (filterStatus.value) result = result.filter((s: any) => s.status === filterStatus.value)
  return result
})

async function load() { loading.value = true; try { const res = await payrollJpApi.sheets(); sheets.value = res.data.data?.items || res.data.data || [] } catch (e: any) { ElMessage.error(e.message) } finally { loading.value = false } }
async function loadEntities() { try { const res = await fetch('/api/masterdata/entities').then(r => r.json()); entities.value = res.data || [] } catch (_) {} }
function entityLabel(id: string) { const f = entities.value.find((e: any) => e.entity_id === id); if (!f) return id; return `${f.entity_code || f.entity_id} - ${f.entity_name || ''} (${f.country || ''})` }

async function createSheet() { if (!createForm.value.entity_id) { ElMessage.warning(t('field.entity_id') + ' required'); return }; creating.value = true; try { await payrollJpApi.createBatch(createForm.value); createDialog.value = false; ElMessage.success(t('payroll.jp.sheet_created')); await load() } catch (e: any) { ElMessage.error(e.message) } finally { creating.value = false } }
function viewDetail(id: string) { router.push(`/payroll/jp/batches/${id}`) }
function goToRelease(id: string) { router.push(`/payroll/jp/batches/${id}/release`) }
function openVoid(id: string) { voidSheetId.value = id; voidReason.value = ''; voidDialog.value = true }
async function confirmVoid() { voiding.value = true; try { await payrollJpApi.voidSheet(voidSheetId.value, { reason: voidReason.value }); voidDialog.value = false; ElMessage.success(t('payroll.jp.voided')); await load() } catch (e: any) { ElMessage.error(e.message) } finally { voiding.value = false } }
async function deleteSheet(id: string) { try { await ElMessageBox.confirm(t('payroll.jp.delete_confirm_msg'), t('action.delete'), { confirmButtonText: t('action.delete'), cancelButtonText: t('action.cancel'), type: 'warning' }) } catch { return }; try { await payrollJpApi.deleteSheet(id); ElMessage.success(t('payroll.jp.sheet_deleted')); await load() } catch (e: any) { ElMessage.error(e.message) } }

onMounted(() => { load(); loadEntities() })
</script>

<template>
  <div class="fiori-page">
    <div class="fiori-toolbar">
      <div class="toolbar-left">
        <h2>{{ t('payroll.jp.monthly_sheets') }}</h2>
        <span class="count-chip">{{ filtered.length }} {{ t('action.records_total') }}</span>
      </div>
      <el-button type="primary" @click="createDialog = true">{{ t('payroll.jp.create_sheet') }}</el-button>
    </div>

    <div class="fiori-filters">
      <el-select v-model="filterEntity" :placeholder="t('field.entity_id')" clearable style="width:260px">
        <el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" />
      </el-select>
      <el-input v-model="filterMonth" :placeholder="t('field.payroll_month') + ' (YYYY-MM)'" clearable style="width:170px" />
      <el-select v-model="filterStatus" :placeholder="t('field.status')" clearable style="width:140px">
        <el-option v-for="(cfg, key) in statusConfig" :key="key" :label="t(cfg.label)" :value="key" />
      </el-select>
    </div>

    <div class="fiori-card">
      <el-table :data="filtered" v-loading="loading" border stripe size="small">
        <el-table-column prop="sheet_id" :label="t('field.sheet_id')" width="230" show-overflow-tooltip />
        <el-table-column prop="payroll_month" :label="t('field.payroll_month')" width="110" />
        <el-table-column :label="t('field.entity_id')" width="270" show-overflow-tooltip>
          <template #default="{row}">{{ entityLabel(row.entity_id) }}</template>
        </el-table-column>
        <el-table-column :label="t('field.status')" width="120">
          <template #default="{row}"><el-tag :type="(statusConfig[row.status]?.type||'') as any" size="small">{{ t(statusConfig[row.status]?.label||row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="employee_count" :label="t('field.employee_count')" width="80" align="center" />
        <el-table-column prop="gross_total" :label="t('field.gross_total')" width="130" align="right">
          <template #default="{row}">{{ row.gross_total ? '¥' + Number(row.gross_total).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="deduction_total" :label="t('field.deduction_total')" width="130" align="right">
          <template #default="{row}">{{ row.deduction_total ? '¥' + Number(row.deduction_total).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column prop="net_total" :label="t('field.net_total')" width="130" align="right">
          <template #default="{row}">{{ row.net_total ? '¥' + Number(row.net_total).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('field.actions')" width="200" fixed="right">
          <template #default="{row}">
            <el-button size="small" text type="primary" @click="viewDetail(row.sheet_id)">{{ t('action.detail') }}</el-button>
            <el-button v-if="row.status==='confirmed'" size="small" text type="success" @click="goToRelease(row.sheet_id)">{{ t('action.release') }}</el-button>
            <el-button v-if="row.status==='draft'" size="small" text type="danger" @click="openVoid(row.sheet_id)">{{ t('payroll.jp.void') }}</el-button>
            <el-button v-if="row.status==='voided'" size="small" text type="danger" @click="deleteSheet(row.sheet_id)">{{ t('action.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createDialog" :title="t('payroll.jp.create_sheet')" width="480px">
      <el-form :model="createForm" label-width="140px">
        <el-form-item :label="t('field.payroll_month')"><el-input v-model="createForm.payroll_month" placeholder="2026-07" /><div class="form-hint">{{ t('payroll.sg.create_sheet_hint') }}</div></el-form-item>
        <el-form-item :label="t('field.entity_id')"><el-select v-model="createForm.entity_id" style="width:100%"><el-option v-for="e in entities" :key="e.entity_id" :label="entityLabel(e.entity_id)" :value="e.entity_id" /></el-select></el-form-item>
        <el-form-item :label="t('field.notes')"><el-input v-model="createForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createDialog=false">{{ t('action.cancel') }}</el-button><el-button type="primary" :loading="creating" @click="createSheet">{{ t('action.create') }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="voidDialog" :title="t('payroll.jp.void_sheet')" width="420px">
      <p>{{ t('payroll.jp.void_confirm') }}</p>
      <el-input v-model="voidReason" :placeholder="t('field.void_reason')" type="textarea" :rows="2" />
      <template #footer><el-button @click="voidDialog=false">{{ t('action.cancel') }}</el-button><el-button type="danger" :loading="voiding" @click="confirmVoid">{{ t('payroll.jp.void') }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fiori-page { max-width:1500px; margin:0 auto; padding:24px; font-size:15px; }
.fiori-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
.toolbar-left { display:flex; align-items:center; gap:12px; }
.toolbar-left h2 { margin:0; font-size:1.3rem; font-weight:700; color:#1d2a3a; }
.count-chip { background:#e8f0fe; color:#1B6CB2; padding:2px 12px; border-radius:12px; font-size:.82rem; font-weight:600; }
.fiori-filters { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
.fiori-card { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.form-hint { font-size:.78rem; color:#6b7280; margin-top:4px; }
</style>
