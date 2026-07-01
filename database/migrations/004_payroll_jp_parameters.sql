-- ============================================================
-- TACAI Pay JP — 基礎パラメータテーブル (Phase 0)
-- FY2026 (令和8年度) rates
-- Run: psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f this_file.sql
-- ============================================================

-- 1. Social Insurance Rates (社会保険料率)
CREATE TABLE IF NOT EXISTS pay_jp_social_insurance_rates (
    id              SERIAL PRIMARY KEY,
    rate_type       VARCHAR(30)   NOT NULL,
    prefecture      VARCHAR(10)   DEFAULT NULL,
    employee_rate   DECIMAL(7,4)  NOT NULL,
    employer_rate   DECIMAL(7,4)  NOT NULL,
    applicable_from DATE          NOT NULL,
    applicable_to   DATE          DEFAULT NULL,
    is_current      BOOLEAN       DEFAULT true,
    notes           TEXT          DEFAULT NULL,
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_sir_type ON pay_jp_social_insurance_rates(rate_type);
CREATE INDEX IF NOT EXISTS idx_pjp_sir_current ON pay_jp_social_insurance_rates(is_current) WHERE is_current = true;

-- 2. Standard Remuneration Grades (標準報酬月額等級表)
CREATE TABLE IF NOT EXISTS pay_jp_standard_remuneration_grades (
    id                      SERIAL PRIMARY KEY,
    grade_type              VARCHAR(20) NOT NULL,
    grade_number            INTEGER     NOT NULL,
    min_monthly_amount      INTEGER     NOT NULL,
    max_monthly_amount      INTEGER     NOT NULL,
    standard_monthly_amount INTEGER     NOT NULL,
    applicable_from         DATE        NOT NULL,
    applicable_to           DATE        DEFAULT NULL,
    is_current              BOOLEAN     DEFAULT true,
    created_at              TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_srg_type ON pay_jp_standard_remuneration_grades(grade_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pjp_srg_grade ON pay_jp_standard_remuneration_grades(grade_type, grade_number, applicable_from);

-- 3. Withholding Tax Brackets (源泉徴収税額表)
CREATE TABLE IF NOT EXISTS pay_jp_withholding_tax_brackets (
    id              SERIAL PRIMARY KEY,
    table_type      VARCHAR(10) NOT NULL,
    min_salary      INTEGER     NOT NULL,
    max_salary      INTEGER     NOT NULL,
    tax_dep_0       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_1       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_2       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_3       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_4       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_5       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_6       INTEGER     NOT NULL DEFAULT 0,
    tax_dep_7       INTEGER     NOT NULL DEFAULT 0,
    applicable_from DATE        NOT NULL,
    applicable_to   DATE        DEFAULT NULL,
    is_current      BOOLEAN     DEFAULT true,
    created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_wtb_type ON pay_jp_withholding_tax_brackets(table_type);
CREATE INDEX IF NOT EXISTS idx_pjp_wtb_current ON pay_jp_withholding_tax_brackets(is_current) WHERE is_current = true;

-- 4. Workers Accident Insurance Rates (労災保険料率)
CREATE TABLE IF NOT EXISTS pay_jp_accident_insurance_rates (
    id              SERIAL PRIMARY KEY,
    industry_code   VARCHAR(10)  NOT NULL,
    industry_name_ja VARCHAR(200) NOT NULL,
    industry_name_en VARCHAR(200) DEFAULT NULL,
    rate            DECIMAL(7,4) NOT NULL,
    applicable_from DATE         NOT NULL,
    applicable_to   DATE         DEFAULT NULL,
    is_current      BOOLEAN      DEFAULT true,
    notes           TEXT         DEFAULT NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_air_code ON pay_jp_accident_insurance_rates(industry_code);
CREATE INDEX IF NOT EXISTS idx_pjp_air_current ON pay_jp_accident_insurance_rates(is_current) WHERE is_current = true;

-- 5. Audit Logs (監査ログ)
CREATE TABLE IF NOT EXISTS pay_jp_audit_logs (
    id              SERIAL PRIMARY KEY,
    module          VARCHAR(50)   NOT NULL DEFAULT 'pay_jp',
    record_id       VARCHAR(100)  DEFAULT NULL,
    action          VARCHAR(50)   NOT NULL,
    user_name       VARCHAR(200)  DEFAULT NULL,
    table_name      VARCHAR(100)  NOT NULL,
    before_value    JSONB         DEFAULT NULL,
    after_value     JSONB         DEFAULT NULL,
    ip_address      VARCHAR(50)   DEFAULT NULL,
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_ajl_table ON pay_jp_audit_logs(table_name);
CREATE INDEX IF NOT EXISTS idx_pjp_ajl_created ON pay_jp_audit_logs(created_at DESC);

-- 6. Payroll Item Definitions (給与項目定義)
CREATE TABLE IF NOT EXISTS pay_jp_payroll_item_definitions (
    item_id                 TEXT PRIMARY KEY,
    code                    TEXT NOT NULL,
    category                TEXT NOT NULL,
    sub_category            TEXT,
    labels                  JSONB DEFAULT '{}',
    taxable                 BOOLEAN DEFAULT true,
    social_insurance_base   BOOLEAN DEFAULT true,
    employment_insurance_base BOOLEAN DEFAULT true,
    payslip_visible         BOOLEAN DEFAULT true,
    requires_reason         BOOLEAN DEFAULT false,
    display_order           INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'active',
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pjp_pid_category ON pay_jp_payroll_item_definitions(category);
CREATE INDEX IF NOT EXISTS idx_pjp_pid_order ON pay_jp_payroll_item_definitions(display_order);
