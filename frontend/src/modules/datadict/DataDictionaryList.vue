<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { datadictApi } from '@/api/client'
import { Search, RefreshLeft, Plus, Edit, Delete, FolderAdd } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const { t, locale } = useI18n()
const currentLang = computed(() => locale.value as string)

// ── Types ──
interface Category {
  id: number
  category_code: string
  labels: string
  description: string
  display_order: number
  is_active: boolean
  entry_count: number
}

interface DictEntry {
  id: number
  category_id: number
  entry_code: string
  labels: string
  display_order: number
  is_active: boolean
  updated_at: string
}

// ── Sidebar state ──
const sidebarLoading = ref(false)
const categories = ref<Category[]>([])
const selectedCategoryId = ref<number | null>(null)
const sidebarSearch = ref('')
const treeRef = ref<any>(null)

const selectedCategory = computed(() => {
  return categories.value.find(c => c.id === selectedCategoryId.value)
})

// ── Tree data (flat category list, sorted by display_order) ──
const categoryTreeData = computed(() => {
  return [...categories.value]
    .sort((a, b) => a.display_order - b.display_order)
})

// ── Tree filter ──
function filterNode(value: string, data: any): boolean {
  if (!value) return true
  const v = value.toLowerCase()
  const label = (data.labels || data.category_code || '').toLowerCase()
  return label.includes(v) || (data.category_code || '').toLowerCase().includes(v)
}

watch(sidebarSearch, (val) => {
  treeRef.value?.filter(val)
})

// ── Entry state ──
const entryLoading = ref(false)
const entries = ref<DictEntry[]>([])
const entryPage = ref(1)
const entryPageSize = ref(20)
const entryTotal = ref(0)

// ── Entry dialog ──
const entryDialogVisible = ref(false)
const entryDialogMode = ref<'create' | 'edit'>('create')
const editingEntryId = ref<number | null>(null)
const entrySubmitting = ref(false)
const entryFormRef = ref<FormInstance>()

const entryForm = reactive({
  entry_code: '',
  label: '',
  display_order: 0,
  is_active: true,
})

const entryFormRules: FormRules = {
  entry_code: [{ required: true, message: () => t('datadict.entry_code') + ' ' + t('action.required'), trigger: 'blur' }],
}

// ── Category dialog ──
const catDialogVisible = ref(false)
const catDialogMode = ref<'create' | 'edit'>('create')
const editingCatId = ref<number | null>(null)
const catSubmitting = ref(false)
const catFormRef = ref<FormInstance>()

const catForm = reactive({
  category_code: '',
  label: '',
  description: '',
  display_order: 0,
  is_active: true,
})

const catFormRules: FormRules = {
  category_code: [{ required: true, message: () => t('datadict.category_code') + ' ' + t('action.required'), trigger: 'blur' }],
}

// ═══════════════════════════════════════════════════════════
//  Data Loading
// ═══════════════════════════════════════════════════════════

async function loadCategories() {
  sidebarLoading.value = true
  try {
    const { data } = await datadictApi.categories.list()
    categories.value = data?.categories || []
  } catch { /* ignore */ }
  finally {
    sidebarLoading.value = false
  }
}

async function loadEntries() {
  if (!selectedCategoryId.value) {
    entries.value = []
    entryTotal.value = 0
    return
  }
  entryLoading.value = true
  try {
    const params: Record<string, any> = {
      category_id: selectedCategoryId.value,
      page: entryPage.value,
      page_size: entryPageSize.value,
      show_inactive: '1',
    }
    const { data } = await datadictApi.entries.list(params)
    entries.value = data?.items || []
    entryTotal.value = data?.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  } finally {
    entryLoading.value = false
  }
}

// ── Tree selection ──
function handleCategorySelect(data: any) {
  selectedCategoryId.value = data.id
  entryPage.value = 1
  loadEntries()
}

// ═══════════════════════════════════════════════════════════
//  Entry CRUD
// ═══════════════════════════════════════════════════════════

