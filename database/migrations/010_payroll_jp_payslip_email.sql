-- Migration 010: Payroll JP Payslip Email Tracking
-- Adds email sending status and content tracking to pay_jp_payslips
-- Date: 2026-07-02

-- ============================================================
-- pay_jp_payslips: email sending status & content tracking
-- ============================================================
ALTER TABLE pay_jp_payslips
    ADD COLUMN IF NOT EXISTS email_status VARCHAR(20) DEFAULT 'not_sent';

ALTER TABLE pay_jp_payslips
    ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;

ALTER TABLE pay_jp_payslips
    ADD COLUMN IF NOT EXISTS sent_by VARCHAR(200);

ALTER TABLE pay_jp_payslips
    ADD COLUMN IF NOT EXISTS email_error TEXT;

ALTER TABLE pay_jp_payslips
    ADD COLUMN IF NOT EXISTS html_content TEXT;

-- ============================================================
-- Comments
-- ============================================================
COMMENT ON COLUMN pay_jp_payslips.email_status IS 'Email sending status: not_sent, pending, sent, failed';
COMMENT ON COLUMN pay_jp_payslips.sent_at IS 'Timestamp when payslip email was successfully sent';
COMMENT ON COLUMN pay_jp_payslips.sent_by IS 'User who triggered the email send';
COMMENT ON COLUMN pay_jp_payslips.email_error IS 'Error message if email sending failed';
COMMENT ON COLUMN pay_jp_payslips.html_content IS 'HTML snapshot of payslip content at time of sending';
