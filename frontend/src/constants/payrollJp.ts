// JP Payroll shared constants — single source of truth for all payroll/jp/*.vue files.
// Import from this file instead of copy-pasting configs between components.

// ── Batch Status ──
export const JP_STATUS_CONFIG: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.jp.status_draft' },
  calculated: { type: 'warning', label: 'payroll.jp.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.jp.status_confirmed' },
  voided: { type: 'danger', label: 'payroll.jp.status_voided' },
}

export const JP_STATUS_WORKFLOW = ['draft', 'calculated', 'confirmed'] as const

export function jpStatusIndex(s: string): number {
  return (JP_STATUS_WORKFLOW as readonly string[]).indexOf(s)
}

// ── Audit Action Labels ──
export const JP_ACTION_LABELS: Record<string, { icon: string; label: string; color: string }> = {
  CALCULATE:           { icon: '🧮', label: '批量计算', color: '#409EFF' },
  RECALCULATE:         { icon: '🔄', label: '重新计算', color: '#409EFF' },
  RECALCULATE_SINGLE:  { icon: '🔁', label: '逐条重算', color: '#409EFF' },
  CONFIRM:             { icon: '✅', label: '定稿', color: '#67C23A' },
  ROLLBACK:            { icon: '↩️', label: '回退', color: '#E6A23C' },
  EDIT_RECORD:         { icon: '✏️', label: '编辑记录', color: '#909399' },
  EMAIL_SENT:          { icon: '📧', label: '发送邮件', color: '#409EFF' },
  EMAIL_BATCH_SENT:    { icon: '📧', label: '批量发送', color: '#409EFF' },
  EMAIL_SELECTED_SENT: { icon: '📧', label: '选中发送', color: '#409EFF' },
  VOID:                { icon: '🚫', label: '作废', color: '#F56C6C' },
  DELETE:              { icon: '🗑️', label: '删除', color: '#F56C6C' },
}

export function jpActionLabel(action: string) {
  return JP_ACTION_LABELS[action] || { icon: '📋', label: action, color: '#909399' }
}

// ── Audit Value Parser (shared between batch list & detail) ──
export function parseJpAuditValue(v: any): string {
  if (!v) return ''
  try {
    const obj = typeof v === 'string' ? JSON.parse(v) : v
    const parts: string[] = []
    if (obj.status) parts.push(`状态→${obj.status}`)
    if (obj.employee_count !== undefined) parts.push(`${obj.employee_count}人`)
    if (obj.gross_total !== undefined) parts.push(`应发¥${Number(obj.gross_total).toLocaleString()}`)
    if (obj.net_total !== undefined) parts.push(`实发¥${Number(obj.net_total).toLocaleString()}`)
    if (obj.reason) parts.push(`原因: ${obj.reason}`)
    if (obj.deleted) parts.push(`已删除`)
    if (obj.records_deleted !== undefined) parts.push(`关联${obj.records_deleted}条记录已删除`)
    if (obj.email_status) parts.push(`邮件: ${obj.email_status}`)
    if (obj.sent !== undefined) parts.push(`成功${obj.sent}封${obj.failed ? ` 失败${obj.failed}封` : ''}`)
    if (parts.length) return parts.join(' | ')
    return JSON.stringify(obj).substring(0, 150)
  } catch { return String(v).substring(0, 150) }
}

// ── Insurance Rate Type Labels ──
export const JP_RATE_TYPE_LABELS: Record<string, string> = {
  pension: '健康保険',
  health_insurance: '健康保険',
  pension_insurance: '厚生年金保険',
  nursing_care: '介護保険',
  employment: '雇用保険',
  employment_insurance: '雇用保険',
  child_allowance: '児童手当拠出金',
  care_insurance: '介護保険',
}

// ── Parameter Types ──
export const JP_PARAM_TYPES = {
  SOCIAL_INSURANCE_RATE: 'social_insurance_rate',
  WITHHOLDING_TAX_BRACKET: 'withholding_tax_bracket',
  STANDARD_REMUNERATION_GRADE: 'standard_remuneration_grade',
  ACCIDENT_INSURANCE_RATE: 'accident_insurance_rate',
} as const

// ── Item Definition Labels ──
export const JP_ITEM_CATEGORY_LABELS: Record<string, string> = {
  earning: '支給 (Earning)',
  deduction: '控除 (Deduction)',
  employer_cost: '会社負担 (Employer Cost)',
}

export const JP_ITEM_SUBCATEGORY_LABELS: Record<string, string> = {
  base: '基本',
  overtime: '残業',
  allowance: '手当',
  manual: '手動入力',
  statutory: '法定',
  attendance: '勤怠',
}

export const JP_ITEM_CATEGORIES = ['earning', 'deduction', 'employer_cost'] as const
