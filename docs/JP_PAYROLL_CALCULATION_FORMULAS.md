# 日本薪资计算方式说明 / JP Payroll Calculation Formulas

> **版本**: 4.0
> **更新日**: 2026-07-03
> **对应代码**: `backend/services/payroll/jp/app.py` → `_calc_salary_by_type()` + `_lookup_insurance_rate()` + `_lookup_standard_remuneration()` + `_lookup_withholding_tax()`
>
> **v4.0 变更**:
> - 🐛 **Bug Fix**: `monthly_fixed_ot` 中 `fixed_overtime_amount` 重复加算问题修复。该手当已在 base 中包含，不再在 allowances 中重复计入
> - 🇯🇵 **合规**: 健康保険・厚生年金の計算基準を gross_pay → 標準報酬月額（`pay_jp_standard_remuneration_grades` 等級表）に変更
> - 🇯🇵 **合规**: 所得税を固定 5% → 源泉徴収税額表（`pay_jp_withholding_tax_brackets`）による累進課税 + 扶養人数調整に変更
> - 🏢 **雇主成本**: 労災保険料（業種別料率）+ 児童手当拠出金（0.36%）を雇主負担に追加
> - 📝 **文档修正**: バッチ再計算は手動編集を**上書きする**（仕様通り）。docstring の誤記を修正
>
> **v3.0 变更**:
> - 健康保险费率从 5.0% 写死 → 按员工 `prefecture_code` 查 `pay_jp_social_insurance_rates` 表
> - 介护保险费率 0.9% → 0.81%（2026年度实际），新增年龄上限 64岁
> - 雇用保险费率 0.6% → 0.5%（2026年度实际）
> - 公司负担从 15% 概算 → 按各项雇主费率实际加总
> - `pay_jp_social_insurance_rates` 表驱动：各种保险费率统一从参数表动态查询
>
> **v2.0 变更**:
> - 移除 `standard_work_days`：当月工作日统一从批次的 `working_days_in_month` 取
> - `actual_hours` 缺省值从硬编码 `160` 改为取员工主数据的 `standard_monthly_hours`
> - `monthly_hour` 中 `actual_hours` fallback 改为 `std_hours`（同源）

---

## 目录

