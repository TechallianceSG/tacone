<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { masterdataApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/date'

const { t } = useI18n()

interface Department {
  department_id: string
  department_code: string
  department_name_en: string
  department_name_ja: string
  department_name_zh: string
  entity_id: string
  status: string
  created_at: string
  updated_at: string
}

interface EntityOption {
  entity_id: string
  entity_code: string
  entity_name_en: string
}

const departments = ref<Department[]>([])
const entities = ref<EntityOption[]>([])
const loading = ref(false)
const searchText = ref('')
const statusFilter = ref('')
const entityFilter = ref('')

// Dialog
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<string | null>(null)
const form = ref({
  department_code: '',
  department_name_en: '',
  department_name_ja: '',
  department_name_zh: '',
  entity_id: '',
  status: 'active',
  change_reason: '',
  masterdata_change_ack: false,
})
const submitting = ref(false)
const formErrors = ref<string[]>([])

// Pagination
const currentPage = ref(1)
const pageSize = ref(20)

const filteredDepartments = computed(() => {
  let list = departments.value
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(d =>
      (d.department_code || '').toLowerCase().includes(q) ||
      (d.department_name_en || '').toLowerCase().includes(q) ||
      (d.department_name_ja || '').includes(q) ||
      (d.department_name_zh || '').includes(q)
    )
  }
  if (statusFilter.value) {
    list = list.filter(d => d.status === statusFilter.value)
  }
  if (entityFilter.value) {
    list = list.filter(d => d.entity_id === entityFilter.value)
  }
  return list
})

const pagedDepartments = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredDepartments.value.slice(start, start + pageSize.value)
})

const totalFiltered = computed(() => filteredDepartments.value.length)

function entityLabel(id: string) {
  const e = entities.value.find(en => en.entity_id === id)
  return e ? `${e.entity_code} - ${e.entity_name_en}` : id
}

function resetPagination() {
  currentPage.value = 1
}

async function loadData() {
  loading.value = true
  try {
    const [er, dr] = await Promise.all([masterdataApi.entities(), masterdataApi.departments()])
    entities.value = er.data?.entities || []
    departments.value = dr.data?.departments || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to load')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.value = {
    department_code: '',
    department_name_en: '',
    department_name_ja: '',
    department_name_zh: '',
    entity_id: '',
    status: 'active',
    change_reason: '',
    masterdata_change_ack: false,
  }
  formErrors.value = []
  dialogVisible.value = true
}

function openEdit(dep: Department) {
  dialogMode.value = 'edit'
  editingId.value = dep.department_id
  form.value = {
    department_code: dep.department_code || '',
    department_name_en: dep.department_name_en || '',
    department_name_ja: dep.department_name_ja || '',
    department_name_zh: dep.department_name_zh || '',
    entity_id: dep.entity_id || '',
    status: dep.status || 'active',
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
  if (!form.value.entity_id) {
    formErrors.value.push(t('validation.parent_entity_required'))
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      department_code: form.value.department_code,
      department_name_en: form.value.department_name_en,
      department_name_ja: form.value.department_name_ja,
      department_name_zh: form.value.department_name_zh,
      entity_id: form.value.entity_id,
      status: form.value.status,
      change_reason: form.value.change_reason,
    }
    if (dialogMode.value === 'create') {
      await masterdataApi.createDepartment(payload)
      ElMessage.success(t('department.saved_message'))
    } else {
      await masterdataApi.updateDepartment(editingId.value!, payload)
      ElMessage.success(t('department.updated_message'))
    }
    dialogVisible.value = false
    await loadData()
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

async function handleDelete(dep: Department) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate_department', { record: dep.department_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteDepartment(dep.department_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('department.deactivated'))
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to deactivate')
    }
  }
}

async function handleReactivate(dep: Department) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: dep.department_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    await masterdataApi.updateDepartment(dep.department_id, {
      department_code: dep.department_code,
      department_name_en: dep.department_name_en || '',
      department_name_ja: dep.department_name_ja || '',
      department_name_zh: dep.department_name_zh || '',
      entity_id: dep.entity_id,
      status: 'active',
      change_reason: 'Reactivated from portal',
    })
    ElMessage.success(t('department.updated_message'))
    await loadData()
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
  loadData()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchText"
          :placeholder="t('action.filter')"
          :prefix-icon="Search"
          clearable
          style="width: 240px"
          size="default"
          @input="resetPagination"
        />
        <el-select
          v-model="entityFilter"
          :placeholder="t('entity.title')"
          clearable
          style="width: 200px"
          size="default"
          @change="resetPagination"
        >
          <el-option
            v-for="e in entities"
            :key="e.entity_id"
            :label="`${e.entity_code} - ${e.entity_name_en}`"
            :value="e.entity_id"
          />
        </el-select>
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
        <el-button :icon="Refresh" size="default" @click="loadData">{{ t('action.filter') }}</el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" size="default" @click="openCreate">
          {{ t('action.create_department') }}
        </el-button>
      </div>
    </div>

    <el-table :data="pagedDepartments" v-loading="loading" stripe border style="width: 100%" empty-text="—">
      <el-table-column prop="department_code" :label="t('department.department_code')" min-width="130" />
      <el-table-column prop="department_name_en" :label="t('department.department_name_en')" min-width="140" />
      <el-table-column prop="department_name_ja" :label="t('department.department_name_ja')" min-width="140" />
      <el-table-column prop="department_name_zh" :label="t('department.department_name_zh')" min-width="140" />
      <el-table-column :label="t('department.parent_entity')" min-width="180">
        <template #default="{ row }">{{ entityLabel(row.entity_id) }}</template>
      </el-table-column>
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
            text type="danger" size="small"
            @click="handleDelete(row)"
          >{{ t('action.deactivate') }}</el-button>
          <el-button
            v-if="row.status === 'inactive'"
            text type="success" size="small"
            @click="handleReactivate(row)"
          >{{ t('action.activate') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

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

    <!-- Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? t('department.new_title') : t('department.edit_title')"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleSubmit">
        <el-form-item :label="t('department.parent_entity')" required>
          <el-select v-model="form.entity_id" :disabled="dialogMode === 'edit'" style="width:100%">
            <el-option
              v-for="e in entities"
              :key="e.entity_id"
              :label="`${e.entity_code} - ${e.entity_name_en}`"
              :value="e.entity_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('department.department_code')" required>
          <el-input v-model="form.department_code" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_en')" required>
          <el-input v-model="form.department_name_en" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_ja')">
          <el-input v-model="form.department_name_ja" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_zh')">
          <el-input v-model="form.department_name_zh" />
        </el-form-item>
        <el-form-item :label="t('common.status')">
          <el-select v-model="form.status" style="width:100%">
            <el-option :label="t('entity.status.active')" value="active" />
            <el-option :label="t('entity.status.inactive')" value="inactive" />
          </el-select>
        </el-form-item>

        <el-divider />
        <el-form-item :label="t('governance.change_reason')" required>
          <el-input v-model="form.change_reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.masterdata_change_ack">
            {{ t('governance.acknowledge') }}
          </el-checkbox>
        </el-form-item>

        <el-alert
          v-if="formErrors.length > 0"
          :title="formErrors.join(', ')"
          type="error" show-icon :closable="false"
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
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.table-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.record-count { font-size: 0.85rem; color: var(--el-text-color-secondary); }
</style>
