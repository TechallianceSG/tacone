<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { masterdataApi } from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, OfficeBuilding, Folder, UserFilled } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/date'

const { t, locale } = useI18n()

// ── Interfaces ──
interface EntityRec {
  entity_id: string; entity_code: string; entity_name_en: string; entity_name_ja: string; entity_name_zh: string
  legal_name: string; registration_number: string; tax_registration_number: string
  country: string; currency: string; status: string; created_at: string; updated_at: string
}

interface DepartmentRec {
  department_id: string; department_code: string; department_name_en: string; department_name_ja: string; department_name_zh: string
  entity_id: string; status: string; created_at: string; updated_at: string
}

interface TeamRec {
  team_id: string; team_code: string; team_name_en: string; team_name_ja: string; team_name_zh: string
  department_id: string; status: string; created_at: string; updated_at: string
}

interface TreeNode {
  id: string
  type: 'entity' | 'department' | 'team'
  label: string
  code: string
  status: string
  children: TreeNode[]
  rawData: EntityRec | DepartmentRec | TeamRec
  childCount: number
}

// ── Helpers ──
function getDisplayName(raw: Record<string, any>, kind: 'entity' | 'department' | 'team'): string {
  const lang = locale.value
  const nameKey = `${kind}_name_${lang}`
  if (raw[nameKey]) return raw[nameKey]
  for (const l of ['en', 'ja', 'zh']) {
    const k = `${kind}_name_${l}`
    if (raw[k]) return raw[k]
  }
  return raw[`${kind}_code`] || ''
}

function entityLabel(e: EntityRec): string {
  return `${e.entity_code} - ${getDisplayName(e, 'entity')}`
}

// ── Data State ──
const loading = ref(false)
const entities = ref<EntityRec[]>([])
const departments = ref<DepartmentRec[]>([])
const teams = ref<TeamRec[]>([])

// ── Tree Data ──
const treeData = computed<TreeNode[]>(() => {
  const deptMap = new Map<string, DepartmentRec[]>()
  for (const d of departments.value) {
    const key = d.entity_id
    if (!deptMap.has(key)) deptMap.set(key, [])
    deptMap.get(key)!.push(d)
  }
  const teamMap = new Map<string, TeamRec[]>()
  for (const t of teams.value) {
    const key = t.department_id
    if (!teamMap.has(key)) teamMap.set(key, [])
    teamMap.get(key)!.push(t)
  }

  return entities.value
    .map((entity): TreeNode => {
      const childDepts = (deptMap.get(entity.entity_id) || [])
        .sort((a, b) => a.department_code.localeCompare(b.department_code))

      const deptNodes: TreeNode[] = childDepts.map((dept): TreeNode => {
        const childTeams = (teamMap.get(dept.department_id) || [])
          .sort((a, b) => a.team_code.localeCompare(b.team_code))

        const teamNodes: TreeNode[] = childTeams.map((team): TreeNode => ({
          id: `team-${team.team_id}`,
          type: 'team' as const,
          label: `${team.team_code} - ${getDisplayName(team, 'team')}`,
          code: team.team_code,
          status: team.status,
          children: [],
          rawData: team,
          childCount: 0,
        }))

        return {
          id: `dept-${dept.department_id}`,
          type: 'department' as const,
          label: `${dept.department_code} - ${getDisplayName(dept, 'department')}`,
          code: dept.department_code,
          status: dept.status,
          children: teamNodes,
          rawData: dept,
          childCount: teamNodes.length,
        }
      })

      return {
        id: `entity-${entity.entity_id}`,
        type: 'entity' as const,
        label: `${entity.entity_code} - ${getDisplayName(entity, 'entity')}`,
        code: entity.entity_code,
        status: entity.status,
        children: deptNodes,
        rawData: entity,
        childCount: deptNodes.length,
      }
    })
    .sort((a, b) => a.code.localeCompare(b.code))
})

// ── Search & Tree Filter ──
const searchText = ref('')
const treeRef = ref<any>()

function filterNode(value: string, data: TreeNode): boolean {
  if (!value) return true
  const v = value.toLowerCase()
  return data.label.toLowerCase().includes(v) || data.code.toLowerCase().includes(v)
}

watch(searchText, (val) => {
  treeRef.value?.filter(val)
})

// ── Node Selection ──
const selectedNodeId = ref<string | null>(null)

function findNode(nodes: TreeNode[], id: string): TreeNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children.length) {
      const found = findNode(n.children, id)
      if (found) return found
    }
  }
  return null
}

const selectedNode = computed<TreeNode | null>(() => {
  if (!selectedNodeId.value) return null
  return findNode(treeData.value, selectedNodeId.value)
})

const selectedNodeType = computed(() => selectedNode.value?.type ?? null)

// Typed accessors for template (TS can't narrow union in template v-if)
const entityDetail = computed(() => selectedNode.value?.type === 'entity' ? (selectedNode.value.rawData as EntityRec) : null)
const deptDetail = computed(() => selectedNode.value?.type === 'department' ? (selectedNode.value.rawData as DepartmentRec) : null)
const teamDetail = computed(() => selectedNode.value?.type === 'team' ? (selectedNode.value.rawData as TeamRec) : null)