1. [数据来源总览](#数据来源总览)
2. [共通处理](#共通处理)
3. [月給制 (monthly)](#1-月給制-monthly)
4. [時給制 (hourly)](#2-時給制-hourly)
5. [日給制 (daily)](#3-日給制-daily)
6. [月給＋固定残業制 (monthly_fixed_ot)](#4-月給固定残業制-monthly_fixed_ot)
7. [月給＋時給併用制 (monthly_hour)](#5-月給時給併用制-monthly_hour)
8. [社会保险与税金计算](#社会保险与税金计算)
9. [代码位置索引](#代码位置索引)

---

## 数据来源总览

### 员工主数据 (`pay_jp_salary_master`)

| 参数 | 字段 | 说明 |
|------|------|------|
| `salary_type` | `salary_type` | 薪资计算方式 |
| `basic_salary` | `basic_salary` | 基本给（月额） |
| `hourly_rate` | `hourly_rate` | 时给单价 |
| `daily_rate` | `daily_rate` | 日给单价 |
| `standard_work_hours` | `standard_work_hours` | 日标准工作时间（例: 8h） |
| `standard_monthly_hours` | `standard_monthly_hours` | 月标准工作时间（例: 160h），`monthly_hour` 类型的残业分界线 |
| `overtime_hourly_rate` | `overtime_hourly_rate` | 残业时给单价 |
| `fixed_overtime_amount` | `fixed_overtime_amount` | 固定残业代（月额） |
| `social_insurance_eligible` | `social_insurance_eligible` | 社会保险加入资格 |
| `employment_insurance_eligible` | `employment_insurance_eligible` | 雇用保险加入资格 |
| `age_at_fiscal_year_start` | `age_at_fiscal_year_start` | 年度初年龄（介护保险判定：40～64岁） |
| `dependents_count` | `dependents_count` | 扶养人数（源泉徴収税額計算用、0～7） |
| `prefecture_code` | `prefecture_code` | 都道府県コード（健康保険料率の都道府県別判定用） |
| `industry_code` | `industry_code` | 業種コード（労災保険料率の業種別判定用） |
| `monthly_resident_tax` | `monthly_resident_tax` | 每月住民税额（特別徴収） |
| `recurring_deductions` | `recurring_deductions` | 其他固定控除 |
| 各项手当 | `commute/housing/family/position/fixed/transport/phone/performance_bonus/project_bonus` | 各手当金额 |

### 批次设定 (`pay_jp_payroll_batches`)

| 参数 | 字段 | 说明 |
|------|------|------|
| `working_days_in_month` | `working_days_in_month` | **当月工作日数**（默认22），月给/固定残业计算的关键参数 |

### 月度记录 (`pay_jp_monthly_salary_records`)

| 参数 | 字段 | 说明 |
|------|------|------|
| `actual_work_hours` | `actual_work_hours` | 当月实际出勤时间 |
| `actual_work_days` | `actual_work_days` | 当月实际出勤天数 |
| `absence_days` | `absence_days` | 欠勤日数 |

### Fallback 规则

| 变量 | 取值优先级 |
|------|-----------|
| `actual_hours` | 月度记录的 `actual_work_hours` → 员工主数据的 `standard_monthly_hours` → 160 |
| `actual_days` | 月度记录的 `actual_work_days` → 批次的 `working_days_in_month` → 22 |
| `working_days` | 批次的 `working_days_in_month` → 22 |
| `std_hours` | 员工主数据的 `standard_monthly_hours` → 160 |

---

## 共通处理

所有计算方式共通的处理流程：

```
1. 根据 salary_type 计算基本给 (base_pay)
2. 加算各种手当 → 得到支给总额 (gross_pay)
   ※ monthly_fixed_ot 的 fixed_overtime_amount 已在 base_pay 中包含，不重复加算
3. 计算标准报酬月额（標準報酬月額）— 等级表查询
   - 参考报酬 = gross_pay - 通勤手当（通勤手当は標準報酬の算定基礎から除外）
   - 健康保険用 → 查 pay_jp_standard_remuneration_grades (grade_type='health_insurance')
   - 厚生年金用 → 查 pay_jp_standard_remuneration_grades (grade_type='pension_insurance')
4. 计算社会保险料（费率从 pay_jp_social_insurance_rates 动态查询）
   - 健康保険・厚生年金 → 标准报酬月额 × 费率（等级表上限/下限自动适用）
   - 介護保険 → 健康保険标准报酬月额 × 费率（40-64歳のみ）
   - 雇用保険 → gross_pay × 费率（实际工资基准，不使用标准报酬）
5. 计算税金
   - 所得税 → 源泉徴収税額表（课税所得 = gross_pay - 社保合计, 扶养人数 0～7）
     表不可用时 fallback 为 gross_pay × 5%
   - 住民税 → monthly_resident_tax 字段直接取值
6. 加算其他控除 → 得到控除合计 (deduction_total)
7. 计算差额支给额 (net_pay) = gross_pay - deduction_total
8. 计算公司负担额 (employer_cost_total)
   = 健康保険(雇主) + 厚生年金(雇主) + 介護保険(雇主) + 雇用保険(雇主)
   + 児童手当拠出金(雇主) + 労災保険(雇主)
```

### 手当一览（Allowances）

以下手当直接从 `pay_jp_salary_master` 的对应字段取值，全额加算到 gross_pay：

| 手当名 | 字段 | 日文 | 备注 |
|--------|------|------|------|
| 通勤手当 | `commute_allowance` | 通勤手当 | 社保标准报酬计算时**除外** |
| 住宅手当 | `housing_allowance` | 住宅手当 | |
| 家族手当 | `family_allowance` | 家族手当 | |
| 役职手当 | `position_allowance` | 役職手当 | |
| 固定手当 | `fixed_allowance` | 固定手当 | |
| 交通费 | `transport_allowance` | 交通費 | |
| 电话手当 | `phone_allowance` | 電話手当 | |
| 业绩赏与 | `performance_bonus` | 業績賞与 | |
| PJ赏与 | `project_bonus` | プロジェクト賞与 | |
| 固定残业代 | `fixed_overtime_amount` | 固定残業代 | ⚠️ monthly_fixed_ot 时已在 base 中包含，**不重复计入** allowances |

---

## 1. 月給制 (monthly)

### 适用场景
正社員。月额固定给与 + 欠勤控除。

### 数据来源

| 变量 | 来源 |
|------|------|
| `basic` | `basic_salary`（薪资主数据） |
| `working_days` | `working_days_in_month`（批次）→ fallback 22 |
| `absence_days` | `absence_days`（月度记录）→ fallback 0 |

### 计算公式

```
基本给 = basic_salary × (working_days - absence_days) / working_days
支给总额 = 基本给 + Σ(各手当)
```

### 计算示例

> 基本给: ¥300,000 / 当月工作日: 22日 / 欠勤: 2日 / 通勤手当: ¥15,000
> 東京都 (prefecture_code=13) / 年龄: 35岁 / 扶养人数: 0

```
基本给 = 300,000 × (22 - 2) / 22 = 272,727円
gross_pay = 272,727 + 15,000 = 287,727円

—— 社保・税金（详见 §社会保险与税金计算）——

参考报酬 = 287,727 - 15,000(通勤) = 272,727円
健康保険標準報酬 = 280,000円（等级21: 270,000～290,000）
厚生年金標準報酬 = 280,000円（等级19: 270,000～290,000）

健康保険 = 280,000 × 4.925%(東京) = 13,790円
厚生年金 = 280,000 × 9.15%           = 25,620円
雇用保険 = 287,727 × 0.50%           =  1,439円
社保合计                               40,849円

课税所得 = 287,727 - 40,849 = 246,878円
所得税   = 源泉徴収税額表(246,878, 扶養0) ≒ 15,550円
住民税   = monthly_resident_tax（员工主数据）
─────────────────────────────────────────
控除合计  ≒ 56,400円 + 住民税

net_pay  ≒ 287,727 - 56,400 - 住民税
```

### 劳动法相关
- ノーワーク・ノーペイの原則（労基法第24条）
- 欠勤控除は就業規則に定める必要あり

---

## 2. 時給制 (hourly)

### 适用场景
パート・アルバイト。按实际工作时间支给。

### 数据来源

| 变量 | 来源 |
|------|------|
| `rate` | `hourly_rate`（薪资主数据） |
| `actual_hours` | `actual_work_hours`（月度记录）→ fallback `standard_monthly_hours`（薪资主数据）→ 160 |

### 计算公式

```
基本给 = hourly_rate × actual_hours
支给总额 = 基本给 + Σ(各手当)
```

### 计算示例

> 时给: ¥1,500 / 实际工时: 140h / 交通费: ¥10,000
> 東京都 / 年龄: 25岁 / 扶养人数: 0

```
基本给 = 1,500 × 140 = 210,000円
gross_pay = 210,000 + 10,000 = 220,000円

—— 社保・税金（详见 §社会保险与税金计算）——

参考报酬 = 220,000 - 10,000(交通费) = 210,000円
健康保険標準報酬 = 220,000円（等级18: 210,000～230,000）
厚生年金標準報酬 = 220,000円（等级16: 210,000～230,000）

健康保険 = 220,000 × 4.925%(東京) = 10,835円
厚生年金 = 220,000 × 9.15%           = 20,130円
雇用保険 = 220,000 × 0.50%           =  1,100円
社保合计                               32,065円

课税所得 = 220,000 - 32,065 = 187,935円
所得税   = 源泉徴収税額表(187,935, 扶養0) ≒ 6,050円
─────────────────────────────────────────
控除合计  ≒ 38,100円 + 住民税

net_pay  ≒ 220,000 - 38,100 - 住民税
```

### 劳动法相关
- 最低賃金法 — 时给必须高于各都道府县的最低工资标准
- 労基法第37条 — 时间外劳动割増（25%以上）
- **当前限制**: 系统不对 hourly 类型自动计算加班割増。工时超过法定标准（1日8h/周40h）的割増需手动处理

---

## 3. 日給制 (daily)

### 适用场景
日雇い・短期・单日派遣。

### 数据来源

| 变量 | 来源 |
|------|------|
| `rate` | `daily_rate`（薪资主数据） |
| `actual_days` | `actual_work_days`（月度记录）→ fallback 1 |

### 计算公式

```
基本给 = daily_rate × actual_days
支给总额 = 基本给 + Σ(各手当)
```

### 计算示例

> 日给: ¥12,000 / 实际工作: 18日 / 无手当
> 東京都 / 年龄: 30岁 / 扶养人数: 0

```
基本给 = 12,000 × 18 = 216,000円
gross_pay = 216,000円（无手当）

—— 社保・税金（详见 §社会保险与税金计算）——

参考报酬 = 216,000 - 0 = 216,000円
健康保険標準報酬 = 220,000円（等级18: 210,000～230,000）
厚生年金標準報酬 = 220,000円（等级16: 210,000～230,000）

健康保険 = 220,000 × 4.925%(東京) = 10,835円
厚生年金 = 220,000 × 9.15%           = 20,130円
雇用保険 = 216,000 × 0.50%           =  1,080円
社保合计                               32,045円

课税所得 = 216,000 - 32,045 = 183,955円
所得税   = 源泉徴収税額表(183,955, 扶養0) ≒ 5,780円
─────────────────────────────────────────
控除合计  ≒ 37,800円 + 住民税

net_pay  ≒ 216,000 - 37,800 - 住民税
```

### 劳动法相关
- 日雇労働者の健康保険（日雇特例被保険者制度）
- 日雇派遣は原則禁止（労働者派遣法）

---

## 4. 月給＋固定残業制 (monthly_fixed_ot)

### 适用场景
裁量労働制、みなし残業制。适用于管理职或采用固定加班费的职位。

### 数据来源

| 变量 | 来源 |
|------|------|
| `basic` | `basic_salary`（薪资主数据） |
| `fixed_ot` | `fixed_overtime_amount`（薪资主数据） |
| `working_days` | `working_days_in_month`（批次）→ fallback 22 |
| `absence_days` | `absence_days`（月度记录）→ fallback 0 |

### 计算公式

```
基本给 = basic_salary × (working_days - absence_days) / working_days
base = 基本给 + fixed_overtime_amount  ← 控除计算基准
gross = base + Σ(其他手当)             ← fixed_overtime_amount 不重复计入 allowances
```

> ⚠️ **v4.0 修复**: `fixed_overtime_amount` 已在 base 中包含，不再在 allowances 中重复加算。

### 计算示例

> 基本给: ¥350,000 / 固定残业代: ¥80,000（みなし45h分）
> 当月工作日: 22日 / 欠勤: 0日 / 通勤手当: ¥20,000
> 東京都 / 年龄: 45岁 / 扶养人数: 1

```
基本给 = 350,000 × 22/22 = 350,000円
base = 350,000 + 80,000 = 430,000円  ← 控除计算基准
gross_pay = 430,000 + 20,000 = 450,000円
            ↑ 通勤手当のみ加算。fixed_overtime_amount(80,000) は allowances に含めない

—— 社保・税金（详见 §社会保险与税金计算）——

参考报酬 = 450,000 - 20,000(通勤) = 430,000円
健康保険標準報酬 = 440,000円（等级28: 425,000～455,000）
厚生年金標準報酬 = 440,000円（等级24: 425,000～455,000）

健康保険 = 440,000 × 4.925%(東京) = 21,670円
厚生年金 = 440,000 × 9.15%           = 40,260円
介護保険 = 440,000 × 0.81%           =  3,564円  (40-64歳)
雇用保険 = 450,000 × 0.50%           =  2,250円
社保合计                               67,744円

课税所得 = 450,000 - 67,744 = 382,256円
所得税   = 源泉徴収税額表(382,256, 扶養1) ≒ 35,770円
─────────────────────────────────────────
控除合计  ≒ 103,500円 + 住民税

net_pay  ≒ 450,000 - 103,500 - 住民税
```

### 劳动法相关
- 裁量労働制适用时需「労使協定」缔结
- 固定残业代（みなし残業代）需包含割増賃金
- **当前限制**: 系统不校验实际残业时间是否超过みなし范围

---

## 5. 月給＋時給併用制 (monthly_hour)

### 适用场景
派遣社員等。基本给＋时给的混合计算。有固定基本给，同时按实际工时计算时给部分，标准时间超过部分按残业时给计算。

### 数据来源

| 变量 | 来源 |
|------|------|
| `basic` | `basic_salary`（薪资主数据） |
| `hourly_rate` | `hourly_rate`（薪资主数据） |
| `overtime_rate` | `overtime_hourly_rate`（薪资主数据） |
| `std_hours` | `standard_monthly_hours`（薪资主数据）→ fallback 160 |
| `actual_hours` | `actual_work_hours`（月度记录）→ fallback `std_hours` |

### 计算公式

```
std_hours  = standard_monthly_hours（月标准工时，残业分界线）
actual_hrs = actual_work_hours or std_hours

if actual_hrs ≤ std_hours:
    monthly_part  = basic × actual_hrs / std_hours    ← 基本给按比例
    hourly_part   = hourly_rate × actual_hrs
    overtime_pay  = 0
else:
    monthly_part  = basic                              ← 基本给全额
    hourly_part   = hourly_rate × std_hours
    ot_hours      = actual_hrs - std_hours
    overtime_pay  = overtime_rate × ot_hours

base = monthly_part + hourly_part + overtime_pay
gross = base + Σ(各手当)
```

### 计算例 1：未达标准时间（150h < 160h）

> 基本给: ¥80,000 / 时给: ¥1,000 / 残业时给: ¥1,500
> 月标准工时 (`standard_monthly_hours`): 160h
> 实际工时: 150h

```
monthly_part = 80,000 × 150 / 160 = 75,000円
hourly_part  = 1,000 × 150         = 150,000円
overtime_pay = 0

base = 75,000 + 150,000 + 0 = 225,000円
```

### 计算例 2：超过标准时间（170h > 160h）

> 同上条件 / 实际工时: 170h

```
monthly_part = 80,000                           =  80,000円  (全额)
hourly_part  = 1,000 × 160                      = 160,000円
ot_hours     = 170 - 160                         = 10h
overtime_pay = 1,500 × 10                       =  15,000円

base = 80,000 + 160,000 + 15,000 = 255,000円
```

### 计算例 3：刚好等于标准时间（160h = 160h）

> 同上条件 / 实际工时: 160h

```
monthly_part = 80,000 × 160 / 160 =  80,000円
hourly_part  = 1,000 × 160         = 160,000円
overtime_pay = 0

base = 80,000 + 160,000 + 0 = 240,000円
```

### 验算对比表

| 实际工时 | monthly_part | hourly_part | overtime | **base** |
|----------|-------------|-------------|----------|-----------|
| 120h | 60,000 | 120,000 | 0 | **180,000** |
| 140h | 70,000 | 140,000 | 0 | **210,000** |
| 150h | 75,000 | 150,000 | 0 | **225,000** |
| 160h | 80,000 | 160,000 | 0 | **240,000** |
| 170h | 80,000 | 160,000 | 15,000 | **255,000** |
| 180h | 80,000 | 160,000 | 30,000 | **270,000** |

> base 计算后，社保・税金按 [共通处理](#共通处理) 流程继续计算。

### 劳动法相关
- 労基法第37条：时间外劳动割増率
  - 法定时间外（1日8h/周40h超）: 25%以上
  - 深夜劳动（22:00-5:00）: 追加25%
  - 法定休日劳动: 35%以上
- **当前限制**: 残业费率由 `overtime_hourly_rate` 字段直接指定，不自动计算割増率

---

## 社会保险与税金计算

### 费率来源

> 所有费率统一从 `pay_jp_social_insurance_rates` 参数表动态查询。
> 查询优先级：`prefecture` 精确匹配 → `prefecture IS NULL`（全国默认）→ fallback 0。

### 标准报酬月额（標準報酬月額）— v4.0 新增

健康保険和厚生年金的保费**不**直接按 gross_pay 计算，而是先查 `pay_jp_standard_remuneration_grades` 等级表确定标准报酬月额：

```
参考报酬 = gross_pay - 通勤手当（通勤手当は標準報酬の算定基礎から除外）
健康保険標準報酬 = lookup_grade(ref_remuneration, 'health_insurance')
厚生年金標準報酬 = lookup_grade(ref_remuneration, 'pension_insurance')
```

等级表自动提供最低/最高限额（健康保険: 58,000～1,390,000円、厚生年金: 88,000～650,000円）。
等级表不可用时 fallback 为参考报酬原值。

### 社会保险料（2026年度 令和8年度）

> 以下费率为 FY2026 种子数据的参考值。实际计算时从参数表动态查询。

| 保险种类 | 员工负担 | 雇主负担 | 计算基准 | 条件 | 都道府县差异 |
|----------|---------|---------|----------|------|:--:|
| 厚生年金 | 9.15% | 9.15% | **標準報酬月額** | `social_insurance_eligible = true` | ❌ 全国统一 |
| 健康保险 | 按都道府县 | 按都道府县 | **標準報酬月額** | `social_insurance_eligible = true` | ✅ **不同** |
| 介护保险 | 0.81% | 0.81% | 健康保険標準報酬 | `social_insurance_eligible = true` AND **40 ≤ 年龄 ≤ 64** | ❌ 全国统一 |
| 雇用保险 | 0.50% | 0.85% | 实际 gross_pay | `employment_insurance_eligible = true` | ❌ 全国统一 |
| 児童手当 | — | 0.36% | 健康保険標準報酬 | `social_insurance_eligible = true` | ❌ 全国统一 |
| 労災保険 | — | 業種別 | 实际 gross_pay | 全员（雇主全额负担） | ❌ 全国统一 |

### 健康保险费率（按都道府县 / 2026年度）

| 都道府县 | prefecture_code | 员工负担 | 雇主负担 | 合计 |
|----------|:--:|---------|---------|------|
| 東京 | 13 | **4.925%** | **4.925%** | 9.85% |
| 大阪 | 27 | **5.065%** | **5.065%** | 10.13% |
| 神奈川 | 14 | **5.065%** | **5.065%** | 10.13% |
| 愛知 | 23 | **5.02%** | **5.02%** | 10.04% |
| 全国平均 (fallback) | — | **5.00%** | **5.00%** | 10.00% |

### 労災保険料率（按業種 / 2026年度）

> 员工需在薪资主数据中配置 `industry_code` 才能计算労災保険料。

| 業種 | industry_code | 料率 |
|------|:--:|------|
| 派遣業（一般） | 055 | **0.35%** |
| 情報通信業 | 001 | **0.20%** |
| 一般事務・金融保険 | 002 | **0.15%** |
| 人材紹介業 | 054 | **0.25%** |
| コンサルティング | 053 | **0.20%** |

### 税金

| 税种 | 计算方式 | 说明 |
|------|----------|------|
| 所得税（源泉徴収） | **源泉徴収税額表（月額表）** による累進課税 | v4.0: 课税所得 = gross_pay - 社保合计, 扶養人数 0～7 対応。`pay_jp_withholding_tax_brackets` 表驱动。表不可用时 fallback 为 5% |
| 住民税 | **`monthly_resident_tax`** 字段直接取值 | 地方税、会社が特別徴収。値は給与マスタに保存 |

### 公司负担（Employer Cost）— v4.0 扩展

```
employer_cost = 健康保険(雇主, 按都道府县, 标准报酬基准)
              + 厚生年金(雇主, 9.15%, 标准报酬基准)
              + 介護保険(雇主, 0.81% if 40-64, 标准报酬基准)
              + 雇用保険(雇主, 0.85%, 实际工资基准)
              + 児童手当拠出金(雇主, 0.36%, 标准报酬基准)
              + 労災保険(雇主, 業種別料率, 实际工资基准)
```

> 各项雇主费率从 `pay_jp_social_insurance_rates.employer_rate` 取值。
> 労災保険从 `pay_jp_accident_insurance_rates.rate` 取值（需员工配置 `industry_code`，否则为 0）。

### 综合计算示例（月給＋時給併用、東京、年龄45岁、扶养1人）

> base=255,000円 / 通勤手当=15,000円 / 他手当なし
> 東京都 (prefecture_code=13) / 扶养人数: 1 / industry_code=001(情報通信業)

```
gross_pay = 255,000 + 15,000(通勤) = 270,000円

—— 標準報酬月額 ——
参考报酬 = 270,000 - 15,000(通勤) = 255,000円
健康保険標準報酬 = 260,000円（等级20: 250,000～270,000）
厚生年金標準報酬 = 260,000円（等级17: 250,000～270,000）

—— 员工控除 ——
健康保険 = 260,000 × 4.925%(東京) = 12,801円
厚生年金 = 260,000 × 9.15%           = 23,790円
介護保険 = 260,000 × 0.81%           =  2,106円  (40-64歳)
雇用保険 = 270,000 × 0.50%           =  1,350円
社保合计                               40,047円

课税所得 = 270,000 - 40,047 = 229,953円
所得税   = 源泉徴収税額表(229,953, 扶養1) ≒ 9,130円
住民税   = monthly_resident_tax（员工主数据）
─────────────────────────────────────────
控除合计  ≒ 49,200円 + 住民税

net_pay  ≒ 270,000 - 49,200 - 住民税

—— 雇主负担 ——
健康保険(雇主) = 260,000 × 4.925% = 12,801円
厚生年金(雇主) = 260,000 × 9.15%  = 23,790円
介護保険(雇主) = 260,000 × 0.81%  =  2,106円
雇用保険(雇主) = 270,000 × 0.85%  =  2,295円
児童手当拠出金 = 260,000 × 0.36%  =    936円
労災保険(IT)   = 270,000 × 0.20%  =    540円
──────────────────────────────────────
雇主负担合计                         42,468円
```

---

## 税表边界处理

### 千円未満切捨てと境界値の扱い

源泉徴収税額表の検索では、日本の税法標準に従い以下の処理を行う：

1. **課税所得の千円未満切捨て**：`(int(taxable_income) // 1000) * 1000`
2. **税表区間**：`[min_salary 以上, max_salary 未満)` — 下限 inclusive, 上限 exclusive
3. **境界値**：切捨て後の値が区間の下限値 `min_salary` と一致する場合、当該区間の税額を適用する

### 所得税の地域差について

- **所得税（源泉徴収）**：国税のため、全国統一の税額表（源泉徴収税額表）を使用する
- **住民税**：地方税のため地域別だが、会社は特別徴収義務者として各市町村から通知された額を控除するのみで、システム側で計算する必要はない。`monthly_resident_tax` 字段に通知額を保存する

### 境界値と年末調整

課税所得の切捨て値が区間境界に一致する極稀なケース（例：512,070 → 512,000 が `[509,000, 512,000)` と `[512,000, 515,000)` の境界に位置する）では、標準的な `[以上, 未満)` ルールにより下限値側の区間（=高い方の税額）が選択される。業務データとの間に僅差（例：490円）が生じることがあるが、これは以下の理由により許容される：

1. 月次の源泉徴収は**概算控除**であり、最終的な税額は**年末調整**で精算される
2. 僅少な差額（数百円程度）は年末調整時に自動的に相殺される
3. 社保料率の僅少な地域差・年度更新差による課税所得の変動が主因であり、計算ロジックの誤りではない

### 参照資料

| 資料 | 内容 |
|------|------|
| `docs/01-07.pdf` | 令和8年分 源泉徴収税額表 月額表（財務省告示） |
| `docs/R8_13tokyo.pdf` | 令和8年度 東京支部 健康保険・厚生年金保険 保険料額表 |

---

## 代码位置索引

| 功能 | 文件 | 函数 |
|------|------|------|
| 薪资计算主逻辑 | `backend/services/payroll/jp/app.py` | `_calc_salary_by_type()` |
| 标准报酬月额查询 | `backend/services/payroll/jp/app.py` | `_lookup_standard_remuneration()` |
| 源泉徴収税额查询 | `backend/services/payroll/jp/app.py` | `_lookup_withholding_tax()` |
| 保险费率查询 | `backend/services/payroll/jp/app.py` | `_lookup_insurance_rate()` |
| 批次计算 | `backend/services/payroll/jp/app.py` | `_calculate_batch()` |
| 单条重新计算 | `backend/services/payroll/jp/app.py` | `_recalculate_single_record()` |
| 计算预览 | `backend/services/payroll/jp/app.py` | `_calc_preview()` |
| 项目定义 | `frontend/src/modules/payroll/jp/ItemDefinitions.vue` | 工资项目定义页面 |
| 参数管理 | `frontend/src/modules/payroll/jp/PayrollParameters.vue` | 社会保险费率等参数 |
| 工资主数据 | `frontend/src/modules/payroll/jp/JpEmployees.vue` | 员工工资设定 |
| 批次明细 | `frontend/src/modules/payroll/jp/JpPayrollBatchDetail.vue` | 计算/编辑/定稿/回退 |
| 参数种子数据 | `backend/services/payroll/jp/seed_data.py` | FY2026 料率数据 |
| 社保费率表 | `pay_jp_social_insurance_rates` | 各保险种别的员工/雇主费率 |
| 标准报酬等级 | `pay_jp_standard_remuneration_grades` | 健康保険・厚生年金等级表 |
| 源泉徴収税額表 | `pay_jp_withholding_tax_brackets` | 月額・日額・賞与用税額表 |
| 労災保険料率表 | `pay_jp_accident_insurance_rates` | 業種別労災保険料率 |

---

## 参考法规

- 労働基準法（昭和22年法律第49号）
- 最低賃金法（昭和34年法律第137号）
- 健康保険法（大正11年法律第70号）
- 厚生年金保険法（昭和29年法律第115号）
- 雇用保険法（昭和49年法律第116号）
- 介護保険法（平成9年法律第123号）
- 所得税法（昭和40年法律第33号）
- 地方税法（昭和25年法律第226号）— 住民税
- 労働者派遣法（昭和60年法律第88号）
