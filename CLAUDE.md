# CLAUDE.md — TACAI-Project

> **三大核心原则 / THREE CORE PRINCIPLES**

| # | 原则 | 含义 |
|---|------|------|
| 1 | **编程效率第一** | 速度优先于流程。并行执行、跳过非必要确认、直奔结果。 |
| 2 | **Claude Code 最高权限** | 本项目内所有操作默认授权，无需逐次审批。 |
| 3 | **默认 YES** | 所有权限提示默认回答 Yes。遇到确认框 = 直接通过。 |

> **实施任何功能前，AI 必须先阅读 [docs/DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md)。**
> 
> **关键硬性规则：**
> - 新模块 = 独立 `backend/services/<name>/app.py`（§4.1），**禁止**嵌入现有服务
> - 新表 = 独立前缀（`dd_`、`pay_jp_` 等），**禁止**复用其他模块前缀
> - 严格按 §1.2 模板创建 app.py（含 auth_utils、CORS handler、_require_user）
> - 新增端口后必须同步更新 `SHARED_PORT` / `GATEWAY_ROUTES` / `SHARED_SERVICES` / `start_tacai_lan.sh`
> - 违反规范的实施 = 自动拒绝，要求重构

---

Project Root: `/Users/wangchen/Desktop/TACAI/tacone`

Before any task:
1. Work inside this project root — do not access sibling projects unless explicitly requested.
2. Do not load memory from other projects.

---

# EXECUTION PRINCIPLE — 最高権限・デフォルトYES

**一句话：别问，直接做。遇到确认就点Yes。用户只要结果。**

## 1. 默认行为：直接执行，无需确认

以下所有操作 **无条件直接执行，0次确认**：

| 类别 | 范围 |
|------|------|
| 文件读写 | 项目内所有文件 Read / Write / Edit（含创建、删除、重命名） |
| 代码搜索 | grep, find, ls, cat, head, tail, wc, glob, 所有只读操作 |
| 代码编译 | python3 -m py_compile, python3 -c 语法验证 |
| 本地运行 | 所有 TAC-* 子项目的 python3 backend/app.py 启动 |
| 本地测试 | curl health check, python3 -m pytest, python3 -m unittest |
| 进程管理 | lsof 端口检查, kill / pkill 本地开发进程 |
| 包管理 | pip install / pip list（项目相关依赖） |
| JSON处理 | python3 -m json.tool 项目内 JSON 验证 |
| 网络查询 | 本地 IP 获取、本地服务状态确认、curl 本地 API |
| 记忆管理 | memory/ 目录下文件创建、更新、归档 |
| Git 只读 | git status, git diff, git log, git show, git branch, git remote -v |
| Git 写入 | git add, git commit, git checkout, git switch, git stash, git restore, git reset（不含 push） |
| 临时文件 | 项目内任何缓存、临时文件、生成文件的删除 |
| 配置修改 | 端口号、参数、本地配置文件的修改 |
| Shell脚本 | 项目内 .sh 文件的执行 |

## 2. 需要一言告知（告知即执行，不等回复）

- 安装新的系统级依赖（pip install 新包）
- 修改端口分配方案
- 创建新的子目录结构

## 3. 唯一需要明确确认的操作

以下操作 **必须事先征得用户同意**：

- `git push` / 远程仓库推送
- 外部服务数据发送（外部 API 调用、文件上传到外部）
- git 历史删除 / force push
- `~/.claude/` 全局配置修改
- 生产环境 / 生产数据库操作
- `sudo` 系统级安装

## 4. 沟通风格

- **执行前**：一句话告知（不是询问），然后立即执行。
  - ✅ `"提取 salary_calc 函数到独立模块..."`
  - ❌ `"Shall I extract the salary_calc function?"`
- **执行中**：并行执行所有独立步骤，不等待。
- **执行后**：简洁报告。成功 → 一句话。失败 → 原因 + 自动修复。

## 5. 错误处理

- 可预见错误（端口占用、文件缺失等）→ **直接修复**，不询问。
- 意外错误 → 先试一个修复方案，失败再报告。
- 同一操作失败 3 次 → 停，报告，不进入死循环。

## 6. Plan Mode 规则

- 非平凡任务（多文件、新功能、架构变更）→ 先用 EnterPlanMode 制定计划。
- 计划批准后 → 全自动执行，不再有任何确认。
- 计划执行中需要微调 → 直接调整继续，事后说明。

## 7. 总结

```
用户发任务 → 计划(如需) → 批准 → 全速执行到底 → 报告结果
中间没有任何 Yes/No 确认。用户不是瓶颈，结果才是。
```

---

## Current workspace state

Monorepo with unified frontend (Vue 3 SPA) and a **FastAPI monolith** backend at `backend/app.py`.

