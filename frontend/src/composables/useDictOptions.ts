import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { datadictApi } from '@/api/client'

interface DictOption {
  value: string
  label: string
}

// ── Module-level cache ──
let _catMap: Map<string, number> | null = null
let _catMapLoading = false
let _catMapPromise: Promise<void> | null = null

// Cache of entries by category_code: Map<category_code, DictOption[]>
const _entryCache = new Map<string, DictOption[]>()

async function _ensureCatMap(): Promise<void> {
  if (_catMap) return
  if (_catMapLoading && _catMapPromise) return _catMapPromise

  _catMapLoading = true
  _catMapPromise = (async () => {
    try {
      const { data } = await datadictApi.categories.list()
      const cats = data?.categories || []
      _catMap = new Map<string, number>()
      for (const c of cats) {
        if (c.category_code && c.id != null) {
          _catMap.set(c.category_code, c.id)
        }
      }
    } catch {
      _catMap = new Map() // empty fallback
    } finally {
      _catMapLoading = false
    }
  })()
  return _catMapPromise
}

function _invalidateCache(): void {
  _catMap = null
  _catMapPromise = null
  _entryCache.clear()
}

/**
 * Composable to load dropdown options from the data dictionary.
 *
 * Usage:
 *   const { loadOptions, getOptions, loading } = useDictOptions()
 *   await loadOptions(['country_code', 'employee_status'])
 *   const countryOpts = getOptions('country_code')  // ComputedRef<DictOption[]>
 */
export function useDictOptions() {
  const loading = ref(false)
  const loaded = ref(new Set<string>())

  /** Fetch entries for one or more category codes. Idempotent — skips already-loaded. */
  async function loadOptions(categoryCodes: string | string[]): Promise<void> {
    const codes = Array.isArray(categoryCodes) ? categoryCodes : [categoryCodes]
    const toFetch = codes.filter(c => !_entryCache.has(c))

    if (toFetch.length === 0) {
      // Mark as loaded even if cached
      for (const c of codes) loaded.value.add(c)
      return
    }

    loading.value = true
    try {
      await _ensureCatMap()

      const fetchPromises = toFetch.map(async (code) => {
        const catId = _catMap?.get(code)
        if (catId == null) {
          console.warn(`[useDictOptions] Category not found: "${code}"`)
          _entryCache.set(code, [])
          return
        }
        try {
          const { data } = await datadictApi.entries.list({
            category_id: catId,
            page_size: 200,
            show_inactive: '0', // only active entries
          })
          const items = data?.items || []
          _entryCache.set(code, items.map((it: any) => ({
            value: it.entry_code,
            label: it.labels || it.entry_code,
          })))
        } catch {
          _entryCache.set(code, [])
        }
      })

      await Promise.all(fetchPromises)
    } finally {
      for (const c of codes) loaded.value.add(c)
      loading.value = false
    }
  }

  /** Get reactive options for a category code. Returns empty array if not loaded. */
  function getOptions(categoryCode: string): ComputedRef<DictOption[]> {
    return computed(() => _entryCache.get(categoryCode) || [])
  }

  /** Get raw entry codes (values only) for a category */
  function getValues(categoryCode: string): ComputedRef<string[]> {
    return computed(() => (_entryCache.get(categoryCode) || []).map(o => o.value))
  }

  /** Check if a category's options have been loaded */
  function hasOptions(categoryCode: string): boolean {
    return _entryCache.has(categoryCode)
  }

  return { loadOptions, getOptions, getValues, hasOptions, loading, invalidateCache: _invalidateCache }
}
