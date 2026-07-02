-- ============================================================
-- TACAI Pay JP — editable_in_master column for payroll item definitions
-- Adds the ability to mark which payroll items can be modified
-- in employee salary master data and payroll batches.
-- Run: psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f this_file.sql
-- ============================================================

-- Add editable_in_master column to payroll item definitions
ALTER TABLE pay_jp_payroll_item_definitions
ADD COLUMN IF NOT EXISTS editable_in_master BOOLEAN DEFAULT false;

-- Set default editable_in_master = true for earning items that are typically
-- configured per employee (allowances, bonuses, etc.)
UPDATE pay_jp_payroll_item_definitions SET editable_in_master = true
WHERE category = 'earning' AND sub_category IN ('allowance', 'manual');

-- Set editable_in_master = true for manual deduction items
UPDATE pay_jp_payroll_item_definitions SET editable_in_master = true
WHERE category = 'deduction' AND sub_category = 'manual';

-- Set editable_in_master = true for overtime items (configurable per employee)
UPDATE pay_jp_payroll_item_definitions SET editable_in_master = true
WHERE sub_category = 'overtime';

-- Set editable_in_master = true for attendance-related items
UPDATE pay_jp_payroll_item_definitions SET editable_in_master = true
WHERE sub_category = 'attendance';

COMMENT ON COLUMN pay_jp_payroll_item_definitions.editable_in_master IS 'When true, this payroll item can be defined/modified in employee salary master data and in payroll batch records';
