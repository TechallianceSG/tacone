<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { masterdataApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/date'

const { t } = useI18n()

interface Entity {
  entity_id: string
  entity_code: string
  entity_name_en: string
  entity_name_ja: string
  entity_name_zh: string
  legal_name: string
  registration_number: string
  tax_registration_number: string
  country: string
  currency: string
  status: string
  created_at: string
  updated_at: string
}

const entities = ref<Entity[]>([])
const loading = ref(false)
const searchText = ref('')
const statusFilter = ref('')

// Dialog state
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<string | null>(null)
const form = ref({
  entity_code: '',
  legal_name: '',
  entity_name_en: '',
  entity_name_ja: '',
  entity_name_zh: '',
  registration_number: '',
  tax_registration_number: '',
  country: '',
  currency: '',
  status: 'active',
  change_reason: '',
  masterdata_change_ack: false,
})
const submitting = ref(false)
const formErrors = ref<string[]>([])

// Pagination
const currentPage = ref(1)
const pageSize = ref(20)

const filteredEntities = computed(() => {
  let list = entities.value
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(e =>
      (e.entity_code || '').toLowerCase().includes(q) ||
      (e.entity_name_en || '').toLowerCase().includes(q) ||
      (e.entity_name_ja || '').includes(q) ||
      (e.entity_name_zh || '').includes(q) ||
      (e.legal_name || '').toLowerCase().includes(q) ||
      (e.country || '').toLowerCase().includes(q)
    )
  }
  if (statusFilter.value) {
    list = list.filter(e => e.status === statusFilter.value)
  }
  return list
})

const pagedEntities = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredEntities.value.slice(start, start + pageSize.value)
})

const totalFiltered = computed(() => filteredEntities.value.length)

function resetPagination() {
  currentPage.value = 1
}

async function loadEntities() {
  loading.value = true
  try {
    const { data } = await masterdataApi.entities()
    entities.value = data?.entities || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to load entities')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.value = {
    entity_code: '',
    legal_name: '',
    entity_name_en: '',
    entity_name_ja: '',
    entity_name_zh: '',
    registration_number: '',
    tax_registration_number: '',
    country: '',
    currency: '',
    status: 'active',
    change_reason: '',
    masterdata_change_ack: false,
  }
  formErrors.value = []
  dialogVisible.value = true
}

function openEdit(entity: Entity) {
  dialogMode.value = 'edit'
  editingId.value = entity.entity_id
  form.value = {
    entity_code: entity.entity_code || '',
    legal_name: entity.legal_name || '',
    entity_name_en: entity.entity_name_en || '',
    entity_name_ja: entity.entity_name_ja || '',
    entity_name_zh: entity.entity_name_zh || '',
    registration_number: entity.registration_number || '',
    tax_registration_number: entity.tax_registration_number || '',
    country: entity.country || '',
    currency: entity.currency || '',
    status: entity.status || 'active',
    change_reason: '',
    masterdata_change_ack: false,
  }
  formErrors.value = []
  dialogVisible.value = true
}

async function handleSubmit() {
  formErrors.value = []
  if (!form.value.masterdata_change_ack) {
    formErrors.value.push(t('validation.change_ack_required'))
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      entity_code: form.value.entity_code,
      legal_name: form.value.legal_name,
      entity_name_en: form.value.entity_name_en,
      entity_name_ja: form.value.entity_name_ja,
      entity_name_zh: form.value.entity_name_zh,
      registration_number: form.value.registration_number,
      tax_registration_number: form.value.tax_registration_number,
      country: form.value.country,
      currency: form.value.currency,
      status: form.value.status,
      change_reason: form.value.change_reason,
    }
    if (dialogMode.value === 'create') {
      await masterdataApi.createEntity(payload)
      ElMessage.success(t('entity.saved_message'))
    } else {
      await masterdataApi.updateEntity(editingId.value!, payload)
      ElMessage.success(t('entity.updated_message'))
    }
    dialogVisible.value = false
    await loadEntities()
  } catch (e: any) {
    const errData = e?.response?.data
    if (errData?.errors) {
      formErrors.value = Array.isArray(errData.errors) ? errData.errors : [errData.error || 'Unknown error']
    } else {
      formErrors.value = [errData?.error || e?.message || 'Failed to save']
    }
  } finally {
    submitting.value = false
  }
}

async function handleDelete(entity: Entity) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate', { record: entity.entity_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteEntity(entity.entity_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('entity.deactivated'))
    await loadEntities()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to deactivate')
    }
  }
}

