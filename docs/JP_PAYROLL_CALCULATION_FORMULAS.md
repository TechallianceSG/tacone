# 日本薪资计算方式说明 / JP Payroll Calculation Formulas

> **版本**: 2.0
> **更新日**: 2026-07-02
> **对应代码**: `backend/services/payroll/jp/app.py` → `_calc_salary_by_type()`
>
> **v2.0 变更**:
> - 移除 `standard_work_days`：当月工作日统一从批次的 `working_days_in_month` 取，不再存储于薪资主数据
> - `actual_hours` 缺省值从硬编码 `160` 改为取员工主数据的 `standard_monthly_hours`
> - `monthly_hour` 中 `actual_hours` fallback 改为 `std_hours`（同源）
> - 明确所有参数的数据来源（主数据/批次/月度记录）

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
| `social_insurance_eligible` | `social_insurance_eligible` | 社会保险加入 |
| `employment_insurance_eligible` | `employment_insurance_eligible` | 雇用保险加入 |
| `age_at_fiscal_year_start` | `age_at_fiscal_year_start` | 年度初年龄（介护保险判定） |
| `monthly_resident_tax` | `monthly_resident_tax` | 每月住民税额 |
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
3. 计算社会保险料（健康保険・厚生年金・介護保険・雇用保険）
4. 计算税金（所得税・住民税）
5. 加算其他控除 → 得到控除合计 (deduction_total)
6. 计算差额支给额 (net_pay) = gross_pay - deduction_total
7. 计算公司负担额 (employer_cost_total) = gross_pay × 15%（概算）
```

### 手当一览（Allowances）

以下手当直接从 `pay_jp_salary_master` 的对应字段取值，全额加算到 gross_pay：

| 手当名 | 字段 | 日文 |
|--------|------|------|
| 通勤手当 | `commute_allowance` | 通勤手当 |
| 住宅手当 | `housing_allowance` | 住宅手当 |
| 家族手当 | `family_allowance` | 家族手当 |
| 役职手当 | `position_allowance` | 役職手当 |
| 固定手当 | `fixed_allowance` | 固定手当 |
| 交通费 | `transport_allowance` | 交通費 |
| 电话手当 | `phone_allowance` | 電話手当 |
| 业绩赏与 | `performance_bonus` | 業績賞与 |
| PJ赏与 | `project_bonus` | プロジェクト賞与 |
| 固定残业代 | `fixed_overtime_amount` | 固定残業代 |

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

```
基本给 = 300,000 × (22 - 2) / 22 = 300,000 × 20/22 = 272,727円
gross = 272,727 + 15,000 = 287,727円

控除（概算）:
  健康保険 5.0%:   287,727 × 0.05   = 14,386
  厚生年金 9.15%:  287,727 × 0.0915 = 26,327
  雇用保険 0.6%:   287,727 × 0.006  =  1,726
  所得税 5.0%:     287,727 × 0.05   = 14,386
  控除合计:                          56,825

net_pay = 287,727 - 56,825 = 230,902円
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

```
基本给 = 1,500 × 140 = 210,000円
gross = 210,000 + 10,000 = 220,000円

控除（概算）:
  健康保険 5.0%:   220,000 × 0.05   = 11,000
  厚生年金 9.15%:  220,000 × 0.0915 = 20,130
  雇用保険 0.6%:   220,000 × 0.006  =  1,320
  所得税 5.0%:     220,000 × 0.05   = 11,000
  控除合计:                          43,450

net_pay = 220,000 - 43,450 = 176,550円
```

### 劳动法相关
- 最低賃金法 — 时给必须高于各都道府县的最低工资标准
- 労基法第37条 — 时间外劳动割増（25%以上）

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

> 日给: ¥12,000 / 实际工作: 18日

```
基本给 = 12,000 × 18 = 216,000円
gross = 216,000円

控除（概算）:
  健康保険 5.0%:   216,000 × 0.05   = 10,800
  厚生年金 9.15%:  216,000 × 0.0915 = 19,764
  雇用保険 0.6%:   216,000 × 0.006  =  1,296
  所得税 5.0%:     216,000 × 0.05   = 10,800
  控除合计:                          42,660

net_pay = 216,000 - 42,660 = 173,340円
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
gross = base + Σ(其他手当)
```

