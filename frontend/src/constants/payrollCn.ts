// CN Payroll shared constants — single source of truth for all payroll/cn/*.vue files.

// ── Batch Status ──
export const CN_STATUS_CONFIG: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.cn.status_draft' },
  calculated: { type: 'warning', label: 'payroll.cn.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.cn.status_confirmed' },
  voided: { type: 'danger', label: 'payroll.cn.status_voided' },
}

export const CN_STATUS_WORKFLOW = ['draft', 'calculated', 'confirmed'] as const

export function cnStatusIndex(s: string): number {
  return (CN_STATUS_WORKFLOW as readonly string[]).indexOf(s)
}

// ── Audit Action Labels ──
export const CN_ACTION_LABELS: Record<string, { icon: string; label: string; color: string }> = {
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

export function cnActionLabel(action: string) {
  return CN_ACTION_LABELS[action] || { icon: '📋', label: action, color: '#909399' }
}

// ── Audit Value Parser ──
export function parseCnAuditValue(v: any): string {
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
