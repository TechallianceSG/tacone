import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { payrollJpApi } from '@/api/client'

// ── Types ──
export interface RateTypeLabel {
  rate_type: string
  labels: Record<string, string>
  display_order?: number
  category?: string
}

export interface JpConstants {
  item_categories: string[]
  item_category_labels: Record<string, string>
  item_subcategory_labels: Record<string, string>
  salary_type_labels: Record<string, string>
  rate_type_labels: RateTypeLabel[]
  parameter_types: Record<string, string>
}

// ── Module-level cache ──
let _cache: JpConstants | null = null
let _loading = false
let _pendingPromise: Promise<JpConstants> | null = null

async function _ensureLoaded(): Promise<JpConstants> {
  if (_cache) return _cache
  if (_loading && _pendingPromise) return _pendingPromise

  _loading = true
  _pendingPromise = (async () => {
    try {
      const { data } = await payrollJpApi.constants()
      _cache = data.data ?? data
      return _cache!
    } catch {
      // Fallback to hardcoded defaults so UI still works
      _cache = {
        item_categories: ['earning', 'deduction', 'employer_cost'],
        item_category_labels: {
          earning: '支給 (Earning)',
          deduction: '控除 (Deduction)',
          employer_cost: '会社負担 (Employer Cost)',
        },
        item_subcategory_labels: {
          base: '基本', overtime: '残業', allowance: '手当',
          manual: '手動入力', statutory: '法定', attendance: '勤怠',
        },
        salary_type_labels: {
          monthly: '月給 / Monthly',
          hourly: '時給 / Hourly',
          daily: '日給 / Daily',
          monthly_fixed_ot: '月給＋固定残業 / Monthly + Fixed OT',
          monthly_hour: '月給時給ハイブリッド / Monthly-Hour Hybrid',
        },
        rate_type_labels: [],
        parameter_types: {
          SOCIAL_INSURANCE_RATE: 'social_insurance_rate',
          WITHHOLDING_TAX_BRACKET: 'withholding_tax_bracket',
          STANDARD_REMUNERATION_GRADE: 'standard_remuneration_grade',
          ACCIDENT_INSURANCE_RATE: 'accident_insurance_rate',
        },
      }
      return _cache
    } finally {
      _loading = false
    }
  })()
  return _pendingPromise
}

// ── Reactive refs built from cache ──
const _itemCategories = ref<string[]>([])
const _itemCategoryLabels = ref<Record<string, string>>({})
const _itemSubcategoryLabels = ref<Record<string, string>>({})
const _salaryTypeLabels = ref<Record<string, string>>({})
const _rateTypeLabels = ref<RateTypeLabel[]>([])
const _parameterTypes = ref<Record<string, string>>({})
let _initialized = false

async function _init() {
  if (_initialized) return
  _initialized = true
  const c = await _ensureLoaded()
  _itemCategories.value = c.item_categories
  _itemCategoryLabels.value = c.item_category_labels
  _itemSubcategoryLabels.value = c.item_subcategory_labels
  _salaryTypeLabels.value = c.salary_type_labels
  _rateTypeLabels.value = c.rate_type_labels
  _parameterTypes.value = c.parameter_types
}

/**
 * Composable for JP payroll reference/constants data.
 * Fetches once and caches at module level — safe to call in any component.
 *
 * Usage:
 *   const { itemCategories, itemCategoryLabels, salaryTypes, init } = usePayrollJpConstants()
 *   onMounted(() => init())
 */
export function usePayrollJpConstants() {
  const ready = computed(() => _itemCategories.value.length > 0)

  /** Trigger loading (idempotent — safe to call multiple times). */
  async function init(): Promise<void> {
    return _init()
  }

  /** Item categories as {value, label} pairs for dropdowns. */
  const itemCategoryOptions: ComputedRef<{ value: string; label: string }[]> = computed(() =>
    _itemCategories.value.map(c => ({
      value: c,
      label: _itemCategoryLabels.value[c] || c,
    }))
  )

  /** Subcategory options built from subcategory_labels. */
  const itemSubcategoryOptions: ComputedRef<{ value: string; label: string }[]> = computed(() =>
    Object.entries(_itemSubcategoryLabels.value).map(([k, v]) => ({
      value: k,
      label: v,
    }))
  )

  /** Salary types as {value, label} pairs for dropdowns. */
  const salaryTypes: ComputedRef<{ value: string; label: string }[]> = computed(() =>
    Object.entries(_salaryTypeLabels.value).map(([k, v]) => ({
      value: k,
      label: v,
    }))
  )

  /** Rate type labels — map rate_type → display label. */
  const rateTypeLabelMap: ComputedRef<Record<string, string>> = computed(() => {
    const m: Record<string, string> = {}
    for (const r of _rateTypeLabels.value) {
      const labels = r.labels || {}
      m[r.rate_type] = labels.ja || labels.en || r.rate_type
    }
    return m
  })

  /** Parameter types as {value, label} pairs. */
  const parameterTypeOptions: ComputedRef<{ value: string; label: string }[]> = computed(() =>
    Object.entries(_parameterTypes.value).map(([label, value]) => ({
      value,
      label,
    }))
  )

  return {
    init,
    ready,
    itemCategories: _itemCategories,
    itemCategoryLabels: _itemCategoryLabels,
    itemSubcategoryLabels: _itemSubcategoryLabels,
    itemCategoryOptions,
    itemSubcategoryOptions,
    salaryTypes,
    salaryTypeLabels: _salaryTypeLabels,
    rateTypeLabels: _rateTypeLabels,
    rateTypeLabelMap,
    parameterTypes: _parameterTypes,
    parameterTypeOptions,
    /** Invalidate cache (e.g., after data changes). */
    invalidateCache() {
      _cache = null
      _pendingPromise = null
      _initialized = false
    },
  }
}