// ── Computed Children ──
const childrenOfSelectedEntity = computed(() => {
  if (!selectedNode.value || selectedNode.value.type !== 'entity') return []
  return departments.value.filter(d => d.entity_id === (selectedNode.value!.rawData as EntityRec).entity_id)
})

const childrenOfSelectedDepartment = computed(() => {
  if (!selectedNode.value || selectedNode.value.type !== 'department') return []
  return teams.value.filter(t => t.department_id === (selectedNode.value!.rawData as DepartmentRec).department_id)
})

function parentDeptForTeam(t: TeamRec): DepartmentRec | undefined {
  return departments.value.find(d => d.department_id === t.department_id)
}

function entityForDept(dept: DepartmentRec): EntityRec | undefined {
  return entities.value.find(e => e.entity_id === dept.entity_id)
}

function entityForTeam(t: TeamRec): EntityRec | undefined {
  const dept = parentDeptForTeam(t)
  return dept ? entityForDept(dept) : undefined
}

// ── Data Loading ──
async function loadAllData() {
  loading.value = true
  try {
    const [er, dr, tr] = await Promise.all([
      masterdataApi.entities(),
      masterdataApi.departments(),
      masterdataApi.teams(),
    ])
    entities.value = er.data?.entities || []
    departments.value = dr.data?.departments || []
    teams.value = tr.data?.teams || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.message || 'Failed to load')
    entities.value = []
    departments.value = []
    teams.value = []
  } finally {
    loading.value = false
  }
}

// ── Navigation ──
function getParentIds(nodes: TreeNode[], targetId: string, path: string[] = []): string[] {
  for (const n of nodes) {
    if (n.id === targetId) return path
    if (n.children.length) {
      const found = getParentIds(n.children, targetId, [...path, n.id])
      if (found.length > 0 || n.children.some(c => c.id === targetId)) {
        return found.length > 0 ? found : [...path, n.id]
      }
    }
  }
  return []
}

async function navigateToEntity(entityId: string) {
  selectedNodeId.value = `entity-${entityId}`
  await nextTick()
  if (treeRef.value) {
    const parentIds = getParentIds(treeData.value, selectedNodeId.value!)
    for (const pid of parentIds) {
      treeRef.value.store?.nodesMap?.[pid]?.expand()
    }
    treeRef.value.setCurrentKey(selectedNodeId.value)
  }
}

async function navigateToDepartment(deptId: string) {
  selectedNodeId.value = `dept-${deptId}`
  await nextTick()
  if (treeRef.value) {
    const parentIds = getParentIds(treeData.value, selectedNodeId.value!)
    for (const pid of parentIds) {
      treeRef.value.store?.nodesMap?.[pid]?.expand()
    }
    treeRef.value.setCurrentKey(selectedNodeId.value)
  }
}

// ── Persist Selection ──
async function refreshAndKeepSelection() {
  const saved = selectedNodeId.value
  await loadAllData()
  if (saved) {
    await nextTick()
    selectedNodeId.value = saved
    await nextTick()
    if (treeRef.value) {
      treeRef.value.setCurrentKey(saved)
    }
  }
}

function handleNodeClick(node: TreeNode) {
  selectedNodeId.value = node.id
}

// ── Status Helpers ──
function statusTagType(status: string) {
  return status === 'active' ? 'success' : status === 'inactive' ? 'info' : 'danger'
}

// ══════════════════════════════════════════════
// ENTITY CRUD
// ══════════════════════════════════════════════
const entityDialogVisible = ref(false)
const entityDialogMode = ref<'create' | 'edit'>('create')
const entityEditingId = ref<string | null>(null)
const entitySubmitting = ref(false)
const entityFormErrors = ref<string[]>([])
const entityForm = ref({
  entity_code: '', legal_name: '', entity_name_en: '', entity_name_ja: '', entity_name_zh: '',
  registration_number: '', tax_registration_number: '',
  country: '', currency: '', status: 'active',
  change_reason: '', masterdata_change_ack: false,
})

function openEntityCreate() {
  entityDialogMode.value = 'create'
  entityEditingId.value = null
  entityForm.value = {
    entity_code: '', legal_name: '', entity_name_en: '', entity_name_ja: '', entity_name_zh: '',
    registration_number: '', tax_registration_number: '',
    country: '', currency: '', status: 'active',
    change_reason: '', masterdata_change_ack: false,
  }
  entityFormErrors.value = []
  entityDialogVisible.value = true
}

function openEntityEdit() {
  const node = selectedNode.value
  if (!node || node.type !== 'entity') return
  const e = node.rawData as EntityRec
  entityDialogMode.value = 'edit'
  entityEditingId.value = e.entity_id
  entityForm.value = {
    entity_code: e.entity_code || '', legal_name: e.legal_name || '',
    entity_name_en: e.entity_name_en || '', entity_name_ja: e.entity_name_ja || '', entity_name_zh: e.entity_name_zh || '',
    registration_number: e.registration_number || '', tax_registration_number: e.tax_registration_number || '',
    country: e.country || '', currency: e.currency || '', status: e.status || 'active',
    change_reason: '', masterdata_change_ack: false,
  }
  entityFormErrors.value = []
  entityDialogVisible.value = true
}

