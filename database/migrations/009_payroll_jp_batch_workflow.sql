-- Migration 009: Payroll JP Batch Workflow Enhancement
-- Adds workflow tracking fields to pay_jp_payroll_batches and pay_jp_monthly_salary_records
-- Date: 2026-07-02

-- ============================================================
-- pay_jp_payroll_batches: workflow state tracking
-- ============================================================
ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS recalculate_count INTEGER DEFAULT 0;

ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP;

ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS confirmed_by VARCHAR(200);

ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMP;

ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS rolled_back_by VARCHAR(200);

ALTER TABLE pay_jp_payroll_batches
    ADD COLUMN IF NOT EXISTS rollback_reason TEXT;

-- ============================================================
-- pay_jp_monthly_salary_records: manual edit & calculation tracking
-- ============================================================
ALTER TABLE pay_jp_monthly_salary_records
    ADD COLUMN IF NOT EXISTS manually_edited BOOLEAN DEFAULT FALSE;

ALTER TABLE pay_jp_monthly_salary_records
    ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;

ALTER TABLE pay_jp_monthly_salary_records
    ADD COLUMN IF NOT EXISTS edited_by VARCHAR(200);

ALTER TABLE pay_jp_monthly_salary_records
    ADD COLUMN IF NOT EXISTS calculation_detail JSONB;

ALTER TABLE pay_jp_monthly_salary_records
    ADD COLUMN IF NOT EXISTS last_calculated_at TIMESTAMP;

-- ============================================================
-- Comments
-- ============================================================
COMMENT ON COLUMN pay_jp_payroll_batches.recalculate_count IS 'Number of times batch has been (re)calculated';
COMMENT ON COLUMN pay_jp_payroll_batches.confirmed_at IS 'Timestamp when batch was confirmed (定稿)';
COMMENT ON COLUMN pay_jp_payroll_batches.confirmed_by IS 'User who confirmed the batch';
COMMENT ON COLUMN pay_jp_payroll_batches.rolled_back_at IS 'Timestamp when batch was rolled back from confirmed to calculated';
COMMENT ON COLUMN pay_jp_payroll_batches.rolled_back_by IS 'User who performed the rollback';
COMMENT ON COLUMN pay_jp_payroll_batches.rollback_reason IS 'Reason provided for rollback';

COMMENT ON COLUMN pay_jp_monthly_salary_records.manually_edited IS 'Whether the record has been manually edited after calculation';
COMMENT ON COLUMN pay_jp_monthly_salary_records.edited_at IS 'Timestamp of last manual edit';
COMMENT ON COLUMN pay_jp_monthly_salary_records.edited_by IS 'User who performed the manual edit';
COMMENT ON COLUMN pay_jp_monthly_salary_records.calculation_detail IS 'JSON: salary_type, formula, inputs, breakdown, messages from calculation';
COMMENT ON COLUMN pay_jp_monthly_salary_records.last_calculated_at IS 'Timestamp of last calculation (initial or recalculation)';