function openEntryCreate() {
  if (!selectedCategoryId.value) {
    ElMessage.warning(t('datadict.select_category'))
    return
  }
  entryDialogMode.value = 'create'
  editingEntryId.value = null
  entryForm.entry_code = ''
  entryForm.label = ''
  entryForm.display_order = 0
  entryForm.is_active = true
  entryDialogVisible.value = true
}

function openEntryEdit(row: DictEntry) {
  entryDialogMode.value = 'edit'
  editingEntryId.value = row.id
  entryForm.entry_code = row.entry_code
  entryForm.label = row.labels || ''
  entryForm.display_order = row.display_order
  entryForm.is_active = row.is_active
  entryDialogVisible.value = true
}

async function handleEntrySubmit() {
  if (!entryFormRef.value) return
  try { await entryFormRef.value.validate() } catch { return }
  entrySubmitting.value = true
  try {
    const label = entryForm.label.trim()
    const payload = {
      category_id: selectedCategoryId.value,
      entry_code: entryForm.entry_code.trim(),
      labels: { ja: label, zh: label, en: label },
      display_order: entryForm.display_order,
      is_active: entryForm.is_active,
    }
    if (entryDialogMode.value === 'create') {
      await datadictApi.entries.create(payload)
      ElMessage.success(t('datadict.saved'))
    } else {
      await datadictApi.entries.update(editingEntryId.value!, payload)
      ElMessage.success(t('datadict.updated'))
    }
    entryDialogVisible.value = false
    loadEntries()
    loadCategories() // refresh entry counts
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  } finally {
    entrySubmitting.value = false
  }
}

