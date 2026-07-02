<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { masterdataApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/date'

const { t } = useI18n()

interface Team {
  team_id: string
  team_code: string
  team_name_en: string
  team_name_ja: string
  team_name_zh: string
  department_id: string
  status: string
  created_at: string
  updated_at: string
}

interface EntityOption {
  entity_id: string
  entity_code: string
  entity_name_en: string
}

interface DepartmentOption {
  department_id: string
  department_code: string
  department_name_en: string
  entity_id: string
}

const teams = ref<Team[]>([])
const entities = ref<EntityOption[]>([])
const allDepartments = ref<DepartmentOption[]>([])
const loading = ref(false)
const searchText = ref('')
const statusFilter = ref('')
const entityFilter = ref('')
const departmentFilter = ref('')

// Dialog
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<string | null>(null)
const form = ref({
  team_code: '',
  team_name_en: '',
  team_name_ja: '',
  team_name_zh: '',
  entity_id: '',
  department_id: '',
  status: 'active',
  change_reason: '',
  masterdata_change_ack: false,
})
const submitting = ref(false)
const formErrors = ref<string[]>([])

// Pagination
const currentPage = ref(1)
const pageSize = ref(20)

// Derived: departments filtered by selected entity
const filteredDeptOptions = computed(() => {
  if (!form.value.entity_id) return allDepartments.value
  return allDepartments.value.filter(d => d.entity_id === form.value.entity_id)
})

// Filter departments by entity for the filter bar
const filterDeptOptions = computed(() => {
  if (!entityFilter.value) return allDepartments.value
  return allDepartments.value.filter(d => d.entity_id === entityFilter.value)
})

// Watch entity filter → reset department filter
watch(entityFilter, () => {
  departmentFilter.value = ''
  resetPagination()
})

const filteredTeams = computed(() => {
  let list = teams.value
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(t =>
      (t.team_code || '').toLowerCase().includes(q) ||
      (t.team_name_en || '').toLowerCase().includes(q) ||
      (t.team_name_ja || '').includes(q) ||
      (t.team_name_zh || '').includes(q)
    )
  }
  if (statusFilter.value) {
    list = list.filter(t => t.status === statusFilter.value)
  }
  if (departmentFilter.value) {
    list = list.filter(t => t.department_id === departmentFilter.value)
  } else if (entityFilter.value) {
    // Filter teams whose parent department belongs to the selected entity
    const deptIds = new Set(allDepartments.value.filter(d => d.entity_id === entityFilter.value).map(d => d.department_id))
    list = list.filter(t => deptIds.has(t.department_id))
  }
  return list
})

const pagedTeams = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTeams.value.slice(start, start + pageSize.value)
})

const totalFiltered = computed(() => filteredTeams.value.length)

function entityLabelForTeam(team: Team) {
  const dep = allDepartments.value.find(d => d.department_id === team.department_id)
  if (!dep) return ''
  const ent = entities.value.find(e => e.entity_id === dep.entity_id)
  return ent ? `${ent.entity_code} - ${ent.entity_name_en}` : dep.entity_id
}

function deptLabel(id: string) {
  const d = allDepartments.value.find(dep => dep.department_id === id)
  return d ? `${d.department_code} - ${d.department_name_en}` : id
}

function resetPagination() {
  currentPage.value = 1
}

// When entity changes in form, clear department
watch(() => form.value.entity_id, () => {
  form.value.department_id = ''
})

async function loadData() {
  loading.value = true
  try {
    const [er, dr, tr] = await Promise.all([
      masterdataApi.entities(),
      masterdataApi.departments(),
      masterdataApi.teams(),
    ])
    entities.value = er.data?.entities || []
    allDepartments.value = dr.data?.departments || []
    teams.value = tr.data?.teams || []
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
    team_code: '',
    team_name_en: '',
    team_name_ja: '',
    team_name_zh: '',
    entity_id: '',
    department_id: '',
    status: 'active',
    change_reason: '',
    masterdata_change_ack: false,
  }
  formErrors.value = []
  dialogVisible.value = true
}

