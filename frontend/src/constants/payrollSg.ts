// ── Singapore Payroll Constants ──

export const SG_STATUS_CONFIG: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'payroll.jp.status_draft' },
  calculated: { type: 'warning', label: 'payroll.jp.status_calculated' },
  confirmed: { type: 'success', label: 'payroll.jp.status_confirmed' },
  payslips_generated: { type: 'success', label: 'payroll.sg.payslips_generated' },
  voided: { type: 'danger', label: 'payroll.jp.status_voided' },
}

export const SG_STATUS_WORKFLOW = ['draft', 'calculated', 'confirmed'] as const

export function sgStatusIndex(s: string): number {
  const idx = SG_STATUS_WORKFLOW.indexOf(s as any)
  return idx >= 0 ? idx : 0
}

export const SG_ACTION_LABELS: Record<string, { icon: string; label: string; color: string }> = {
  CALCULATE:   { icon: '🧮', label: 'payroll.sg.action_calculate', color: '#409EFF' },
  CONFIRM:     { icon: '✅', label: 'payroll.sg.action_confirm', color: '#67C23A' },
  ROLLBACK:    { icon: '↩️', label: 'payroll.sg.action_rollback', color: '#E6A23C' },
  EDIT_RECORD: { icon: '✏️', label: 'payroll.sg.action_edit_record', color: '#909399' },
  VOID:        { icon: '🚫', label: 'payroll.sg.action_void', color: '#F56C6C' },
  DELETE:      { icon: '🗑️', label: 'payroll.sg.action_delete', color: '#F56C6C' },
  EMAIL_SENT:  { icon: '📧', label: 'payroll.sg.action_email_sent', color: '#67C23A' },
  ACTIVATE:    { icon: '🔄', label: 'payroll.sg.action_activate', color: '#67C23A' },
  DEACTIVATE:  { icon: '⏸️', label: 'payroll.sg.action_deactivate', color: '#E6A23C' },
}

export function sgActionLabel(action: string) {
  return SG_ACTION_LABELS[action] || { icon: '📋', label: action, color: '#909399' }
}

export function parseSgAuditValue(v: any): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'string') {
    try { const p = JSON.parse(v); return typeof p === 'object' ? JSON.stringify(p) : v } catch { return v }
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

// ── Reference data (item categories, salary types, CPF age ranges) ──
// Moved to backend API: GET /api/payroll/sg/constants
// Use usePayrollSgConstants() composable instead of importing from here.