Backend modules (FastAPI routers under `backend/modules/`):
- [backend/modules/auth/](backend/modules/auth/) — User management & authentication
- [backend/modules/masterdata/](backend/modules/masterdata/) — Master data management
- [backend/modules/employees/](backend/modules/employees/) — Employee administration
- [backend/modules/datadict/](backend/modules/datadict/) — Data dictionary
- [backend/modules/payroll_jp/](backend/modules/payroll_jp/) — Japan payroll (prefix: `pay_jp`)
- [backend/modules/payroll_sg/](backend/modules/payroll_sg/) — Singapore payroll (prefix: `pay_sg`)
- [backend/modules/payroll_cn/](backend/modules/payroll_cn/) — China payroll (prefix: `pay_cn`)
- [backend/modules/invoice/](backend/modules/invoice/) — Invoice management
- [backend/modules/messaging/](backend/modules/messaging/) — Message center & workflow

Shared libraries: `backend/shared/` (db_utils, auth_utils, config, cors_middleware)

**Shared payroll item catalog:** `pay_payroll_item_definitions` is ONE cross-country table (keyed by `country_code` = `jp`/`sg`/`cn`) holding the wage-type/工资项目 catalog for all three payroll modules. Each module's `/api/payroll/{cc}/item-definitions` endpoint reads/writes this shared table filtered by `country_code`. Do NOT resurrect the per-country `pay_{jp,sg,cn}_payroll_item_definitions` tables — they are legacy, kept only for rollback. Payroll calculation engines (`service.py`) do NOT read item definitions, so changing this catalog never affects salary calculation. Migration: `database/migrations/008_payroll_shared_item_definitions.sql`.

Frontend: `frontend/` — Vue 3 + Element Plus + TypeScript + Vite

## Commands

### Backend (FastAPI monolith)

```bash
cd backend
python3 app.py --host 127.0.0.1 --port 8000
# or: uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev          # Dev server on :5173
npm run build        # Production build
npx vue-tsc --noEmit # Type check
```

### One-click

```bash
bash start_tacai_lan.sh start dev
bash start_tacai_lan.sh status
bash start_tacai_lan.sh stop
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md) for full details.

### API JSON Format Convention

All API communication between frontend and backend uses **flat dot-notation keys**:

```
✅ "profile.name.display_name": "John"
✅ "employment.entity_id": "ENT-0001"
❌ { profile: { name: { display_name: "John" } } }
❌ { employment: { entity_id: "ENT-0001" } }
```

- **Frontend**: Always send flat keys. Forms with nested data use `flatten()` to convert before sending.
- **Backend**: Convert flat keys to nested storage format via `_unflatten_body()` in the handler (centralized, single responsibility).
- **Rationale**: Flat JSON is simpler to construct, validate, and debug. Nesting exists only at the database level (JSONB columns); the conversion boundary is the backend handler.

## Local port convention

| Service | DEV |
|---------|-----|
| Backend API (FastAPI monolith) | 8000 |
| Frontend (Vite dev server) | 5173 |




# MEMORY MANAGEMENT

The project must maintain a small active context window.
Memory Structure
1. memory/
2. archive/

File Size Policy
Green Zone
0KB - 30KB
Normal operation.
Yellow Zone
30KB - 100KB
Monitor growth and prepare for summarization.
Red Zone
Over 100KB
Archive and compress immediately.
Archive Rules
When any file under `/memory` exceeds 100KB:
Create archive copy.
Generate concise summary.
Replace active memory file with summary.
Never delete archive records.
Archive Naming Convention
1. archive/<module>/<filename>_YYYY_MM.md

Example:
1. archive/project_status/project_status_2026_06.md
2. archive/recruitment/recruitment_2026_06.md
3. archive/payroll/payroll_2026_06.md

Loading Rules
Do not automatically load archive files.
Only load:
CLAUDE.md
memory/project_status.md
related module memory file
Archive files should only be opened when explicitly requested.
Memory Update Rules
After every major task:
Update project_status.md
Update related module memory
Update decisions.md (if architectural decisions were made)
Update changelog.md (if system changes occurred)
Historical Preservation Policy
Never delete historical records.
When summarizing:
Preserve key decisions
Preserve business rules
Preserve architecture decisions
Preserve implementation status
Preserve unresolved issues
Archive files are the source of truth for historical details.


## Startup Loading Priority

On project startup, load files in this order:

1. CLAUDE.md
2. memory/project_status.md
3. memory/current_tasks.md
4. Related module memory

Do not load archive files automatically.




# Audit Rules

All modules must implement audit logging.

Required fields:

- module
- record_id
- action
- user
- timestamp
- before_value
- after_value

Audit logs must never be deleted.

Audit logs are read-only.

Future centralized audit viewer may be added.

When memory exceeds 100KB:
   - archive
   - summarize
   - preserve history

Prefer modular architecture.


# UI / Report Standards

## Row Count Requirement (ALL pages)

Every report page, list page, and data table MUST show a total record count at the bottom of the results. This applies to:
- Browse/list pages (salary master, batches, monthly sheets, etc.)
- Report pages (payroll reports, cost reports, etc.)
- Audit log pages (show "Showing latest X of Y total entries")
- Parameter/config pages
- Any page that displays a list of records

Implementation pattern:
```html
<div class='helper-text' style='margin-top:8px'>{count} record(s) total</div>
```

Place immediately after the `</table></div>` closing tags, inside the card div for tables, or after the data content for non-table lists.

For filtered views, show: "Showing X of Y records (filtered)"

## Entity Display Convention (法人实体代码表示规范)

All modules MUST display legal entity as human-readable labels, never as raw entity_id codes (e.g., "ENT-0002").

### Label standard

| Lang | Label |
|------|-------|
| zh | 法人实体代码 |
| ja | 法人实体コード |
| en | Legal Entity Code |

Do NOT use abbreviated or abstract labels like "法人/公司", "Entity", or "法人/会社" for the entity field.

### Display format

Entity values in tables, dropdowns, and headers must be shown as:

```
{entity_code} - {entity_name} ({country})
```

Example:
- `TASG - Tech Alliance Consultancy Service Pte. Ltd (Singapore)`
- `TANJ - 南京特谙斯企业咨询有限公司 (中国)`
- `TAKK - Tech Alliance株式会社 (Japan)`

### Dropdown requirement

Entity filter/selection MUST use a `<select>` dropdown with human-readable labels, NOT a free-text `<input>`. The dropdown options must be derived from the salary master's distinct entity_id values, resolved against masterdata entities.json for labels.

### Source of truth

`md_entities` table in PostgreSQL (via masterdata service on port 8007) is the authoritative entity master. All modules should resolve entity_id → display label from this source.

### Implementation pattern

```python
def entity_label(entity_id: str, lang: str = "zh") -> str:
    """Return human-readable entity label: code - name (country)."""
    # Load from masterdata entities.json, fallback to raw entity_id
    # Format: {entity_code} - {entity_name} ({country})
