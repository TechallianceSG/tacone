-- Data Cleanup: Remove stale/incomplete records from pay_jp_payroll_batches
-- Run AFTER migration 011_payroll_jp_core_tables.sql
-- Date: 2026-07-02

-- Delete batch records that have NULL batch_id (created before table had proper columns)
DELETE FROM pay_jp_payroll_batches WHERE batch_id IS NULL;

-- Also clean up orphaned monthly salary records (records with no valid batch_id)
DELETE FROM pay_jp_monthly_salary_records WHERE batch_id IS NULL OR batch_id = '';

-- Also clean up orphaned payslip records
DELETE FROM pay_jp_payslips WHERE batch_id IS NULL OR batch_id = '';

-- Verify
SELECT 'pay_jp_payroll_batches' AS table_name, count(*) AS remaining FROM pay_jp_payroll_batches
UNION ALL
SELECT 'pay_jp_monthly_salary_records', count(*) FROM pay_jp_monthly_salary_records
UNION ALL
SELECT 'pay_jp_payslips', count(*) FROM pay_jp_payslips
UNION ALL
SELECT 'pay_jp_audit_logs', count(*) FROM pay_jp_audit_logs;