function openEdit(team: Team) {
  dialogMode.value = 'edit'
  editingId.value = team.team_id
  const dep = allDepartments.value.find(d => d.department_id === team.department_id)
  form.value = {
    team_code: team.team_code || '',
    team_name_en: team.team_name_en || '',
    team_name_ja: team.team_name_ja || '',
    team_name_zh: team.team_name_zh || '',
    entity_id: dep?.entity_id || '',
    department_id: team.department_id || '',
    status: team.status || 'active',
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
  if (!form.value.department_id) {
    formErrors.value.push(t('validation.parent_department_required'))
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      team_code: form.value.team_code,
      team_name_en: form.value.team_name_en,
      team_name_ja: form.value.team_name_ja,
      team_name_zh: form.value.team_name_zh,
      entity_id: form.value.entity_id,
      department_id: form.value.department_id,
      status: form.value.status,
      change_reason: form.value.change_reason,
    }
    if (dialogMode.value === 'create') {
      await masterdataApi.createTeam(payload)
      ElMessage.success(t('team.saved_message'))
    } else {
      await masterdataApi.updateTeam(editingId.value!, payload)
      ElMessage.success(t('team.updated_message'))
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

async function handleDelete(team: Team) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate_team', { record: team.team_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteTeam(team.team_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('team.deactivated'))
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to deactivate')
    }
  }
}

async function handleReactivate(team: Team) {
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: team.team_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    const allDepts = allDepartments.value
    const dep = allDepts.find(d => d.department_id === team.department_id)
    await masterdataApi.updateTeam(team.team_id, {
      team_code: team.team_code,
      team_name_en: team.team_name_en || '',
      team_name_ja: team.team_name_ja || '',
      team_name_zh: team.team_name_zh || '',
      entity_id: dep?.entity_id || '',
      department_id: team.department_id,
      status: 'active',
      change_reason: 'Reactivated from portal',
    })
    ElMessage.success(t('team.updated_message'))
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
          style="width: 220px"
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
          v-model="departmentFilter"
          :placeholder="t('department.title')"
          clearable
          style="width: 200px"
          size="default"
          @change="resetPagination"
        >
          <el-option
            v-for="d in filterDeptOptions"
            :key="d.department_id"
            :label="`${d.department_code} - ${d.department_name_en}`"
            :value="d.department_id"
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
          {{ t('action.create_team') }}
        </el-button>
      </div>
    </div>

    <el-table :data="pagedTeams" v-loading="loading" stripe border style="width: 100%" empty-text="—">
      <el-table-column prop="team_code" :label="t('team.team_code')" min-width="130" />
      <el-table-column prop="team_name_en" :label="t('team.team_name_en')" min-width="140" />
      <el-table-column prop="team_name_ja" :label="t('team.team_name_ja')" min-width="140" />
      <el-table-column prop="team_name_zh" :label="t('team.team_name_zh')" min-width="140" />
      <el-table-column :label="t('team.parent_entity')" min-width="180">
        <template #default="{ row }">{{ entityLabelForTeam(row) }}</template>
      </el-table-column>
      <el-table-column :label="t('team.parent_department')" min-width="180">
        <template #default="{ row }">{{ deptLabel(row.department_id) }}</template>
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
      :title="dialogMode === 'create' ? t('team.new_title') : t('team.edit_title')"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleSubmit">
        <el-form-item :label="t('team.parent_entity')" required>
          <el-select v-model="form.entity_id" :disabled="dialogMode === 'edit'" style="width:100%" @change="form.department_id = ''">
            <el-option
              v-for="e in entities"
              :key="e.entity_id"
              :label="`${e.entity_code} - ${e.entity_name_en}`"
              :value="e.entity_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('team.parent_department')" required>
          <el-select v-model="form.department_id" :disabled="dialogMode === 'edit'" style="width:100%">
            <el-option
              v-for="d in filteredDeptOptions"
              :key="d.department_id"
              :label="`${d.department_code} - ${d.department_name_en}`"
              :value="d.department_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('team.team_code')" required>
          <el-input v-model="form.team_code" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_en')" required>
          <el-input v-model="form.team_name_en" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_ja')">
          <el-input v-model="form.team_name_ja" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_zh')">
          <el-input v-model="form.team_name_zh" />
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