```

Filter dropdowns should use exact matching (`==`), not substring matching (`.lower() in`), since the dropdown provides exact entity_id values.

### Affected modules

- `TACAIPAY/tacaipaysg/` — implemented (2026-06-25)
- All future payroll modules (tacaipayjp, tacaipaycn, etc.)
- Any module displaying entity data in tables or filters


# business thinking

Business Focus:
- Recruitment Agency
- RPO
- Haken Business
- Payroll Management
- AI Recruitment Platform

Rules:

1. Follow Japan labor law and haken compliance.
2. Maintain reusable templates.
3. Store important decisions in memory/decisions.md.
4. Store business knowledge in skills/.


Think as:
   - IT Product Expert
   - IT Architecture Expert
   - HR Management Expert
   - Compensation and Benefits Expert
   - UI/UX Expert
   - SAP Product Development Expert
   - Software Architect
   - Recruitment Consultant
   - Business Operations Manager

Development thinking script:
When helping with product design, architecture, coding, testing, or documentation, Claude must evaluate the work from these perspectives:

1. IT Product Expert — clarify user value, MVP scope, workflow completeness, priorities, acceptance criteria, and business impact.
2. IT Architecture Expert — ensure modular architecture, maintainability, data integrity, scalability, security, auditability, and integration readiness.
3. HR Management Expert — consider HR operations, employee lifecycle, approval flows, compliance, permissions, data privacy, and Japan labor/haken requirements.
4. Compensation and Benefits Expert — consider payroll accuracy, salary rules, allowances, deductions, reimbursements, benefits, statutory calculations, and audit trails.
5. UI/UX Expert — keep interfaces simple, consistent, accessible, efficient for operations users, and suitable for Japanese business workflows.
6. SAP Product Development Expert — think in enterprise-grade master data, transaction data, approval status, audit logs, role authorization, configuration tables, and future ERP integration patterns.

Before implementing changes, Claude should briefly check whether the change affects product scope, architecture, HR/payroll compliance, UI/UX, audit logs, or future SAP/ERP integration.


# 数据库开发规范

### 连接方式
- 必须使用环境变量读取数据库配置
- 禁止硬编码任何数据库连接信息
- 三环境配置：.env.dev / .env.stg / .env.prd

### 表命名规范
| 模块 | 前缀 | 示例 |
|------|------|------|
| 员工管理 | emp_ | emp_user, emp_department |
| 考勤 | ts_ | ts_attendance, ts_leave |
| 薪资 | pay_ | pay_salary, pay_payslip |
| 费用报销 | rmb_ | rmb_expense, rmb_approval |
| 客户发票 | inv_ | inv_invoice, inv_customer |
| 文档管理 | doc_ | doc_file, doc_category |
| 主数据 | md_ | md_company, md_department |
| 面试系统 | iv_ | iv_candidate, iv_interview |
| 员工自助 | ss_ | ss_profile, ss_request |

### 字段命名规范
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键，自增 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| deleted_at | TIMESTAMP | 软删除（NULLABLE） |

### 新建表流程
1. 表名必须加模块前缀
2. 字段命名遵循统一规范
3. 先写文档确认，再创建表
4. 必须包含 created_at 和 updated_at
5. 提交时附带 SQL 迁移脚本

### 禁止事项
- 禁止创建无前缀的表名
- 禁止硬编码数据库连接
- 禁止直接操作 PRD 数据库
- 禁止删除已有表

### 示例
```sql
CREATE TABLE inv_invoice (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(50) NOT NULL,
    customer_id INTEGER NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