async function handleEntitySubmit() {
  entityFormErrors.value = []
  if (!entityForm.value.masterdata_change_ack) {
    entityFormErrors.value.push(t('validation.change_ack_required'))
    return
  }
  entitySubmitting.value = true
  try {
    const payload: Record<string, unknown> = { ...entityForm.value }
    if (entityDialogMode.value === 'create') {
      await masterdataApi.createEntity(payload)
      ElMessage.success(t('entity.saved_message'))
    } else {
      await masterdataApi.updateEntity(entityEditingId.value!, payload)
      ElMessage.success(t('entity.updated_message'))
    }
    entityDialogVisible.value = false
    await refreshAndKeepSelection()
  } catch (e: any) {
    const errData = e?.response?.data
    entityFormErrors.value = errData?.errors
      ? (Array.isArray(errData.errors) ? errData.errors : [errData.error || 'Unknown error'])
      : [errData?.error || e?.message || 'Failed to save']
  } finally {
    entitySubmitting.value = false
  }
}

async function handleEntityDeactivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'entity') return
  const e = node.rawData as EntityRec
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate', { record: e.entity_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteEntity(e.entity_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('entity.deactivated'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to deactivate')
    }
  }
}

async function handleEntityActivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'entity') return
  const e = node.rawData as EntityRec
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: e.entity_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    const payload: Record<string, unknown> = {
      entity_code: e.entity_code, legal_name: e.legal_name || '',
      entity_name_en: e.entity_name_en || '', entity_name_ja: e.entity_name_ja || '', entity_name_zh: e.entity_name_zh || '',
      registration_number: e.registration_number || '', tax_registration_number: e.tax_registration_number || '',
      country: e.country || '', currency: e.currency || '', status: 'active',
      change_reason: 'Reactivated from portal',
    }
    await masterdataApi.updateEntity(e.entity_id, payload)
    ElMessage.success(t('entity.updated_message'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to reactivate')
    }
  }
}

// ══════════════════════════════════════════════
// DEPARTMENT CRUD
// ══════════════════════════════════════════════
const deptDialogVisible = ref(false)
const deptDialogMode = ref<'create' | 'edit'>('create')
const deptEditingId = ref<string | null>(null)
const deptSubmitting = ref(false)
const deptFormErrors = ref<string[]>([])
const deptForm = ref({
  department_code: '', department_name_en: '', department_name_ja: '', department_name_zh: '',
  entity_id: '', status: 'active',
  change_reason: '', masterdata_change_ack: false,
})

function openDeptCreate(parentEntityId?: string) {
  deptDialogMode.value = 'create'
  deptEditingId.value = null
  const eid = parentEntityId || (selectedNode.value?.type === 'entity' ? (selectedNode.value.rawData as EntityRec).entity_id : '')
  deptForm.value = {
    department_code: '', department_name_en: '', department_name_ja: '', department_name_zh: '',
    entity_id: eid,
    status: 'active', change_reason: '', masterdata_change_ack: false,
  }
  deptFormErrors.value = []
  deptDialogVisible.value = true
}

function openDeptEdit() {
  const node = selectedNode.value
  if (!node || node.type !== 'department') return
  const d = node.rawData as DepartmentRec
  deptDialogMode.value = 'edit'
  deptEditingId.value = d.department_id
  deptForm.value = {
    department_code: d.department_code || '', department_name_en: d.department_name_en || '',
    department_name_ja: d.department_name_ja || '', department_name_zh: d.department_name_zh || '',
    entity_id: d.entity_id || '', status: d.status || 'active',
    change_reason: '', masterdata_change_ack: false,
  }
  deptFormErrors.value = []
  deptDialogVisible.value = true
}

async function handleDeptSubmit() {
  deptFormErrors.value = []
  if (!deptForm.value.masterdata_change_ack) {
    deptFormErrors.value.push(t('validation.change_ack_required'))
    return
  }
  if (!deptForm.value.entity_id) {
    deptFormErrors.value.push(t('validation.parent_entity_required'))
    return
  }
  deptSubmitting.value = true
  try {
    const payload: Record<string, unknown> = { ...deptForm.value }
    if (deptDialogMode.value === 'create') {
      await masterdataApi.createDepartment(payload)
      ElMessage.success(t('department.saved_message'))
    } else {
      await masterdataApi.updateDepartment(deptEditingId.value!, payload)
      ElMessage.success(t('department.updated_message'))
    }
    deptDialogVisible.value = false
    await refreshAndKeepSelection()
  } catch (e: any) {
    const errData = e?.response?.data
    deptFormErrors.value = errData?.errors
      ? (Array.isArray(errData.errors) ? errData.errors : [errData.error || 'Unknown error'])
      : [errData?.error || e?.message || 'Failed to save']
  } finally {
    deptSubmitting.value = false
  }
}

async function handleDeptDeactivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'department') return
  const d = node.rawData as DepartmentRec
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate_department', { record: d.department_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteDepartment(d.department_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('department.deactivated'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to deactivate')
    }
  }
}

async function handleDeptActivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'department') return
  const d = node.rawData as DepartmentRec
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: d.department_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    const payload: Record<string, unknown> = {
      department_code: d.department_code,
      department_name_en: d.department_name_en || '',
      department_name_ja: d.department_name_ja || '',
      department_name_zh: d.department_name_zh || '',
      entity_id: d.entity_id, status: 'active',
      change_reason: 'Reactivated from portal',
    }
    await masterdataApi.updateDepartment(d.department_id, payload)
    ElMessage.success(t('department.updated_message'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to reactivate')
    }
  }
}

