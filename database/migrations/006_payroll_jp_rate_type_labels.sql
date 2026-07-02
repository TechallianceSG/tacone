-- ============================================================
-- TACAI Pay JP — 料率タイプデータ辞書 (rate_type labels)
-- FY2026 (令和8年度)
-- Run: psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f this_file.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS pay_jp_rate_type_labels (
    rate_type       VARCHAR(30) PRIMARY KEY,
    labels          JSONB DEFAULT '{}',
    display_order   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed FY2026 labels
INSERT INTO pay_jp_rate_type_labels (rate_type, labels, display_order) VALUES
('health_insurance', '{"ja": "健康保険（協会けんぽ）", "en": "Health Insurance", "zh": "健康保险（协会健保）"}', 1),
('nursing_care',    '{"ja": "介護保険", "en": "Nursing Care Insurance", "zh": "护理保险"}', 2),
('pension',         '{"ja": "厚生年金保険", "en": "Pension Insurance", "zh": "厚生年金保险"}', 3),
('employment',      '{"ja": "雇用保険", "en": "Employment Insurance", "zh": "雇佣保险"}', 4),
('child_allowance', '{"ja": "児童手当拠出金", "en": "Child Allowance Contribution", "zh": "儿童津贴缴纳金"}', 5)
ON CONFLICT (rate_type) DO UPDATE SET
    labels = EXCLUDED.labels,
    display_order = EXCLUDED.display_order,
    updated_at = CURRENT_TIMESTAMP;
