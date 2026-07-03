// Invoice shared constants — single source of truth for all invoice/*.vue files.

// ── Invoice Status ──
export const INVOICE_STATUS_CONFIG: Record<string, { type: string; label: string }> = {
  draft: { type: '', label: 'Draft' },
  pending_approval: { type: 'warning', label: 'Pending Approval' },
  approved: { type: 'success', label: 'Approved' },
  sent: { type: 'primary', label: 'Sent' },
  paid: { type: 'info', label: 'Paid' },
}

export const INVOICE_STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'paid', label: 'Paid' },
]

// ── Pending Invoice Status ──
export const INVOICE_PENDING_STATUS_CONFIG: Record<string, { type: string }> = {
  converted: { type: 'success' },
  reminded: { type: 'warning' },
  pending: { type: 'info' },
}

// ── Payment Methods ──
export const INVOICE_PAYMENT_METHODS = [
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'check', label: 'Check' },
] as const

// ── Defaults ──
export const INVOICE_DEFAULTS = {
  currency: 'JPY',
  tax_rate: '10%',
  payment_terms_days: 30,
  status: 'draft',
} as const