// ══════════════════════════════════════════════
// TEAM CRUD
// ══════════════════════════════════════════════
const teamDialogVisible = ref(false)
const teamDialogMode = ref<'create' | 'edit'>('create')
const teamEditingId = ref<string | null>(null)
const teamSubmitting = ref(false)
const teamFormErrors = ref<string[]>([])
const teamForm = ref({
  team_code: '', team_name_en: '', team_name_ja: '', team_name_zh: '',
  entity_id: '', department_id: '', status: 'active',
  change_reason: '', masterdata_change_ack: false,
})

const teamFormDeptOptions = computed(() => {
  if (!teamForm.value.entity_id) return departments.value
  return departments.value.filter(d => d.entity_id === teamForm.value.entity_id)
})

watch(() => teamForm.value.entity_id, () => {
  teamForm.value.department_id = ''
})

function openTeamCreate(parentEntityId?: string, parentDeptId?: string) {
  teamDialogMode.value = 'create'
  teamEditingId.value = null
  const eid = parentEntityId || (selectedNode.value?.type === 'department'
    ? (selectedNode.value.rawData as DepartmentRec).entity_id
    : '')
  const did = parentDeptId || (selectedNode.value?.type === 'department'
    ? (selectedNode.value.rawData as DepartmentRec).department_id
    : '')
  teamForm.value = {
    team_code: '', team_name_en: '', team_name_ja: '', team_name_zh: '',
    entity_id: eid, department_id: did,
    status: 'active', change_reason: '', masterdata_change_ack: false,
  }
  teamFormErrors.value = []
  teamDialogVisible.value = true
}

function openTeamEdit() {
  const node = selectedNode.value
  if (!node || node.type !== 'team') return
  const tm = node.rawData as TeamRec
  const dept = parentDeptForTeam(tm)
  teamDialogMode.value = 'edit'
  teamEditingId.value = tm.team_id
  teamForm.value = {
    team_code: tm.team_code || '', team_name_en: tm.team_name_en || '',
    team_name_ja: tm.team_name_ja || '', team_name_zh: tm.team_name_zh || '',
    entity_id: dept?.entity_id || '', department_id: tm.department_id || '',
    status: tm.status || 'active',
    change_reason: '', masterdata_change_ack: false,
  }
  teamFormErrors.value = []
  teamDialogVisible.value = true
}

async function handleTeamSubmit() {
  teamFormErrors.value = []
  if (!teamForm.value.masterdata_change_ack) {
    teamFormErrors.value.push(t('validation.change_ack_required'))
    return
  }
  if (!teamForm.value.department_id) {
    teamFormErrors.value.push(t('validation.parent_department_required'))
    return
  }
  teamSubmitting.value = true
  try {
    const payload: Record<string, unknown> = { ...teamForm.value }
    if (teamDialogMode.value === 'create') {
      await masterdataApi.createTeam(payload)
      ElMessage.success(t('team.saved_message'))
    } else {
      await masterdataApi.updateTeam(teamEditingId.value!, payload)
      ElMessage.success(t('team.updated_message'))
    }
    teamDialogVisible.value = false
    await refreshAndKeepSelection()
  } catch (e: any) {
    const errData = e?.response?.data
    teamFormErrors.value = errData?.errors
      ? (Array.isArray(errData.errors) ? errData.errors : [errData.error || 'Unknown error'])
      : [errData?.error || e?.message || 'Failed to save']
  } finally {
    teamSubmitting.value = false
  }
}

