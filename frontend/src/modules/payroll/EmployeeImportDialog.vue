<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

interface ImportApi {
  importableEmployees: (params?: Record<string, any>) => Promise<any>
  importEmployees: (data: { employee_ids: string[] }) => Promise<any>
}

const props = defineProps<{
  modelValue: boolean
  countryCode: 'jp' | 'sg' | 'cn'
  api: ImportApi
  entities?: any[]
  departments?: any[]
  entityResolver?: (id: string) => string
  /** Optional custom loader — falls back to api.importableEmployees() if not provided */
  loadFn?: () => Promise<any[]>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'imported': []
}>()

const { t } = useI18n()

const loading = ref(false)
const importing = ref(false)
const importableList = ref<any[]>([])
const selectedImportIds = ref<string[]>([])

// Filters (primarily for JP, can be used by others too)
const importSearch = ref('')
const importFilterEntity = ref('')
const importFilterDept = ref('')

const filteredList = computed(() => {
  let result = importableList.value
  if (importFilterEntity.value) result = result.filter((e: any) => e.entity_id === importFilterEntity.value)
  if (importFilterDept.value) {
    result = result.filter((e: any) =>
      (e.department_name || e.department || '') === importFilterDept.value
    )
  }
  if (importSearch.value) {
    const q = importSearch.value.toLowerCase()
    result = result.filter((e: any) =>
      (e.employee_number || e.employee_no || '').toLowerCase().includes(q) ||
      (e.employee_name || e.display_name || '').toLowerCase().includes(q)
    )
  }
  return result
})

const entityLabel = (entityId: string) => {
  if (props.entityResolver) return props.entityResolver(entityId)
  if (props.entities) {
    const found = props.entities.find((e: any) => e.entity_id === entityId || e.entity_code === entityId)
    if (found) return `${found.entity_code || entityId} - ${found.entity_name_en || found.entity_name || ''}`
  }
  return entityId
}

const deptLabel = (row: any) => row.department_name || row.department || '-'

const displayName = (row: any) => row.display_name || row.employee_name || ''

async function loadImportable() {
  loading.value = true
  try {
    if (props.loadFn) {
      importableList.value = await props.loadFn()
    } else {
      const res = await props.api.importableEmployees()
      importableList.value = (res.data?.data || res.data || []) as any[]
    }
  } catch (e: any) {
    importableList.value = []
    ElMessage.error(e.message || 'Failed to load importable employees')
  } finally {
    loading.value = false
  }
}

async function doImport() {
  if (!selectedImportIds.value.length) return
  importing.value = true
  try {
    await props.api.importEmployees({ employee_ids: selectedImportIds.value })
    emit('update:modelValue', false)
    emit('imported')
    ElMessage.success(t('action.imported', { count: selectedImportIds.value.length }))
  } catch (e: any) {
    ElMessage.error(e.message || 'Import failed')
  } finally {
    importing.value = false
  }
}

function onOpen() {
  selectedImportIds.value = []
  importSearch.value = ''
  importFilterEntity.value = ''
  importFilterDept.value = ''
  loadImportable()
}

function onClose() {
  importableList.value = []
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
    @close="onClose"
    :title="t(`payroll.${countryCode}.import_employeeadmin`)"
    width="750px"
    top="2vh"
  >
    <!-- Filters -->
    <div class="fiori-filters" style="margin-bottom:12px; display:flex; gap:8px; flex-wrap:wrap">
      <el-input
        v-model="importSearch"
        :placeholder="t('action.search')"
        clearable
        style="width:200px"
      />
      <el-select
        v-if="entities?.length"
        v-model="importFilterEntity"
        :placeholder="t('field.entity_id')"
        clearable
        style="width:220px"
      >
        <el-option
          v-for="e in entities"
          :key="e.entity_id"
          :label="entityLabel(e.entity_id)"
          :value="e.entity_id"
        />
      </el-select>
      <el-select
        v-if="departments?.length"
        v-model="importFilterDept"
        :placeholder="t('field.department')"
        clearable
        style="width:180px"
      >
        <el-option
          v-for="d in departments"
          :key="d.department_id"
          :label="d.department_name_en || d.department_name_ja || d.department_name || d.department_id"
          :value="d.department_name_en || d.department_name_ja || d.department_name"
        />
      </el-select>
    </div>

    <!-- Table -->
    <el-table
      v-loading="loading"
      :data="filteredList"
      max-height="400"
      @selection-change="(rows: any[]) => selectedImportIds = rows.map((r: any) => r.employee_id)"
      border
      stripe
      size="small"
    >
      <el-table-column type="selection" width="45" />
      <el-table-column prop="employee_number" :label="t('field.employee_number')" min-width="130" />
      <el-table-column :label="t('field.employee_name')" min-width="160">
        <template #default="{ row }">{{ displayName(row) }}</template>
      </el-table-column>
      <el-table-column :label="t('field.entity_id')" min-width="220">
        <template #default="{ row }">{{ entityLabel(row.entity_id) }}</template>
      </el-table-column>
      <el-table-column :label="t('field.department')" min-width="140">
        <template #default="{ row }">{{ deptLabel(row) }}</template>
      </el-table-column>
    </el-table>

    <div class="helper-text" style="margin-top:8px">
      {{ filteredList.length }} {{ t('action.records_total') }}
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('action.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="importing"
        :disabled="!selectedImportIds.length"
        @click="doImport"
      >
        {{ t('action.import') }} ({{ selectedImportIds.length }})
      </el-button>
    </template>
  </el-dialog>
</template>
