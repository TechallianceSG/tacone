import { ref, computed, type ComputedRef } from 'vue'
import { payrollSgApi } from '@/api/client'

// ── Types ──
export interface SgConstants {
  item_categories: string[]
  item_category_labels: Record<string, string>
  item_subcategories: string[]
  item_subcategory_labels: Record<string, string>
  salary_types: { value: string; label: string }[]
  cpf_age_ranges: { value: string; label: string }[]
}

// ── Module-level cache ──
let _cache: SgConstants | null = null
let _loading = false
let _pendingPromise: Promise<SgConstants> | null = null

async function _ensureLoaded(): Promise<SgConstants> {
  if (_cache) return _cache
  if (_loading && _pendingPromise) return _pendingPromise

  _loading = true
  _pendingPromise = (async () => {
    try {
      const { data } = await payrollSgApi.constants()
      _cache = data.data ?? data
      return _cache!
    } catch {
      // Fallback to hardcoded defaults
      _cache = {
        item_categories: ['earning', 'deduction', 'employer_cost'],
        item_category_labels: {
          earning: 'Earning / 収入',
          deduction: 'Deduction / 控除',
          employer_cost: 'Employer Cost / 雇主コスト',
        },
        item_subcategories: ['base', 'allowance', 'overtime', 'statutory', 'manual'],
        item_subcategory_labels: {
          base: 'Base / 基本', allowance: 'Allowance / 手当',
          overtime: 'Overtime / 残業', statutory: 'Statutory / 法定',
          manual: 'Manual / 手動',
        },
        salary_types: [
          { value: 'daily', label: 'Daily / 日給' },
          { value: 'monthly', label: 'Monthly / 月給' },
        ],
        cpf_age_ranges: [
          { value: '55_below', label: '55 and below' },
          { value: '55_60', label: 'Above 55 to 60' },
          { value: '60_65', label: 'Above 60 to 65' },
          { value: '65_above', label: 'Above 65' },
        ],
      }
      return _cache
    } finally {
      _loading = false
    }
  })()
  return _pendingPromise
}

// ── Reactive refs ──
const _itemCategories = ref<string[]>([])
const _itemCategoryLabels = ref<Record<string, string>>({})
const _itemSubcategories = ref<string[]>([])
const _itemSubcategoryLabels = ref<Record<string, string>>({})
const _salaryTypes = ref<{ value: string; label: string }[]>([])
const _cpfAgeRanges = ref<{ value: string; label: string }[]>([])
let _initialized = false

async function _init() {
  if (_initialized) return
  _initialized = true
  const c = await _ensureLoaded()
  _itemCategories.value = c.item_categories
  _itemCategoryLabels.value = c.item_category_labels
  _itemSubcategories.value = c.item_subcategories
  _itemSubcategoryLabels.value = c.item_subcategory_labels
  _salaryTypes.value = c.salary_types
  _cpfAgeRanges.value = c.cpf_age_ranges
}

/**
 * Composable for SG payroll reference/constants data.
 * Fetches once and caches at module level — safe to call in any component.
 *
 * Usage:
 *   const { salaryTypes, cpfAgeRanges, init } = usePayrollSgConstants()
 *   onMounted(() => init())
 */
export function usePayrollSgConstants() {
  const ready = computed(() => _itemCategories.value.length > 0)

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

  /** Subcategory options. */
  const itemSubcategoryOptions: ComputedRef<{ value: string; label: string }[]> = computed(() =>
    _itemSubcategories.value.map(s => ({
      value: s,
      label: _itemSubcategoryLabels.value[s] || s,
    }))
  )

  return {
    init,
    ready,
    itemCategories: _itemCategories,
    itemCategoryLabels: _itemCategoryLabels,
    itemSubcategories: _itemSubcategories,
    itemSubcategoryLabels: _itemSubcategoryLabels,
    itemCategoryOptions,
    itemSubcategoryOptions,
    salaryTypes: _salaryTypes,
    cpfAgeRanges: _cpfAgeRanges,
    invalidateCache() {
      _cache = null
      _pendingPromise = null
      _initialized = false
    },
  }
}