> `fixed_overtime_amount` 不重复计入 allowances（避免双重加算）

### 计算示例

> 基本给: ¥350,000 / 固定残业代: ¥80,000（みなし45h分） / 当月工作日: 22日 / 欠勤: 0日 / 通勤手当: ¥20,000

```
基本给 = 350,000 × 22/22 = 350,000円
base = 350,000 + 80,000 = 430,000円  ← 以此为控除基准
gross = 430,000 + 20,000 = 450,000円

控除（概算）:
  健康保険 5.0%:   450,000 × 0.05   = 22,500
  厚生年金 9.15%:  450,000 × 0.0915 = 41,175
  雇用保険 0.6%:   450,000 × 0.006  =  2,700
  所得税 5.0%:     450,000 × 0.05   = 22,500
  控除合计:                          88,875

net_pay = 450,000 - 88,875 = 361,125円
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

### 劳动法相关
- 労基法第37条：时间外劳动割増率
  - 法定时间外（1日8h/周40h超）: 25%以上
  - 深夜劳动（22:00-5:00）: 追加25%
  - 法定休日劳动: 35%以上
- **当前限制**: 残业费率由 `overtime_hourly_rate` 字段直接指定，不自动计算割増率

---

## 社会保险与税金计算

### 社会保险料（当前采用简化费率）

| 保险种类 | 员工负担率 | 条件 | 日文 |
|----------|-----------|------|------|
| 健康保险 | 5.0% | `social_insurance_eligible = true` | 健康保険 |
| 厚生年金 | 9.15% | `social_insurance_eligible = true` | 厚生年金 |
| 介护保险 | 0.9% | `social_insurance_eligible = true` AND 年龄 ≥ 40 | 介護保険 |
| 雇用保险 | 0.6% | `employment_insurance_eligible = true` | 雇用保険 |

### 税金

| 税种 | 计算方式 | 日文 |
|------|----------|------|
| 所得税 | gross_pay × 5.0%（简化） | 所得税 |
| 住民税 | 从 `monthly_resident_tax` 字段直接取值（前年度课税） | 住民税 |

### 公司负担（Employer Cost）

```
employer_cost_total = gross_pay × 15%（概算近似值）
```

**注意**: 当前阶段采用简化费率。正式版本应使用 `pay_jp_social_insurance_rates`、`pay_jp_standard_remuneration_grades`、`pay_jp_withholding_tax_brackets` 参数表中的实际数据。

---

## 代码位置索引

| 功能 | 文件 | 函数/行号 |
|------|------|-----------|
| 薪资计算主逻辑 | `backend/services/payroll/jp/app.py` | `_calc_salary_by_type()` (line 923) |
| 批次计算 | `backend/services/payroll/jp/app.py` | `_calculate_batch()` |
| 单条重新计算 | `backend/services/payroll/jp/app.py` | `_recalculate_single_record()` |
| 计算预览 | `backend/services/payroll/jp/app.py` | `_calc_preview()` |
| 项目定义 | `frontend/src/modules/payroll/jp/ItemDefinitions.vue` | 工资项目定义页面 |
| 参数管理 | `frontend/src/modules/payroll/jp/PayrollParameters.vue` | 社会保险费率等参数 |
| 工资主数据 | `frontend/src/modules/payroll/jp/JpEmployees.vue` | 员工工资设定 |
| 批次明细 | `frontend/src/modules/payroll/jp/JpPayrollBatchDetail.vue` | 计算/编辑/定稿/回退 |
| 参数种子数据 | `backend/services/payroll/jp/seed_data.py` | FY2026 料率数据 |
| 社保费率表 | `database/migrations/004_payroll_jp_parameters.sql` | `pay_jp_social_insurance_rates` |
| 标准报酬等级 | `database/migrations/004_payroll_jp_parameters.sql` | `pay_jp_standard_remuneration_grades` |
| 源泉徴収税額表 | `database/migrations/004_payroll_jp_parameters.sql` | `pay_jp_withholding_tax_brackets` |

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
