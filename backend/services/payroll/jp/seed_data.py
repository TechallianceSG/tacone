#!/usr/bin/env python3
"""TACAI Pay JP — Seed FY2026 (令和8年度) parameter data.

Usage:
    python3 seed_data.py

Requires: PostgreSQL running, DB_* env vars set.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# ── Add shared lib to path ──
_shared_path = Path(__file__).resolve().parents[3] / 'shared'
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

try:
    from db_utils import execute, execute_many, fetch_all
except ImportError as e:
    print(f"ERROR: Cannot import db_utils — {e}")
    sys.exit(1)

AF = date(2026, 4, 1)  # Applicable From: April 2026

# ═══════════════════════════════════════════════════════════════
# 0. Rate Type Labels (料率タイプデータ辞書)
# ═══════════════════════════════════════════════════════════════
RATE_TYPE_LABELS = [
    ("nursing_care",     '{"ja": "介護保険", "en": "Nursing Care Insurance", "zh": "护理保险"}', 1),
    ("employment",       '{"ja": "雇用保険", "en": "Employment Insurance", "zh": "雇佣保险"}', 2),
    ("pension",          '{"ja": "厚生年金保険", "en": "Pension Insurance", "zh": "厚生年金保险"}', 3),
    ("child_allowance",  '{"ja": "児童手当拠出金", "en": "Child Allowance Contribution", "zh": "儿童津贴缴纳金"}', 4),
]

# ═══════════════════════════════════════════════════════════════
# 1. Social Insurance Rates (社会保険料率)
# ═══════════════════════════════════════════════════════════════
SOCIAL_INSURANCE = [
    ("pension",          None, 9.15,  9.15,  AF, "厚生年金 18.3%折半"),
    ("nursing_care",     None, 0.90,  0.90,  AF, "介護保険 1.8%折半 40-64歳"),
    ("employment",       None, 0.60,  0.95,  AF, "雇用保険 一般事業"),
    ("child_allowance",  None, 0.00,  0.36,  AF, "児童手当拠出金 会社のみ"),
    ("health_insurance", "13", 5.00,  5.00,  AF, "東京 10.00%"),
    ("health_insurance", "27", 5.145, 5.145, AF, "大阪 10.29%"),
    ("health_insurance", "14", 5.065, 5.065, AF, "神奈川 10.13%"),
    ("health_insurance", "23", 5.02,  5.02,  AF, "愛知 10.04%"),
    ("health_insurance", None, 5.00,  5.00,  AF, "全国平均 10.00%概算"),
]

# ═══════════════════════════════════════════════════════════════
# 2. Standard Remuneration Grades (標準報酬月額等級表)
# ═══════════════════════════════════════════════════════════════
HEALTH_GRADES = [
    (1,  0,      63000,  58000),  (2,  63000,  73000,  68000),
    (3,  73000,  83000,  78000),  (4,  83000,  93000,  88000),
    (5,  93000,  101000, 98000),  (6,  101000, 107000, 104000),
    (7,  107000, 114000, 110000), (8,  114000, 122000, 118000),
    (9,  122000, 130000, 126000), (10, 130000, 138000, 134000),
    (11, 138000, 146000, 142000), (12, 146000, 155000, 150000),
    (13, 155000, 165000, 160000), (14, 165000, 175000, 170000),
    (15, 175000, 185000, 180000), (16, 185000, 195000, 190000),
    (17, 195000, 210000, 200000), (18, 210000, 230000, 220000),
    (19, 230000, 250000, 240000), (20, 250000, 270000, 260000),
    (21, 270000, 290000, 280000), (22, 290000, 310000, 300000),
    (23, 310000, 330000, 320000), (24, 330000, 350000, 340000),
    (25, 350000, 370000, 360000), (26, 370000, 395000, 380000),
    (27, 395000, 425000, 410000), (28, 425000, 455000, 440000),
    (29, 455000, 485000, 470000), (30, 485000, 515000, 500000),
    (31, 515000, 545000, 530000), (32, 545000, 575000, 560000),
    (33, 575000, 605000, 590000), (34, 605000, 635000, 620000),
    (35, 635000, 665000, 650000), (36, 665000, 695000, 680000),
    (37, 695000, 730000, 710000), (38, 730000, 770000, 750000),
    (39, 770000, 810000, 790000), (40, 810000, 855000, 830000),
    (41, 855000, 905000, 880000), (42, 905000, 955000, 930000),
    (43, 955000, 1005000, 980000), (44, 1005000, 1055000, 1030000),
    (45, 1055000, 1115000, 1090000), (46, 1115000, 1175000, 1150000),
    (47, 1175000, 1235000, 1210000), (48, 1235000, 1295000, 1270000),
    (49, 1295000, 1355000, 1330000), (50, 1355000, 9999999, 1390000),
]

PENSION_GRADES = [
    (1,  0,      93000,  88000),  (2,  93000,  101000, 98000),
    (3,  101000, 107000, 104000), (4,  107000, 114000, 110000),
    (5,  114000, 122000, 118000), (6,  122000, 130000, 126000),
    (7,  130000, 138000, 134000), (8,  138000, 146000, 142000),
    (9,  146000, 155000, 150000), (10, 155000, 165000, 160000),
    (11, 165000, 175000, 170000), (12, 175000, 185000, 180000),
    (13, 185000, 195000, 190000), (14, 195000, 210000, 200000),
    (15, 210000, 230000, 220000), (16, 230000, 250000, 240000),
    (17, 250000, 270000, 260000), (18, 270000, 290000, 280000),
    (19, 290000, 310000, 300000), (20, 310000, 330000, 320000),
    (21, 330000, 350000, 340000), (22, 350000, 370000, 360000),
    (23, 370000, 395000, 380000), (24, 395000, 425000, 410000),
    (25, 425000, 455000, 440000), (26, 455000, 485000, 470000),
    (27, 485000, 515000, 500000), (28, 515000, 545000, 530000),
    (29, 545000, 575000, 560000), (30, 575000, 605000, 590000),
    (31, 605000, 635000, 620000), (32, 635000, 9999999, 650000),
]

# ═══════════════════════════════════════════════════════════════
# 3. Withholding Tax Brackets — Monthly Table (源泉徴収税額表 月額)
# ═══════════════════════════════════════════════════════════════
MONTHLY_TAX = [
    (0,     88000,  0,    0,    0,    0,    0,    0,    0,    0),
    (88000, 89000,  130,  0,    0,    0,    0,    0,    0,    0),
    (89000, 90000,  180,  0,    0,    0,    0,    0,    0,    0),
    (90000, 91000,  230,  0,    0,    0,    0,    0,    0,    0),
    (91000, 92000,  290,  0,    0,    0,    0,    0,    0,    0),
    (92000, 93000,  340,  0,    0,    0,    0,    0,    0,    0),
    (93000, 94000,  390,  0,    0,    0,    0,    0,    0,    0),
    (94000, 95000,  440,  0,    0,    0,    0,    0,    0,    0),
    (99000, 100000, 700,  0,    0,    0,    0,    0,    0,    0),
    (100000,101000, 750,  0,    0,    0,    0,    0,    0,    0),
    (104000,105000, 940,  0,    0,    0,    0,    0,    0,    0),
    (109000,110000, 1180, 0,    0,    0,    0,    0,    0,    0),
    (110000,112000, 1250, 0,    0,    0,    0,    0,    0,    0),
    (112000,114000, 1360, 0,    0,    0,    0,    0,    0,    0),
    (116000,118000, 1580, 0,    0,    0,    0,    0,    0,    0),
    (120000,122000, 1800, 0,    0,    0,    0,    0,    0,    0),
    (124000,126000, 2030, 0,    0,    0,    0,    0,    0,    0),
    (128000,130000, 2260, 0,    0,    0,    0,    0,    0,    0),
    (130000,132000, 2380, 0,    0,    0,    0,    0,    0,    0),
    (134000,136000, 2600, 0,    0,    0,    0,    0,    0,    0),
    (136000,138000, 2720, 80,   0,    0,    0,    0,    0,    0),
    (138000,140000, 2830, 180,  0,    0,    0,    0,    0,    0),
    (140000,142000, 2950, 310,  0,    0,    0,    0,    0,    0),
    (142000,144000, 3080, 440,  0,    0,    0,    0,    0,    0),
    (144000,146000, 3220, 580,  0,    0,    0,    0,    0,    0),
    (148000,150000, 3490, 850,  0,    0,    0,    0,    0,    0),
    (150000,152000, 3620, 980,  0,    0,    0,    0,    0,    0),
    (154000,156000, 3890, 1250, 0,    0,    0,    0,    0,    0),
    (158000,160000, 4160, 1520, 0,    0,    0,    0,    0,    0),
    (162000,164000, 4430, 1790, 0,    0,    0,    0,    0,    0),
    (166000,168000, 4700, 2060, 0,    0,    0,    0,    0,    0),
    (170000,172000, 4970, 2330, 0,    0,    0,    0,    0,    0),
    (174000,176000, 5240, 2600, 0,    0,    0,    0,    0,    0),
    (178000,180000, 5510, 2870, 0,    0,    0,    0,    0,    0),
    (182000,184000, 5780, 3140, 0,    0,    0,    0,    0,    0),
    (186000,188000, 6050, 3410, 0,    0,    0,    0,    0,    0),
    (190000,192000, 6410, 3770, 890,  0,    0,    0,    0,    0),
    (192000,194000, 6700, 4060, 1190, 0,    0,    0,    0,    0),
    (196000,198000, 7290, 4650, 1780, 0,    0,    0,    0,    0),
    (200000,204000, 7990, 5350, 2480, 0,    0,    0,    0,    0),
    (204000,208000, 8620, 5980, 3120, 0,    0,    0,    0,    0),
    (208000,212000, 9250, 6610, 3750, 0,    0,    0,    0,    0),
    (212000,216000, 9880, 7240, 4380, 1160, 0,    0,    0,    0),
    (216000,220000, 10510,7870, 5010, 1790, 0,    0,    0,    0),
    (220000,224000, 11140,8500, 5640, 2420, 0,    0,    0,    0),
    (224000,228000, 11770,9130, 6270, 3050, 0,    0,    0,    0),
    (232000,236000, 13030,10390,7530, 4310, 600,  0,    0,    0),
    (240000,244000, 14290,11650,8790, 5570, 1860, 0,    0,    0),
    (248000,252000, 15550,12910,10050,6830, 3120, 0,    0,    0),
    (256000,260000, 16810,14170,11310,8090, 4380, 280,  0,    0),
    (264000,268000, 18070,15430,12570,9350, 5640, 1540, 0,    0),
    (272000,276000, 19500,16730,13870,10610,6900, 2800, 0,    0),
    (280000,284000, 21140,18090,15230,11990,8170, 4090, 0,    0),
    (288000,292000, 22780,19450,16590,13370,9450, 5390, 1130, 0),
    (296000,300000, 24420,20810,17950,14750,10730,6690, 2430, 0),
    (300000,304000, 25240,21490,18630,15440,11370,7340, 3080, 0),
    (310000,316000, 27700,23530,20670,17510,13290,9290, 5030, 270),
    (320000,324000, 29340,24890,22030,18890,14570,10590,6330, 1570),
    (330000,336000, 31800,26930,24070,20960,16490,12540,8280, 3520),
    (340000,344000, 33440,28290,25430,22340,17770,13840,9580, 4420),
    (350000,356000, 35900,30330,27470,24410,19690,15790,11530,5770),
    (360000,364000, 37540,31690,28830,25790,20970,17090,12830,6670),
    (370000,380000, 40820,34410,31150,28550,23530,19690,15430,8470),
    (380000,390000, 42460,35770,32510,29930,24810,20990,16730,9370),
    (400000,420000, 47600,40400,37100,34500,29200,25400,21100,13100),
    (420000,440000, 50400,43200,39900,37300,32000,28200,23900,15900),
    (440000,460000, 53200,46000,42700,40100,34800,31000,26700,18700),
    (460000,480000, 56000,48800,45500,42900,37600,33800,29500,21500),
    (500000,550000, 61000,53800,50600,48000,42700,38900,34600,26600),
    (550000,600000, 70600,63400,60200,57600,52300,48500,44200,36200),
    (600000,650000, 77000,69800,66600,64000,58700,54900,50600,42600),
    (650000,700000, 86600,79400,76200,73600,68300,64500,60200,52200),
    (700000,750000, 93000,85800,82600,80000,74700,70900,66600,58600),
    (750000,800000, 105800,98600,95400,92800,87500,83700,79400,71400),
    (800000,850000, 112000,106800,103800,101200,95900,92100,87800,79800),
    (850000,900000, 120000,115800,112800,110200,104900,101100,96800,88800),
    (900000,950000, 130000,127800,124800,122200,116900,113100,108800,100800),
    (950000,1000000,140000,139800,136800,134200,128900,125100,120800,112800),
    (1000000,2000000,200000,199800,196800,194200,188900,185100,180800,172800),
    (2000000,9999999,450000,449800,446800,444200,438900,435100,430800,422800),
]

# ═══════════════════════════════════════════════════════════════
# 4. Accident Insurance Rates (労災保険料率)
# ═══════════════════════════════════════════════════════════════
ACCIDENT_INSURANCE = [
    ("055", "派遣業（一般）",           "Dispatch General",          0.0035, AF),
    ("056", "派遣業（製造）",           "Dispatch Manufacturing",    0.0045, AF),
    ("057", "派遣業（建設）",           "Dispatch Construction",     0.0060, AF),
    ("001", "情報通信業",               "IT/Communications",        0.0020, AF),
    ("002", "一般事務・金融保険",       "Office/Finance",           0.0015, AF),
    ("010", "製造業（金属）",           "Metal Mfg",                0.0060, AF),
    ("011", "製造業（電気電子）",       "Electronics Mfg",          0.0030, AF),
    ("020", "建設業（建築）",           "Construction Building",    0.0090, AF),
    ("021", "建設業（土木）",           "Construction Civil",       0.0120, AF),
    ("030", "運輸業（陸運）",           "Transport Land",           0.0065, AF),
    ("040", "小売業",                   "Retail",                   0.0030, AF),
    ("041", "飲食業",                   "Food Service",             0.0035, AF),
    ("050", "医療・福祉（病院）",       "Healthcare Hospital",      0.0030, AF),
    ("051", "医療・福祉（介護）",       "Nursing Care",             0.0035, AF),
    ("053", "コンサルティング",         "Consulting",               0.0020, AF),
    ("054", "人材紹介業",               "Staffing Agency",          0.0025, AF),
]


def seed():
    """Insert FY2026 seed data into all parameter tables."""
    print("=" * 60)
    print("TACAI Pay JP — FY2026 (令和8年度) Seed Data")
    print("=" * 60)

    # ── 0. Rate Type Labels ──
    print("\n[0/5] Rate Type Labels...")
    execute("DELETE FROM pay_jp_rate_type_labels")
    rtl_sql = (
        "INSERT INTO pay_jp_rate_type_labels (rate_type, labels, display_order) "
        "VALUES(%s, %s, %s) "
        "ON CONFLICT (rate_type) DO UPDATE SET labels = EXCLUDED.labels, display_order = EXCLUDED.display_order"
    )
    n = execute_many(rtl_sql, RATE_TYPE_LABELS)
    print(f"  → {n} rows inserted")
    verify("pay_jp_rate_type_labels")

    # ── 1. Social Insurance ──
    print("\n[1/4] Social Insurance Rates...")
    execute("DELETE FROM pay_jp_social_insurance_rates")
    si_sql = (
        "INSERT INTO pay_jp_social_insurance_rates"
        "(rate_type, prefecture, employee_rate, employer_rate, applicable_from, is_current, notes) "
        "VALUES(%s, %s, %s, %s, %s, true, %s)"
    )
    n = execute_many(si_sql, SOCIAL_INSURANCE)
    print(f"  → {n} rows inserted")
    verify("pay_jp_social_insurance_rates")

    # ── 2. Remuneration Grades ──
    print("\n[2/4] Standard Remuneration Grades...")
    execute("DELETE FROM pay_jp_standard_remuneration_grades")
    rg_sql = (
        "INSERT INTO pay_jp_standard_remuneration_grades"
        "(grade_type, grade_number, min_monthly_amount, max_monthly_amount, standard_monthly_amount, applicable_from, is_current) "
        "VALUES(%s, %s, %s, %s, %s, %s, true)"
    )
    health_params = [("health_insurance", *r, AF) for r in HEALTH_GRADES]
    pension_params = [("pension_insurance", *r, AF) for r in PENSION_GRADES]
    n = execute_many(rg_sql, health_params + pension_params)
    print(f"  → {n} rows inserted ({len(HEALTH_GRADES)} health + {len(PENSION_GRADES)} pension)")
    verify("pay_jp_standard_remuneration_grades")

    # ── 3. Tax Brackets ──
    print("\n[3/4] Withholding Tax Brackets...")
    execute("DELETE FROM pay_jp_withholding_tax_brackets")
    tx_sql = (
        "INSERT INTO pay_jp_withholding_tax_brackets"
        "(table_type, min_salary, max_salary, tax_dep_0, tax_dep_1, tax_dep_2, tax_dep_3, "
        " tax_dep_4, tax_dep_5, tax_dep_6, tax_dep_7, applicable_from, is_current) "
        "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)"
    )
    n = execute_many(tx_sql, [("monthly", *r, AF) for r in MONTHLY_TAX])
    print(f"  → {n} rows inserted ({len(MONTHLY_TAX)} monthly brackets)")
    verify("pay_jp_withholding_tax_brackets")

    # ── 4. Accident Insurance ──
    print("\n[4/4] Accident Insurance Rates...")
    execute("DELETE FROM pay_jp_accident_insurance_rates")
    ai_sql = (
        "INSERT INTO pay_jp_accident_insurance_rates"
        "(industry_code, industry_name_ja, industry_name_en, rate, applicable_from, is_current) "
        "VALUES(%s, %s, %s, %s, %s, true)"
    )
    n = execute_many(ai_sql, ACCIDENT_INSURANCE)
    print(f"  → {n} rows inserted")
    verify("pay_jp_accident_insurance_rates")

    # ── 5. Payroll Item Definitions ──
    print("\n[5/5] Payroll Item Definitions...")
    execute("DELETE FROM pay_jp_payroll_item_definitions")
    ITEMS_SQL = (
        "INSERT INTO pay_jp_payroll_item_definitions"
        "(item_id, code, category, sub_category, labels, taxable, social_insurance_base, employment_insurance_base, payslip_visible, requires_reason, display_order, status, editable_in_master) "
        "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    ITEMS = [
        ("item-base_pay", "base_pay", "earning", "base",
         '{"en":"Basic salary","ja":"基本給","zh":"基本工资"}', True, True, True, True, False, 10, "active", True),
        ("item-hourly_pay", "hourly_pay", "earning", "base",
         '{"en":"Hourly pay","ja":"時給","zh":"时薪"}', True, True, True, True, False, 11, "active", True),
        ("item-daily_pay", "daily_pay", "earning", "base",
         '{"en":"Daily pay","ja":"日給","zh":"日薪"}', True, True, True, True, False, 12, "active", True),
        ("item-transportation", "transportation", "earning", "allowance",
         '{"en":"Transportation allowance","ja":"通勤手当","zh":"交通补贴"}', False, False, True, True, False, 13, "active", True),
        ("item-site_allowance", "site_allowance", "earning", "allowance",
         '{"en":"Dispatch site allowance","ja":"派遣先手当","zh":"派遣现场津贴"}', True, True, True, True, False, 14, "active", True),
        ("item-overtime", "overtime", "earning", "overtime",
         '{"en":"Overtime pay","ja":"時間外手当","zh":"加班费"}', True, True, True, True, False, 15, "active", True),
        ("item-late_night", "late_night", "earning", "overtime",
         '{"en":"Late-night premium","ja":"深夜手当","zh":"深夜津贴"}', True, True, True, True, False, 16, "active", True),
        ("item-holiday", "holiday", "earning", "overtime",
         '{"en":"Holiday work pay","ja":"休日手当","zh":"休日出勤费"}', True, True, True, True, False, 17, "active", True),
        ("item-bonus", "bonus", "earning", "manual",
         '{"en":"Bonus/commission","ja":"賞与・歩合","zh":"奖金/佣金"}', True, True, True, True, True, 18, "active", True),
        ("item-absence", "absence", "deduction", "attendance",
         '{"en":"Absence deduction","ja":"欠勤控除","zh":"缺勤扣款"}', False, False, False, True, False, 19, "active", True),
        ("item-advance", "advance", "deduction", "manual",
         '{"en":"Advance repayment","ja":"前払控除","zh":"预支扣款"}', False, False, False, True, True, 20, "active", True),
        ("item-health_insurance", "health_insurance", "deduction", "statutory",
         '{"en":"Health insurance","ja":"健康保険","zh":"健康保险"}', False, False, False, True, False, 21, "active", False),
        ("item-pension", "pension", "deduction", "statutory",
         '{"en":"Welfare pension","ja":"厚生年金","zh":"厚生年金"}', False, False, False, True, False, 22, "active", False),
        ("item-employment_insurance", "employment_insurance", "deduction", "statutory",
         '{"en":"Employment insurance","ja":"雇用保険","zh":"雇用保险"}', False, False, False, True, False, 23, "active", False),
        ("item-income_tax", "income_tax", "deduction", "statutory",
         '{"en":"Income tax","ja":"所得税","zh":"所得税"}', False, False, False, True, False, 24, "active", False),
        ("item-resident_tax", "resident_tax", "deduction", "statutory",
         '{"en":"Resident tax","ja":"住民税","zh":"住民税"}', False, False, False, True, False, 25, "active", False),
        ("item-employer_health_insurance", "employer_health_insurance", "employer_cost", "statutory",
         '{"en":"Employer health insurance","ja":"会社負担健康保険","zh":"公司负担健康保险"}', False, False, False, True, False, 26, "active", False),
        ("item-employer_pension", "employer_pension", "employer_cost", "statutory",
         '{"en":"Employer pension","ja":"会社負担厚生年金","zh":"公司负担厚生年金"}', False, False, False, True, False, 27, "active", False),
        ("item-employer_employment_insurance", "employer_employment_insurance", "employer_cost", "statutory",
         '{"en":"Employer employment insurance","ja":"会社負担雇用保険","zh":"公司负担雇用保险"}', False, False, False, True, False, 28, "active", False),
    ]
    n = execute_many(ITEMS_SQL, ITEMS)
    print(f"  → {n} rows inserted")
    verify("pay_jp_payroll_item_definitions")

    print("\n" + "=" * 60)
    print("✅ Seed complete — FY2026 (Reiwa 8) data loaded.")
    print("=" * 60)


def verify(table: str):
    rows = fetch_all(f"SELECT COUNT(*) as c FROM {table}")
    print(f"     Verified: {table} = {rows[0]['c']} rows")


if __name__ == "__main__":
    seed()
