-- ============================================================
-- TACAI Pay JP — Data Dictionary: add category column + salary types
-- FY2026 (令和8年度)
-- Run: psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f this_file.sql
-- ============================================================

-- Add category column to distinguish insurance vs salary_type entries
ALTER TABLE pay_jp_rate_type_labels
ADD COLUMN IF NOT EXISTS category VARCHAR(30) DEFAULT 'insurance';

-- Tag existing entries
UPDATE pay_jp_rate_type_labels SET category = 'insurance' WHERE category IS NULL;

-- Seed salary type labels into the data dictionary
INSERT INTO pay_jp_rate_type_labels (rate_type, labels, display_order, category) VALUES
('salary_type_monthly',          '{"ja": "月給", "en": "Monthly Salary", "zh": "月薪"}', 10, 'salary_type'),
('salary_type_hourly',           '{"ja": "時給", "en": "Hourly Wage", "zh": "时薪"}', 11, 'salary_type'),
('salary_type_daily',            '{"ja": "日給", "en": "Daily Wage", "zh": "日薪"}', 12, 'salary_type'),
('salary_type_monthly_fixed_ot', '{"ja": "月給＋固定残業", "en": "Monthly + Fixed OT", "zh": "月薪+固定加班"}', 13, 'salary_type'),
('salary_type_monthly_hour',     '{"ja": "月給＋時給", "en": "Monthly + Hourly", "zh": "月薪+时薪"}', 14, 'salary_type')
ON CONFLICT (rate_type) DO UPDATE SET
    labels = EXCLUDED.labels,
    display_order = EXCLUDED.display_order,
    category = EXCLUDED.category,
    updated_at = CURRENT_TIMESTAMP;
