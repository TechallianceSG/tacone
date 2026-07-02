-- Migration 011: Payroll JP Core Business Tables
-- Properly creates pay_jp_payroll_batches, pay_jp_monthly_salary_records, pay_jp_payslips
-- These tables were previously created ad-hoc by db_utils.insert_record (missing columns)
-- Date: 2026-07-02

-- ============================================================
-- 1. pay_jp_payroll_batches — 工资批次主表
-- ============================================================
CREATE TABLE IF NOT EXISTS pay_jp_payroll_batches (
    id SERIAL,
    batch_id VARCHAR(50) PRIMARY KEY,
    country_code VARCHAR(10) DEFAULT 'JP',
    entity_id VARCHAR(50),
    payroll_month VARCHAR(7),
    working_days_in_month NUMERIC(5,1) DEFAULT 22,
    status VARCHAR(20) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    employee_count INTEGER DEFAULT 0,
    gross_total NUMERIC(14,2) DEFAULT 0,
    deduction_total NUMERIC(14,2) DEFAULT 0,
    net_total NUMERIC(14,2) DEFAULT 0,
    employer_cost_total NUMERIC(14,2) DEFAULT 0,
    recalculate_count INTEGER DEFAULT 0,
    confirmed_at TIMESTAMP,
    confirmed_by VARCHAR(200),
    rolled_back_at TIMESTAMP,
    rolled_back_by VARCHAR(200),
    rollback_reason TEXT,
    created_by VARCHAR(200),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ensure columns exist (for tables created before this migration)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pay_jp_payroll_batches') THEN
        -- Add missing columns one by one
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS id SERIAL;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS country_code VARCHAR(10) DEFAULT 'JP';
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS entity_id VARCHAR(50);
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS payroll_month VARCHAR(7);
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS working_days_in_month NUMERIC(5,1) DEFAULT 22;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS employee_count INTEGER DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS gross_total NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS deduction_total NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS net_total NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS employer_cost_total NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS recalculate_count INTEGER DEFAULT 0;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMP;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS confirmed_by VARCHAR(200);
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMP;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS rolled_back_by VARCHAR(200);
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS rollback_reason TEXT;
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS created_by VARCHAR(200);
        ALTER TABLE pay_jp_payroll_batches ADD COLUMN IF NOT EXISTS notes TEXT;
    END IF;
END $$;

COMMENT ON TABLE pay_jp_payroll_batches IS 'Payroll batch/sheet header. One batch per entity per month.';
COMMENT ON COLUMN pay_jp_payroll_batches.batch_id IS 'Unique batch identifier, format JPB-XXXXXXXXXXXX';
COMMENT ON COLUMN pay_jp_payroll_batches.working_days_in_month IS 'Statutory working days in this month (default 22)';
COMMENT ON COLUMN pay_jp_payroll_batches.status IS 'Workflow status: draft, calculated, confirmed, voided';

-- ============================================================
-- 2. pay_jp_monthly_salary_records — 月度工资计算记录
-- ============================================================
CREATE TABLE IF NOT EXISTS pay_jp_monthly_salary_records (
    id SERIAL,
    record_id VARCHAR(50) PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    payroll_month VARCHAR(7),
    country_code VARCHAR(10) DEFAULT 'JP',
    entity_id VARCHAR(50),
    employee_id VARCHAR(50),
    employee_number VARCHAR(50),
    employee_name VARCHAR(200),
    email VARCHAR(200),
    department_label VARCHAR(200),
    team_label VARCHAR(200),
    salary_type VARCHAR(30) DEFAULT 'monthly',
    basic_salary NUMERIC(14,2),
    -- Input fields (editable per batch)
    absence_days NUMERIC(5,1) DEFAULT 0,
    actual_work_days NUMERIC(5,1),
    actual_work_hours NUMERIC(6,1),
    overtime_hours NUMERIC(6,1) DEFAULT 0,
    paid_leave_days NUMERIC(5,1) DEFAULT 0,
    sick_leave_days NUMERIC(5,1) DEFAULT 0,
    -- Allowance fields (editable per batch)
    commute_allowance NUMERIC(14,2),
    housing_allowance NUMERIC(14,2),
    family_allowance NUMERIC(14,2),
    position_allowance NUMERIC(14,2),
    fixed_allowance NUMERIC(14,2),
    transport_allowance NUMERIC(14,2),
    phone_allowance NUMERIC(14,2),
    performance_bonus NUMERIC(14,2),
    project_bonus NUMERIC(14,2),
    other_allowance NUMERIC(14,2),
    other_deduction NUMERIC(14,2),
    -- Calculated fields
    base_pay_calculated NUMERIC(14,2),
    gross_pay NUMERIC(14,2),
    health_insurance_employee NUMERIC(14,2),
    pension_employee NUMERIC(14,2),
    employment_insurance_employee NUMERIC(14,2),
    care_insurance_employee NUMERIC(14,2),
    income_tax NUMERIC(14,2),
    residence_tax NUMERIC(14,2),
    monthly_resident_tax NUMERIC(14,2),
    recurring_deductions NUMERIC(14,2),
    deduction_total NUMERIC(14,2),
    net_pay NUMERIC(14,2),
    employer_cost_total NUMERIC(14,2),
    -- Tracking fields
    status VARCHAR(20) DEFAULT 'calculated',
    manually_edited BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMP,
    edited_by VARCHAR(200),
    calculation_detail JSONB,
    last_calculated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pay_jp_monthly_salary_records') THEN
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS id SERIAL;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS batch_id VARCHAR(50);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS payroll_month VARCHAR(7);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS country_code VARCHAR(10) DEFAULT 'JP';
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS entity_id VARCHAR(50);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS employee_id VARCHAR(50);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS employee_number VARCHAR(50);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS employee_name VARCHAR(200);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS email VARCHAR(200);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS department_label VARCHAR(200);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS team_label VARCHAR(200);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS salary_type VARCHAR(30) DEFAULT 'monthly';
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS basic_salary NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS absence_days NUMERIC(5,1) DEFAULT 0;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS actual_work_days NUMERIC(5,1);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS actual_work_hours NUMERIC(6,1);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS overtime_hours NUMERIC(6,1) DEFAULT 0;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS paid_leave_days NUMERIC(5,1) DEFAULT 0;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS sick_leave_days NUMERIC(5,1) DEFAULT 0;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS commute_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS housing_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS family_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS position_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS fixed_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS transport_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS phone_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS performance_bonus NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS project_bonus NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS other_allowance NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS other_deduction NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS base_pay_calculated NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS gross_pay NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS health_insurance_employee NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS pension_employee NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS employment_insurance_employee NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS care_insurance_employee NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS income_tax NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS residence_tax NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS monthly_resident_tax NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS recurring_deductions NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS deduction_total NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS net_pay NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS employer_cost_total NUMERIC(14,2);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'calculated';
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS manually_edited BOOLEAN DEFAULT FALSE;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS edited_by VARCHAR(200);
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS calculation_detail JSONB;
        ALTER TABLE pay_jp_monthly_salary_records ADD COLUMN IF NOT EXISTS last_calculated_at TIMESTAMP;
    END IF;
END $$;

COMMENT ON TABLE pay_jp_monthly_salary_records IS 'Per-employee monthly payroll calculation results. One row per employee per batch.';
COMMENT ON COLUMN pay_jp_monthly_salary_records.record_id IS 'Unique record identifier, format JPR-XXXXXXXXXXXX';

-- ============================================================
-- 3. pay_jp_payslips — 工资单
-- ============================================================
CREATE TABLE IF NOT EXISTS pay_jp_payslips (
    id SERIAL,
    record_id VARCHAR(50) PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    employee_id VARCHAR(50),
    employee_number VARCHAR(50),
    employee_name VARCHAR(200),
    email_to VARCHAR(200),
    payroll_month VARCHAR(7),
    gross_pay NUMERIC(14,2),
    net_pay NUMERIC(14,2),
    email_status VARCHAR(20) DEFAULT 'not_sent',
    sent_at TIMESTAMP,
    sent_by VARCHAR(200),
    email_error TEXT,
    html_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pay_jp_payslips') THEN
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS id SERIAL;
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS batch_id VARCHAR(50);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS employee_id VARCHAR(50);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS employee_number VARCHAR(50);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS employee_name VARCHAR(200);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS email_to VARCHAR(200);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS payroll_month VARCHAR(7);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS gross_pay NUMERIC(14,2);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS net_pay NUMERIC(14,2);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS email_status VARCHAR(20) DEFAULT 'not_sent';
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS sent_by VARCHAR(200);
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS email_error TEXT;
        ALTER TABLE pay_jp_payslips ADD COLUMN IF NOT EXISTS html_content TEXT;
    END IF;
END $$;

COMMENT ON TABLE pay_jp_payslips IS 'Payslip records generated on batch confirmation. Used for email delivery tracking.';
COMMENT ON COLUMN pay_jp_payslips.email_status IS 'Email status: not_sent, pending, sent, failed';