async function handleTeamDeactivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'team') return
  const tm = node.rawData as TeamRec
  try {
    await ElMessageBox.confirm(
      t('action.confirm_deactivate_team', { record: tm.team_code }),
      t('action.deactivate_confirm'),
      { confirmButtonText: t('action.deactivate'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await masterdataApi.deleteTeam(tm.team_id, { change_reason: 'Deactivated from portal' })
    ElMessage.success(t('team.deactivated'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to deactivate')
    }
  }
}

async function handleTeamActivate() {
  const node = selectedNode.value
  if (!node || node.type !== 'team') return
  const tm = node.rawData as TeamRec
  const dept = parentDeptForTeam(tm)
  try {
    await ElMessageBox.confirm(
      t('action.confirm_activate', { record: tm.team_code }),
      t('action.activate'),
      { confirmButtonText: t('action.activate'), cancelButtonText: t('action.cancel'), type: 'info' }
    )
    const payload: Record<string, unknown> = {
      team_code: tm.team_code,
      team_name_en: tm.team_name_en || '',
      team_name_ja: tm.team_name_ja || '',
      team_name_zh: tm.team_name_zh || '',
      entity_id: dept?.entity_id || '',
      department_id: tm.department_id,
      status: 'active',
      change_reason: 'Reactivated from portal',
    }
    await masterdataApi.updateTeam(tm.team_id, payload)
    ElMessage.success(t('team.updated_message'))
    await refreshAndKeepSelection()
  } catch (err: any) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(err?.response?.data?.error || err?.message || 'Failed to reactivate')
    }
  }
}

// ══════════════════════════════════════════════
// LIFECYCLE
// ══════════════════════════════════════════════
onMounted(() => {
  loadAllData()
})
</script>

<template>
  <div class="fiori-page">
    <!-- ═══ Toolbar ═══ -->
    <div class="fiori-toolbar">
      <div class="fiori-toolbar-left">
        <h2 class="fiori-page-title">{{ t('module.masterdata') }}</h2>
      </div>
      <div class="fiori-toolbar-right">
        <el-button type="primary" :icon="Plus" size="default" @click="openEntityCreate">
          {{ t('action.create_entity') }}
        </el-button>
      </div>
    </div>

    <!-- ═══ Main Split Layout ═══ -->
    <div class="masterdata-layout">
      <!-- ── Left Sidebar: Organization Tree ── -->
      <div class="masterdata-sidebar">
        <div class="sidebar-header">
          <el-input
            v-model="searchText"
            :placeholder="t('action.search')"
            :prefix-icon="Search"
            clearable
            size="default"
          />
        </div>
        <div class="sidebar-tree" v-loading="loading">
          <el-tree
            v-if="treeData.length > 0"
            ref="treeRef"
            :data="treeData"
            :props="{ children: 'children', label: 'label' }"
            node-key="id"
            :highlight-current="true"
            :expand-on-click-node="true"
            :default-expand-all="false"
            :filter-node-method="filterNode"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <span class="org-tree-node">
                <el-icon v-if="data.type === 'entity'" class="node-icon entity-icon" :size="14">
                  <OfficeBuilding />
                </el-icon>
                <el-icon v-else-if="data.type === 'department'" class="node-icon dept-icon" :size="14">
                  <Folder />
                </el-icon>
                <el-icon v-else class="node-icon team-icon" :size="14">
                  <UserFilled />
                </el-icon>
                <span class="node-label">{{ data.label }}</span>
                <span class="node-meta">
                  <span v-if="data.childCount > 0" class="node-count">({{ data.childCount }})</span>
                  <span v-if="data.status !== 'active'" class="node-inactive-tag">
                    {{ t('entity.status.inactive', data.status) }}
                  </span>
                </span>
              </span>
            </template>
          </el-tree>
          <div v-else class="empty-state">
            <div class="empty-state-inner">
              <el-icon :size="36" style="color:#c0c4cc"><OfficeBuilding /></el-icon>
              <p>{{ t('organization.no_structure') }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Right Main Panel: Detail View ── -->
      <div class="masterdata-main">
        <!-- ═══ Entity Detail ═══ -->
        <template v-if="selectedNodeType === 'entity' && entityDetail">
          <div class="node-detail-card">
            <div class="detail-header">
              <div class="detail-header-left">
                <el-icon :size="20" class="detail-type-icon entity-icon"><OfficeBuilding /></el-icon>
                <h3>{{ t('entity.detail_title') }}</h3>
                <el-tag :type="statusTagType(selectedNode!.status)" size="small">
                  {{ t(`entity.status.${selectedNode!.status}`, selectedNode!.status) }}
                </el-tag>
              </div>
              <div class="detail-header-right">
                <el-button size="small" @click="openEntityEdit">{{ t('action.edit') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'active'"
                  size="small"
                  type="danger"
                  @click="handleEntityDeactivate"
                >{{ t('action.deactivate') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'inactive'"
                  size="small"
                  type="success"
                  @click="handleEntityActivate"
                >{{ t('action.activate') }}</el-button>
              </div>
            </div>
            <div class="detail-body">
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.entity_code') }}</label>
                    <span>{{ entityDetail.entity_code }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.entity_name_en') }}</label>
                    <span>{{ entityDetail.entity_name_en }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.entity_name_ja') }}</label>
                    <span>{{ entityDetail.entity_name_ja || '—' }}</span>
                  </div>
                </el-col>
              </el-row>
              <el-row :gutter="20" style="margin-top:12px">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.entity_name_zh') }}</label>
                    <span>{{ entityDetail.entity_name_zh || '—' }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.legal_name') }}</label>
                    <span>{{ entityDetail.legal_name || '—' }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.country') }}</label>
                    <span>{{ entityDetail.country || '—' }}</span>
                  </div>
                </el-col>
              </el-row>
              <el-row :gutter="20" style="margin-top:12px">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('entity.currency') }}</label>
                    <span>{{ entityDetail.currency || '—' }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('common.updated_at') }}</label>
                    <span>{{ formatDateTime(entityDetail.updated_at) }}</span>
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>

          <!-- Children: Departments -->
          <div class="children-section">
            <div class="children-section-header">
              <span class="children-title">
                {{ t('department.title') }}
                <span class="children-count">{{ childrenOfSelectedEntity.length }}</span>
              </span>
              <el-button type="primary" size="small" :icon="Plus" @click="openDeptCreate(entityDetail.entity_id)">
                {{ t('action.create_department') }}
              </el-button>
            </div>
            <el-table
              v-if="childrenOfSelectedEntity.length > 0"
              :data="childrenOfSelectedEntity"
              stripe
              border
              style="width:100%"
              empty-text="—"
            >
              <el-table-column prop="department_code" :label="t('department.department_code')" min-width="130" />
              <el-table-column prop="department_name_en" :label="t('department.department_name_en')" min-width="140" />
              <el-table-column prop="department_name_ja" :label="t('department.department_name_ja')" min-width="140" />
              <el-table-column prop="department_name_zh" :label="t('department.department_name_zh')" min-width="140" />
              <el-table-column :label="t('common.status')" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">
                    {{ t(`entity.status.${row.status}`, row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('action.actions')" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button text type="primary" size="small" @click="navigateToDepartment(row.department_id)">
                    {{ t('action.view') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <div v-else class="empty-children">
              <p>{{ t('organization.no_departments') }}</p>
            </div>
          </div>
        </template>

        <!-- ═══ Department Detail ═══ -->
        <template v-else-if="selectedNodeType === 'department' && deptDetail">
          <div class="node-detail-card">
            <div class="detail-header">
              <div class="detail-header-left">
                <el-icon :size="20" class="detail-type-icon dept-icon"><Folder /></el-icon>
                <h3>{{ t('department.detail_title') }}</h3>
                <el-tag :type="statusTagType(selectedNode!.status)" size="small">
                  {{ t(`entity.status.${selectedNode!.status}`, selectedNode!.status) }}
                </el-tag>
              </div>
              <div class="detail-header-right">
                <el-button size="small" @click="openDeptEdit">{{ t('action.edit') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'active'"
                  size="small"
                  type="danger"
                  @click="handleDeptDeactivate"
                >{{ t('action.deactivate') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'inactive'"
                  size="small"
                  type="success"
                  @click="handleDeptActivate"
                >{{ t('action.activate') }}</el-button>
              </div>
            </div>
            <div class="detail-body">
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('department.department_code') }}</label>
                    <span>{{ deptDetail.department_code }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('department.department_name_en') }}</label>
                    <span>{{ deptDetail.department_name_en }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('department.department_name_ja') }}</label>
                    <span>{{ deptDetail.department_name_ja || '—' }}</span>
                  </div>
                </el-col>
              </el-row>
              <el-row :gutter="20" style="margin-top:12px">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('department.department_name_zh') }}</label>
                    <span>{{ deptDetail.department_name_zh || '—' }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('department.parent_entity') }}</label>
                    <span>
                      <a
                        v-if="entityForDept(deptDetail)"
                        class="nav-link"
                        @click="navigateToEntity(deptDetail.entity_id)"
                      >
                        {{ entityLabel(entityForDept(deptDetail)!) }}
                      </a>
                      <span v-else>—</span>
                    </span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('common.updated_at') }}</label>
                    <span>{{ formatDateTime(deptDetail.updated_at) }}</span>
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>

          <!-- Children: Teams -->
          <div class="children-section">
            <div class="children-section-header">
              <span class="children-title">
                {{ t('team.title') }}
                <span class="children-count">{{ childrenOfSelectedDepartment.length }}</span>
              </span>
              <el-button
                type="primary"
                size="small"
                :icon="Plus"
                @click="openTeamCreate(deptDetail.entity_id, deptDetail.department_id)"
              >
                {{ t('action.create_team') }}
              </el-button>
            </div>
            <el-table
              v-if="childrenOfSelectedDepartment.length > 0"
              :data="childrenOfSelectedDepartment"
              stripe
              border
              style="width:100%"
              empty-text="—"
            >
              <el-table-column prop="team_code" :label="t('team.team_code')" min-width="130" />
              <el-table-column prop="team_name_en" :label="t('team.team_name_en')" min-width="140" />
              <el-table-column prop="team_name_ja" :label="t('team.team_name_ja')" min-width="140" />
              <el-table-column prop="team_name_zh" :label="t('team.team_name_zh')" min-width="140" />
              <el-table-column :label="t('common.status')" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">
                    {{ t(`entity.status.${row.status}`, row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('action.actions')" width="80" fixed="right">
                <template #default="{ row }">
                  <el-button text type="primary" size="small" @click="navigateToDepartment(row.department_id); selectedNodeId = 'team-' + row.team_id">
                    {{ t('action.view') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <div v-else class="empty-children">
              <p>{{ t('organization.no_teams') }}</p>
            </div>
          </div>
        </template>

        <!-- ═══ Team Detail ═══ -->
        <template v-else-if="selectedNodeType === 'team' && teamDetail">
          <div class="node-detail-card">
            <div class="detail-header">
              <div class="detail-header-left">
                <el-icon :size="20" class="detail-type-icon team-icon"><UserFilled /></el-icon>
                <h3>{{ t('team.detail_title') }}</h3>
                <el-tag :type="statusTagType(selectedNode!.status)" size="small">
                  {{ t(`entity.status.${selectedNode!.status}`, selectedNode!.status) }}
                </el-tag>
              </div>
              <div class="detail-header-right">
                <el-button size="small" @click="openTeamEdit">{{ t('action.edit') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'active'"
                  size="small"
                  type="danger"
                  @click="handleTeamDeactivate"
                >{{ t('action.deactivate') }}</el-button>
                <el-button
                  v-if="selectedNode!.status === 'inactive'"
                  size="small"
                  type="success"
                  @click="handleTeamActivate"
                >{{ t('action.activate') }}</el-button>
              </div>
            </div>
            <div class="detail-body">
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.team_code') }}</label>
                    <span>{{ teamDetail.team_code }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.team_name_en') }}</label>
                    <span>{{ teamDetail.team_name_en }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.team_name_ja') }}</label>
                    <span>{{ teamDetail.team_name_ja || '—' }}</span>
                  </div>
                </el-col>
              </el-row>
              <el-row :gutter="20" style="margin-top:12px">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.team_name_zh') }}</label>
                    <span>{{ teamDetail.team_name_zh || '—' }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.parent_entity') }}</label>
                    <span>
                      <a
                        v-if="entityForTeam(teamDetail)"
                        class="nav-link"
                        @click="navigateToEntity(entityForTeam(teamDetail)!.entity_id)"
                      >
                        {{ entityLabel(entityForTeam(teamDetail)!) }}
                      </a>
                      <span v-else>—</span>
                    </span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('team.parent_department') }}</label>
                    <span>
                      <a
                        v-if="parentDeptForTeam(teamDetail)"
                        class="nav-link"
                        @click="navigateToDepartment(teamDetail.department_id)"
                      >
                        {{ parentDeptForTeam(teamDetail)!.department_code }}
                        -
                        {{ getDisplayName(parentDeptForTeam(teamDetail)!, 'department') }}
                      </a>
                      <span v-else>—</span>
                    </span>
                  </div>
                </el-col>
              </el-row>
              <el-row :gutter="20" style="margin-top:12px">
                <el-col :span="8">
                  <div class="detail-field">
                    <label>{{ t('common.updated_at') }}</label>
                    <span>{{ formatDateTime(teamDetail.updated_at) }}</span>
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>

          <!-- Team leaf node -->
          <div class="empty-children" style="margin-top:16px">
            <p>{{ t('team.no_records') }}</p>
          </div>
        </template>

        <!-- ═══ No Selection ═══ -->
        <div v-else class="empty-state">
          <div class="empty-state-inner">
            <el-icon :size="48" style="color:#c0c4cc"><OfficeBuilding /></el-icon>
            <p>{{ t('organization.no_structure') }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════ -->
    <!-- DIALOGS -->
    <!-- ═══════════════════════════════════════════ -->

    <!-- ── Entity Dialog ── -->
    <el-dialog
      v-model="entityDialogVisible"
      :title="entityDialogMode === 'create' ? t('entity.new_title') : t('entity.edit_title')"
      width="640px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleEntitySubmit">
        <el-form-item :label="t('entity.entity_code')" required>
          <el-input v-model="entityForm.entity_code" :disabled="entityDialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('entity.legal_name')">
          <el-input v-model="entityForm.legal_name" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_en')" required>
          <el-input v-model="entityForm.entity_name_en" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_ja')">
          <el-input v-model="entityForm.entity_name_ja" />
        </el-form-item>
        <el-form-item :label="t('entity.entity_name_zh')">
          <el-input v-model="entityForm.entity_name_zh" />
        </el-form-item>
        <el-form-item :label="t('entity.registration_number')">
          <el-input v-model="entityForm.registration_number" />
        </el-form-item>
        <el-form-item :label="t('entity.tax_registration_number')">
          <el-input v-model="entityForm.tax_registration_number" />
        </el-form-item>
        <el-form-item :label="t('entity.country')">
          <el-input v-model="entityForm.country" />
        </el-form-item>
        <el-form-item :label="t('entity.currency')">
          <el-input v-model="entityForm.currency" />
        </el-form-item>
        <el-form-item :label="t('common.status')">
          <el-select v-model="entityForm.status" style="width:100%">
            <el-option :label="t('entity.status.active')" value="active" />
            <el-option :label="t('entity.status.inactive')" value="inactive" />
          </el-select>
        </el-form-item>

        <el-divider />
        <el-form-item :label="t('governance.change_reason')" required>
          <el-input v-model="entityForm.change_reason" type="textarea" :rows="2" :placeholder="t('governance.change_reason')" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="entityForm.masterdata_change_ack">
            {{ t('governance.acknowledge') }}
          </el-checkbox>
        </el-form-item>

        <el-alert
          v-if="entityFormErrors.length > 0"
          :title="entityFormErrors.join(', ')"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom:12px"
        />
      </el-form>
      <template #footer>
        <el-button @click="entityDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="entitySubmitting" @click="handleEntitySubmit">
          {{ entityDialogMode === 'create' ? t('action.create') : t('action.save_update') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Department Dialog ── -->
    <el-dialog
      v-model="deptDialogVisible"
      :title="deptDialogMode === 'create' ? t('department.new_title') : t('department.edit_title')"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleDeptSubmit">
        <el-form-item :label="t('department.parent_entity')" required>
          <el-select v-model="deptForm.entity_id" :disabled="deptDialogMode === 'edit'" style="width:100%">
            <el-option
              v-for="e in entities"
              :key="e.entity_id"
              :label="entityLabel(e)"
              :value="e.entity_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('department.department_code')" required>
          <el-input v-model="deptForm.department_code" :disabled="deptDialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_en')" required>
          <el-input v-model="deptForm.department_name_en" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_ja')">
          <el-input v-model="deptForm.department_name_ja" />
        </el-form-item>
        <el-form-item :label="t('department.department_name_zh')">
          <el-input v-model="deptForm.department_name_zh" />
        </el-form-item>
        <el-form-item :label="t('common.status')">
          <el-select v-model="deptForm.status" style="width:100%">
            <el-option :label="t('entity.status.active')" value="active" />
            <el-option :label="t('entity.status.inactive')" value="inactive" />
          </el-select>
        </el-form-item>

        <el-divider />
        <el-form-item :label="t('governance.change_reason')" required>
          <el-input v-model="deptForm.change_reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="deptForm.masterdata_change_ack">
            {{ t('governance.acknowledge') }}
          </el-checkbox>
        </el-form-item>

        <el-alert
          v-if="deptFormErrors.length > 0"
          :title="deptFormErrors.join(', ')"
          type="error" show-icon :closable="false"
          style="margin-bottom:12px"
        />
      </el-form>
      <template #footer>
        <el-button @click="deptDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="deptSubmitting" @click="handleDeptSubmit">
          {{ deptDialogMode === 'create' ? t('action.create') : t('action.save_update') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Team Dialog ── -->
    <el-dialog
      v-model="teamDialogVisible"
      :title="teamDialogMode === 'create' ? t('team.new_title') : t('team.edit_title')"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form label-width="160px" @submit.prevent="handleTeamSubmit">
        <el-form-item :label="t('team.parent_entity')" required>
          <el-select v-model="teamForm.entity_id" :disabled="teamDialogMode === 'edit'" style="width:100%" @change="teamForm.department_id = ''">
            <el-option
              v-for="e in entities"
              :key="e.entity_id"
              :label="entityLabel(e)"
              :value="e.entity_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('team.parent_department')" required>
          <el-select v-model="teamForm.department_id" :disabled="teamDialogMode === 'edit'" style="width:100%">
            <el-option
              v-for="d in teamFormDeptOptions"
              :key="d.department_id"
              :label="`${d.department_code} - ${getDisplayName(d, 'department')}`"
              :value="d.department_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('team.team_code')" required>
          <el-input v-model="teamForm.team_code" :disabled="teamDialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_en')" required>
          <el-input v-model="teamForm.team_name_en" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_ja')">
          <el-input v-model="teamForm.team_name_ja" />
        </el-form-item>
        <el-form-item :label="t('team.team_name_zh')">
          <el-input v-model="teamForm.team_name_zh" />
        </el-form-item>
        <el-form-item :label="t('common.status')">
          <el-select v-model="teamForm.status" style="width:100%">
            <el-option :label="t('entity.status.active')" value="active" />
            <el-option :label="t('entity.status.inactive')" value="inactive" />
          </el-select>
        </el-form-item>

        <el-divider />
        <el-form-item :label="t('governance.change_reason')" required>
          <el-input v-model="teamForm.change_reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="teamForm.masterdata_change_ack">
            {{ t('governance.acknowledge') }}
          </el-checkbox>
        </el-form-item>

        <el-alert
          v-if="teamFormErrors.length > 0"
          :title="teamFormErrors.join(', ')"
          type="error" show-icon :closable="false"
          style="margin-bottom:12px"
        />
      </el-form>
      <template #footer>
        <el-button @click="teamDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="teamSubmitting" @click="handleTeamSubmit">
          {{ teamDialogMode === 'create' ? t('action.create') : t('action.save_update') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ── Page Layout ── */
.fiori-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.fiori-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.fiori-toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fiori-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fiori-page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin: 0;
}

/* ── Split Layout ── */
.masterdata-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.masterdata-sidebar {
  width: 340px;
  min-width: 280px;
  flex-shrink: 0;
}

.masterdata-main {
  flex: 1;
  min-width: 0;
}

/* ── Sidebar ── */
.sidebar-header {
  margin-bottom: 12px;
}

.sidebar-tree {
  min-height: 200px;
  background: #fff;
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ── Tree Node ── */
.org-tree-node {
  display: flex;
  flex: 1;
  align-items: center;
  max-width: 90%;
  gap: 6px;
  font-size: 0.875rem;
}

.node-icon {
  flex-shrink: 0;
}

.entity-icon { color: var(--el-color-primary); }
.dept-icon { color: var(--el-color-success); }
.team-icon { color: var(--el-color-warning); }

.node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.node-count {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

.node-inactive-tag {
  font-size: 0.7rem;
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  padding: 0 4px;
  border-radius: 3px;
}

/* ── Tree row height (match default search input) ── */
:deep(.el-tree-node__content) {
  height: 32px;
  line-height: 32px;
}

/* ── Empty State ── */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.empty-state-inner {
  text-align: center;
  color: var(--el-text-color-secondary);
}

.empty-state-inner p {
  margin-top: 12px;
  font-size: 0.95rem;
}

/* ── Detail Card ── */
.node-detail-card {
  background: #fff;
  border-radius: 8px;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #f5f7fa;
  border-left: 4px solid var(--el-color-primary);
}

.detail-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header-left h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.detail-type-icon {
  flex-shrink: 0;
}

.detail-header-right {
  display: flex;
  gap: 8px;
}

.detail-body {
  padding: 16px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-field label {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.detail-field span {
  font-size: 0.9rem;
  color: var(--el-text-color-primary);
}

.nav-link {
  color: var(--el-color-primary);
  cursor: pointer;
  text-decoration: none;
}

.nav-link:hover {
  text-decoration: underline;
}

/* ── Children Section ── */
.children-section {
  margin-top: 16px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.children-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.children-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.children-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  background: var(--el-color-primary);
  border-radius: 11px;
}

.empty-children {
  padding: 24px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.empty-children p {
  margin: 0;
  font-size: 0.9rem;
}
</style>