async function handleReactivate(entity: Entity) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: entity.entity_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    await masterdataApi.updateEntity(entity.entity_id, {
      entity_code: entity.entity_code,
      legal_name: entity.legal_name || '',
      entity_name_en: entity.entity_name_en || '',
      entity_name_ja: entity.entity_name_ja || '',
      entity_name_zh: entity.entity_name_zh || '',
      registration_number: entity.registration_number || '',
      tax_registration_number: entity.tax_registration_number || '',
      country: entity.country || '',
      currency: entity.currency || '',
      status: 'active',
      change_reason: 'Reactivated from portal',
    })
    ElMessage.success(t('entity.updated_message'))
    await loadEntities()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to reactivate')
    }
  }
}

function statusTagType(status: string) {
  return status === 'active' ? 'success' : status === 'inactive' ? 'info' : 'danger'
}

onMounted(() => {
  loadEntities()
})
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchText"
          :placeholder="t('action.filter')"
          :prefix-icon="Search"
          clearable
          style="width: 260px"
          size="default"
          @input="resetPagination"
        />
        <el-select
          v-model="statusFilter"
          :placeholder="t('common.status')"
          clearable
          style="width: 140px"
          size="default"
          @change="resetPagination"
        >
          <el-option :label="t('entity.status.active')" value="active" />
          <el-option :label="t('entity.status.inactive')" value="inactive" />
        </el-select>
        <el-button :icon="Refresh" size="default" @click="loadEntities">{{ t('action.filter') }}</el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" size="default" @click="openCreate">
          {{ t('action.create_entity') }}
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <el-table
      :data="pagedEntities"
      v-loading="loading"
      stripe
      border
      style="width: 100%"
      empty-text="—"
    >
      <el-table-column prop="entity_code" :label="t('entity.entity_code')" min-width="120" />
      <el-table-column prop="entity_name_en" :label="t('entity.entity_name_en')" min-width="140" />
      <el-table-column prop="entity_name_ja" :label="t('entity.entity_name_ja')" min-width="140" />
      <el-table-column prop="entity_name_zh" :label="t('entity.entity_name_zh')" min-width="140" />
      <el-table-column prop="country" :label="t('entity.country')" width="100" />
      <el-table-column prop="currency" :label="t('entity.currency')" width="90" />
      <el-table-column prop="status" :label="t('common.status')" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ t(`entity.status.${row.status}`, row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('common.updated_at')" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('action.actions')" width="150" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" size="small" @click="openEdit(row)">{{ t('action.edit') }}</el-button>
          <el-button
            v-if="row.status === 'active'"
            text
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >{{ t('action.deactivate') }}</el-button>
          <el-button
            v-if="row.status === 'inactive'"
            text
            type="success"
            size="small"
            @click="handleReactivate(row)"
          >{{ t('action.activate') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination + Count -->
    <div class="table-footer">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalFiltered"
        layout="prev, pager, next"
        background
        small
      />
      <div class="record-count">{{ totalFiltered }} record(s) total</div>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? t('entity.new_title') : t('entity.edit_title')"
      width="640px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleSubmit">
        <el-form-item :label="t('entity.entity_code')" required>
          <el-input v-model="form.entity_code" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('entity.legal_name')">
          <el-input v-model="form.legal_name" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_en')" required>
          <el-input v-model="form.entity_name_en" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_ja')">
          <el-input v-model="form.entity_name_ja" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_zh')">
          <el-input v-model="form.entity_name_zh" />
        </el-form-item>
        <el-form-item :label="t('entity.registration_number')">
          <el-input v-model="form.registration_number" />
        </el-form-item>
        <el-form-item :label="t('entity.tax_registration_number')">
          <el-input v-model="form.tax_registration_number" />
        </el-form-item>
        <el-form-item :label="t('entity.country')">
          <el-input v-model="form.country" />
        </el-form-item>
        <el-form-item :label="t('entity.currency')">
          <el-input v-model="form.currency" />
        </el-form-item>
        <el-form-item :label="t('common.status')">
          <el-select v-model="form.status" style="width:100%">
            <el-option :label="t('entity.status.active')" value="active" />
            <el-option :label="t('entity.status.inactive')" value="inactive" />
          </el-select>
        </el-form-item>

        <!-- Change Governance -->
        <el-divider />
        <el-form-item :label="t('governance.change_reason')" required>
          <el-input v-model="form.change_reason" type="textarea" :rows="2" :placeholder="t('governance.change_reason')" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.masterdata_change_ack">
            {{ t('governance.acknowledge') }}
          </el-checkbox>
        </el-form-item>

        <!-- Errors -->
        <el-alert
          v-if="formErrors.length > 0"
          :title="formErrors.join(', ')"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ dialogMode === 'create' ? t('action.create') : t('action.save_update') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
.record-count {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
}
</style>
