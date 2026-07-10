import { payrollJpApi, payrollSgApi, payrollCnApi } from '@/api/client'
import { JP_STATUS_CONFIG, JP_STATUS_WORKFLOW, jpStatusIndex, JP_ACTION_LABELS, jpActionLabel, parseJpAuditValue } from '@/constants/payrollJp'
import { SG_STATUS_CONFIG, SG_STATUS_WORKFLOW, sgStatusIndex, SG_ACTION_LABELS, sgActionLabel, parseSgAuditValue } from '@/constants/payrollSg'
import { CN_STATUS_CONFIG, CN_STATUS_WORKFLOW, cnStatusIndex, CN_ACTION_LABELS, cnActionLabel, parseCnAuditValue } from '@/constants/payrollCn'

// Inline item category constants (shared between JP and SG)
const _ITEM_CATEGORIES = ['earning', 'deduction', 'employer_cost'] as const
const _ITEM_SUBCATEGORIES = ['base', 'allowance', 'overtime', 'statutory', 'manual'] as const
const _ITEM_CATEGORY_LABELS: Record<string, string> = {
  earning: 'Earning / 収入', deduction: 'Deduction / 控除', employer_cost: 'Employer Cost / 雇主コスト',
}
const _ITEM_SUBCATEGORY_LABELS: Record<string, string> = {
  base: 'Base / 基本', allowance: 'Allowance / 手当', overtime: 'Overtime / 残業',
  statutory: 'Statutory / 法定', manual: 'Manual / 手動',
}

export type CountryCode = 'jp' | 'sg' | 'cn'

export function usePayroll(countryCode: CountryCode) {
  const isJP = countryCode === 'jp'
  const isSG = countryCode === 'sg'
  const isCN = countryCode === 'cn'

  // API client
  const api = isJP ? payrollJpApi : isSG ? payrollSgApi : payrollCnApi

  // Route base
  const baseRoute = `/payroll/${countryCode}`

  // Status config
  const STATUS_CONFIG = isJP ? JP_STATUS_CONFIG : isSG ? SG_STATUS_CONFIG : CN_STATUS_CONFIG
  const STATUS_WORKFLOW = isJP ? JP_STATUS_WORKFLOW : isSG ? SG_STATUS_WORKFLOW : CN_STATUS_WORKFLOW
  const statusIndex = isJP ? jpStatusIndex : isSG ? sgStatusIndex : cnStatusIndex

  // Action labels
  const ACTION_LABELS = isJP ? JP_ACTION_LABELS : isSG ? SG_ACTION_LABELS : CN_ACTION_LABELS
  const actionLabel = isJP ? jpActionLabel : isSG ? sgActionLabel : cnActionLabel
  const parseAuditValue = isJP ? parseJpAuditValue : isSG ? parseSgAuditValue : parseCnAuditValue

  // Item categories (same for all countries)
  const ITEM_CATEGORIES = _ITEM_CATEGORIES
  const ITEM_SUBCATEGORIES = _ITEM_SUBCATEGORIES
  const ITEM_CATEGORY_LABELS = _ITEM_CATEGORY_LABELS
  const ITEM_SUBCATEGORY_LABELS = _ITEM_SUBCATEGORY_LABELS

  // Currency formatting
  const currencySymbol = isSG ? 'SGD ' : '¥'
  function fmtCurrency(v: number): string {
    if (!v && v !== 0) return '-'
    if (isSG) return `SGD ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    return `¥${Number(v).toLocaleString()}`
  }

  // Navigation helper
  function routeTo(path: string) {
    return `${baseRoute}/${path}`
  }

  // i18n key helper: payroll.{countryCode}.{suffix}
  function pk(suffix: string): string {
    return `payroll.${countryCode}.${suffix}`
  }

  return {
    countryCode, isJP, isSG, isCN,
    api, baseRoute,
    STATUS_CONFIG, STATUS_WORKFLOW, statusIndex,
    ACTION_LABELS, actionLabel, parseAuditValue,
    ITEM_CATEGORIES, ITEM_SUBCATEGORIES, ITEM_CATEGORY_LABELS, ITEM_SUBCATEGORY_LABELS,
    currencySymbol, fmtCurrency, routeTo, pk,
  }
}