async function handleEntryDeactivate(row: DictEntry) {
  try {
    await ElMessageBox.confirm(
      t('datadict.confirm_deactivate', { code: row.entry_code }),
      t('action.confirm'),
      { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await datadictApi.entries.update(row.id, { is_active: false })
    ElMessage.success(t('datadict.deactivated'))
    loadEntries()
    loadCategories()
  } catch { /* cancelled */ }
}

async function handleEntryActivate(row: DictEntry) {
  try {
    await datadictApi.entries.update(row.id, { is_active: true })
    ElMessage.success(t('datadict.activated'))
    loadEntries()
    loadCategories()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  }
}

async function handleEntryDelete(row: DictEntry) {
  try {
    await ElMessageBox.confirm(
      t('datadict.confirm_delete_entry', { code: row.entry_code }),
      t('action.confirm'),
      { confirmButtonText: t('action.delete'), cancelButtonText: t('action.cancel'), type: 'error' }
    )
    await datadictApi.entries.delete(row.id)
    ElMessage.success(t('datadict.entry_deleted'))
    loadEntries()
    loadCategories()
  } catch { /* cancelled */ }
}

// ── Entry pagination ──
function handleEntryPageChange(p: number) { entryPage.value = p; loadEntries() }
function handleEntrySizeChange(s: number) { entryPageSize.value = s; entryPage.value = 1; loadEntries() }

// ═══════════════════════════════════════════════════════════
//  Category CRUD
// ═══════════════════════════════════════════════════════════

function openCategoryCreate() {
  catDialogMode.value = 'create'
  editingCatId.value = null
  catForm.category_code = ''
  catForm.label = ''
  catForm.description = ''
  catForm.display_order = 0
  catForm.is_active = true
  catDialogVisible.value = true
}

function openCategoryEdit(cat: Category) {
  catDialogMode.value = 'edit'
  editingCatId.value = cat.id
  catForm.category_code = cat.category_code
  catForm.label = cat.labels || ''
  catForm.description = cat.description || ''
  catForm.display_order = cat.display_order
  catForm.is_active = cat.is_active
  catDialogVisible.value = true
}

async function handleCategorySubmit() {
  if (!catFormRef.value) return
  try { await catFormRef.value.validate() } catch { return }
  catSubmitting.value = true
  try {
    const label = catForm.label.trim()
    const desc = catForm.description.trim()
    const payload = {
      category_code: catForm.category_code.trim(),
      labels: { ja: label, zh: label, en: label },
      description: { ja: desc, zh: desc, en: desc },
      display_order: catForm.display_order,
      is_active: catForm.is_active,
    }
    if (catDialogMode.value === 'create') {
      await datadictApi.categories.create(payload)
      ElMessage.success(t('datadict.category_saved'))
    } else {
      await datadictApi.categories.update(editingCatId.value!, payload)
      ElMessage.success(t('datadict.category_updated'))
    }
    catDialogVisible.value = false
    loadCategories()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  } finally {
    catSubmitting.value = false
  }
}

async function handleCategoryDeactivate(cat: Category) {
  try {
    await ElMessageBox.confirm(
      t('datadict.confirm_deactivate_category', { code: cat.category_code }),
      t('action.confirm'),
      { confirmButtonText: t('action.confirm'), cancelButtonText: t('action.cancel'), type: 'warning' }
    )
    await datadictApi.categories.update(cat.id, { is_active: false })
    ElMessage.success(t('datadict.category_deactivated'))
    if (selectedCategoryId.value === cat.id) {
      selectedCategoryId.value = null
    }
    loadCategories()
  } catch { /* cancelled */ }
}

async function handleCategoryActivate(cat: Category) {
  try {
    await datadictApi.categories.update(cat.id, { is_active: true })
    ElMessage.success(t('datadict.category_activated'))
    loadCategories()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  }
}

async function handleCategoryDelete(cat: Category) {
  try {
    await ElMessageBox.confirm(
      t('datadict.confirm_delete_category', { code: cat.category_code }),
      t('action.confirm'),
      { confirmButtonText: t('action.delete'), cancelButtonText: t('action.cancel'), type: 'error' }
    )
    await datadictApi.categories.delete(cat.id)
    ElMessage.success(t('datadict.category_deleted'))
    if (selectedCategoryId.value === cat.id) {
      selectedCategoryId.value = null
    }
    loadCategories()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || t('error.load_failed'))
  }
}

// ═══════════════════════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════════════════════

function getLabel(row: DictEntry): string {
  return row.labels || '-'
}

function catLabel(cat: Category): string {
  return cat.labels || cat.category_code
}

function catDesc(cat: Category): string {
  return cat.description || ''
}

// ═══════════════════════════════════════════════════════════
//  Lifecycle
// ═══════════════════════════════════════════════════════════

onMounted(async () => {
  await loadCategories()
})
</script>

<template>
  <div class="fiori-page">
    <!-- ═══ Page Header ═══ -->
    <div class="fiori-toolbar">
      <div class="fiori-toolbar-left">
        <h2 class="fiori-page-title">{{ t('datadict.title') }}</h2>
      </div>
      <div class="fiori-toolbar-right" style="display:flex;gap:8px">
        <el-button :icon="FolderAdd" @click="openCategoryCreate">
          {{ t('datadict.create_category') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openEntryCreate">
          {{ t('datadict.create') }}
        </el-button>
      </div>
    </div>

    <!-- ═══ Main Layout: Sidebar + Content ═══ -->
    <div class="datadict-layout">
      <!-- ═══ Left Sidebar ═══ -->
      <div class="datadict-sidebar fiori-card">
        <div class="sidebar-header">
          <el-input
            v-model="sidebarSearch"
            :placeholder="t('action.search')"
            :prefix-icon="Search"
            clearable
            size="small"
          />
        </div>
        <div class="sidebar-tree" v-loading="sidebarLoading">
          <el-tree
            ref="treeRef"
            :data="categoryTreeData"
            :props="{ children: 'children', label: 'id' }"
            node-key="id"
            :highlight-current="true"
            :expand-on-click-node="true"
            :default-expand-all="true"
            :filter-node-method="filterNode"
            @node-click="handleCategorySelect"
          >
            <template #default="{ data }">
              <span class="category-node">
                <span class="cat-label">{{ catLabel(data) }}</span>
                <span class="cat-meta">
                  <span class="cat-count">({{ data.entry_count || 0 }})</span>
                  <span v-if="!data.is_active" class="cat-inactive-tag">
                    {{ t('datadict.inactive') }}
                  </span>
                  <span class="cat-actions">
                    <el-button
                      v-if="data.is_active"
                      link
                      type="warning"
                      size="small"
                      @click.stop="handleCategoryDeactivate(data)"
                    >
                      {{ t('action.deactivate') }}
                    </el-button>
                    <el-button
                      v-else
                      link
                      type="success"
                      size="small"
                      @click.stop="handleCategoryActivate(data)"
                    >
                      {{ t('action.restore') }}
                    </el-button>
                    <el-button link type="primary" size="small" @click.stop="openCategoryEdit(data)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button link type="danger" size="small" @click.stop="handleCategoryDelete(data)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </span>
                </span>
              </span>
            </template>
          </el-tree>
        </div>
      </div>

      <!-- ═══ Right Main Panel ═══ -->
      <div class="datadict-main">
        <!-- Category selected: show description + entry table -->
        <template v-if="selectedCategory">
          <!-- Category description header -->
          <div class="category-header">
            <div class="category-header-top">
              <h3>{{ catLabel(selectedCategory) }}</h3>
              <el-tag size="small" type="info">{{ selectedCategory.labels || selectedCategory.category_code }}</el-tag>
              <el-tag v-if="!selectedCategory.is_active" size="small" type="danger">
                {{ t('datadict.inactive') }}
              </el-tag>
            </div>
            <p v-if="catDesc(selectedCategory)" class="category-desc">
              {{ catDesc(selectedCategory) }}
            </p>
          </div>

          <!-- Entry table -->
          <div class="fiori-card">
            <el-table
              :data="entries"
              v-loading="entryLoading"
              stripe
              border
              style="width:100%"
              empty-text="—"
            >
              <el-table-column prop="entry_code" :label="t('datadict.entry_code')" width="160" sortable />
              <el-table-column :label="t('datadict.label')" min-width="200">
                <template #default="{ row }">{{ getLabel(row) }}</template>
              </el-table-column>
              <el-table-column prop="display_order" :label="t('datadict.display_order')" width="80" align="center" />
              <el-table-column :label="t('datadict.is_active')" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                    {{ row.is_active ? t('datadict.active') : t('datadict.inactive') }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('action.actions')" width="220" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.is_active"
                    link
                    type="warning"
                    size="small"
                    @click="handleEntryDeactivate(row)"
                  >
                    {{ t('action.deactivate') }}
                  </el-button>
                  <el-button
                    v-else
                    link
                    type="success"
                    size="small"
                    @click="handleEntryActivate(row)"
                  >
                    {{ t('action.restore') }}
                  </el-button>
                  <el-button link type="primary" :icon="Edit" size="small" @click="openEntryEdit(row)">
                    {{ t('action.edit') }}
                  </el-button>
                  <el-button link type="danger" :icon="Delete" size="small" @click="handleEntryDelete(row)">
                    {{ t('action.delete') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- Pagination + record count -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
              <el-pagination
                v-model:current-page="entryPage"
                v-model:page-size="entryPageSize"
                :total="entryTotal"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next"
                @current-change="handleEntryPageChange"
                @size-change="handleEntrySizeChange"
              />
              <div class="helper-text">{{ entryTotal }} {{ t('action.records_total') }}</div>
            </div>
          </div>
        </template>

        <!-- No category selected: placeholder -->
        <div v-else class="empty-state">
          <div class="empty-state-inner">
            <el-icon :size="48" style="color:#c0c4cc"><FolderAdd /></el-icon>
            <p>{{ t('datadict.no_category_selected') }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Category Dialog ═══ -->
    <el-dialog
      v-model="catDialogVisible"
      :title="catDialogMode === 'create' ? t('datadict.create_category') : t('datadict.edit_category')"
      width="600px"
      :close-on-click-modal="false"
      @closed="catFormRef?.resetFields()"
    >
      <el-form
        ref="catFormRef"
        :model="catForm"
        :rules="catFormRules"
        label-position="top"
        @submit.prevent="handleCategorySubmit"
      >
        <el-form-item :label="t('datadict.category_code')" prop="category_code">
          <el-input
            v-model="catForm.category_code"
            :disabled="catDialogMode === 'edit'"
            maxlength="100"
            :placeholder="t('datadict.category_code')"
          />
        </el-form-item>
        <el-form-item :label="t('datadict.label')">
          <el-input v-model="catForm.label" maxlength="200" />
        </el-form-item>
        <el-form-item :label="t('datadict.description')">
          <el-input v-model="catForm.description" maxlength="500" type="textarea" :rows="2" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('datadict.display_order')">
              <el-input-number v-model="catForm.display_order" :min="0" :max="9999" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('datadict.is_active')">
              <el-switch v-model="catForm.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="catDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="catSubmitting" @click="handleCategorySubmit">
          {{ t('action.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ═══ Entry Dialog ═══ -->
    <el-dialog
      v-model="entryDialogVisible"
      :title="entryDialogMode === 'create' ? t('datadict.create') : t('datadict.edit')"
      width="540px"
      :close-on-click-modal="false"
      @closed="entryFormRef?.resetFields()"
    >
      <el-form
        ref="entryFormRef"
        :model="entryForm"
        :rules="entryFormRules"
        label-position="top"
        @submit.prevent="handleEntrySubmit"
      >
        <!-- Show the selected category name (read-only) -->
        <el-form-item :label="t('datadict.category')">
          <el-input
            :model-value="selectedCategory ? catLabel(selectedCategory) : ''"
            disabled
          />
        </el-form-item>
        <el-form-item :label="t('datadict.entry_code')" prop="entry_code">
          <el-input
            v-model="entryForm.entry_code"
            :disabled="entryDialogMode === 'edit'"
            maxlength="100"
            :placeholder="t('datadict.entry_code')"
          />
        </el-form-item>
        <el-form-item :label="t('datadict.label')">
          <el-input v-model="entryForm.label" maxlength="200" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('datadict.display_order')">
              <el-input-number v-model="entryForm.display_order" :min="0" :max="9999" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('datadict.is_active')">
              <el-switch v-model="entryForm.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="entryDialogVisible = false">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="entrySubmitting" @click="handleEntrySubmit">
          {{ t('action.save') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
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

.fiori-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.helper-text {
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}

/* ── Layout ── */
.datadict-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.datadict-sidebar {
  width: 300px;
  min-width: 260px;
  flex-shrink: 0;
}

.datadict-main {
  flex: 1;
  min-width: 0;
}

/* ── Sidebar ── */
.sidebar-header {
  margin-bottom: 12px;
}

.sidebar-tree {
  min-height: 200px;
}

.category-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 4px;
}

.cat-label {
  flex-shrink: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cat-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.cat-count {
  color: #999;
  font-size: 0.78rem;
}

.cat-inactive-tag {
  font-size: 0.7rem;
  color: #f56c6c;
  background: #fef0f0;
  padding: 0px 4px;
  border-radius: 3px;
}

.cat-actions {
  display: none;
}

.category-node:hover .cat-actions {
  display: inline-flex;
}

/* ── Tree customizations ── */
:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: var(--el-color-primary-light-9);
}

/* ── Category Header ── */
.category-header {
  margin-bottom: 16px;
  padding: 14px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  border-left: 4px solid var(--el-color-primary);
}

.category-header-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.category-header-top h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
}

.category-desc {
  color: #666;
  font-size: 0.9rem;
  margin-top: 6px;
  margin-bottom: 0;
  line-height: 1.5;
}

/* ── Empty State ── */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.empty-state-inner {
  text-align: center;
  color: #999;
}

.empty-state-inner p {
  margin-top: 12px;
  font-size: 1rem;
}
</style>
