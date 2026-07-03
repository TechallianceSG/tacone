# TACAI 项目目录结构说明

> 版本: 2.1  
> 更新日期: 2026-07-03
> 适用范围: `tacone` 全项目

---

## 一、顶层概览

```
tacai-project/
├── backend/                    # 后端服务（Python 标准库）
│   ├── shared/                 #   共享库
│   ├── services/               #   业务服务
│   └── migrations/             #   数据库迁移（规划中）
├── frontend/                   # 前端 SPA（Vue 3 + Element Plus + TypeScript）
├── database/                   # 数据库管理
├── docs/                       # 项目文档
├── deployment/                 # 部署配置
├── .env.dev / .env.stg / .env.prd
├── start_tacai_lan.sh          # 一键启动脚本
└── README.md
```

---

## 二、`backend/` — 后端

### 2.1 `backend/shared/` — 共享库

所有业务服务共用的 Python 模块。通过 `sys.path` 加入搜索路径后直接 import。

| 文件 | 职责 | 被哪些服务依赖 |
|------|------|-------------|
| `config.py` | 端口/环境配置、服务注册（原 `tacai_config.py`） | 全部 |
| `db_utils.py` | PostgreSQL CRUD 操作 | 全部 |
| `api_utils.py` | JSON 响应标准化（`success()`, `error()`, `paginated()`） | user_admin, masterdata（按需引入） |
| `cors_middleware.py` | CORS 跨域中间件 | 全部 |

**导入方式：**
```python
# 每个 service 的 app.py 顶部有固定代码：
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))
from db_utils import load_table, save_table
from config import ALLOWED_PORTS
```

### 2.2 `backend/services/` — 业务服务

每个服务是一个独立目录，包含入口 `app.py`。服务之间通过 HTTP API 调用，不直接 import。

| 目录 | 服务名 | 端口 | 数据库前缀 | 状态 |
|------|--------|------|-----------|------|
| `user_admin/` | 用户管理 & 认证 | 3001 (DEV) / 4001 (STG) / 6001 (PRD) | `ua_` | ✅ |
| `portal/` | 统一入口 Portal | 3000 (DEV) / 4000 (STG) / 6000 (PRD) | `pt_` | ✅ |
| `employee_admin/` | 员工管理 | 8004 | `emp_` | ✅ |
| `datadict/` | 数据字典 | 8005 | `dd_` | ✅ |
| `masterdata/` | 主数据管理 | 8007 | `md_` | ✅ |
| `messaging/` | 消息中心 & 审批流 | 8012 | `msg_` | ✅ |
| `payroll/jp/` | 日本薪资 | 8013 | `pay_jp_` | ✅ |
| `invoice/` | 发票管理 | 8019 | `inv_` | ✅ |

**服务目录标准结构：**
```
service_name/
├── app.py              # 入口（必须）
├── README.md           # 服务说明
├── docs/               # 服务文档
├── i18n/               # 服务级多语言（可选，前端统一 i18n 后可移除）
└── tests/              # 测试（规划中）
```

**启动命令（统一格式）：**
```bash
cd backend/services/<service_name>
python3 app.py --host 127.0.0.1 --port <port>
```

---

## 三、`frontend/` — 前端

Vue 3 + TypeScript + Element Plus SPA，使用 Vite 构建。

### 3.1 源码目录 `src/`

```
src/
├── api/                     # API 调用层
│   └── client.ts            #   Axios 实例 + 所有后端 API 接口定义
├── components/              # 共享 UI 组件（跨模块复用）
├── composables/             # 共享逻辑（Vue composables）
├── layouts/                 # 布局组件
│   └── AppLayout.vue        #   统一顶部导航栏
├── modules/                 # 业务模块（按领域分目录）
│   ├── auth/                #   登录
│   ├── dashboard/           #   仪表盘
│   ├── employees/           #   员工管理
│   ├── users/               #   用户管理
│   ├── timesheet/           #   工时 [规划中]
│   ├── payroll/             #   薪资 [规划中]
│   ├── reimbursement/       #   报销 [规划中]
│   ├── messaging/           #   消息 [规划中]
│   └── self_service/        #   自助 [规划中]
├── router/                  # 路由定义 + 导航守卫
├── stores/                  # Pinia 状态管理
├── i18n/                    # 多语言资源文件
├── types/                   # TypeScript 类型定义
└── styles/                  # 全局样式
```

### 3.2 前后端模块映射

| 前端 `modules/` | 后端 `services/` | API 代理路径 |
|----------------|-----------------|-------------|
| `auth/` | `user_admin/` | `/api/auth` |
| `dashboard/` | `portal/` | `/api/portal` |
| `employees/` | `employee_admin/` | `/api/employees` |
| `users/` | `user_admin/` | `/api/users` |
| `timesheet/` | `timesheet/` | `/api/timesheet` |
| `reimbursement/` | `reimbursement/` | `/api/expense` |
| `payroll/` | `payroll/` | `/api/payroll` |
| `messaging/` | `messaging/` | `/api/messages` |
| `self_service/` | `self_service/` | `/api/selfservice` |

### 3.3 新增模块开发流程

1. 在 `src/modules/<name>/` 创建页面组件
2. 在 `src/router/index.ts` 添加路由
3. 在 `src/api/client.ts` 添加 API 接口
4. 在 `src/i18n/` 三语文件添加翻译 key
5. 在 `vite.config.ts` 添加代理（如需）

---

## 四、`database/` — 数据库

```
database/migrations/           # SQL 迁移脚本（本地参考，不纳入 git 版本控制）
├── 001_payroll_jp_schema.sql      # 日本薪资全部表
└── 002_data_dictionary.sql        # 数据字典表 + 种子数据
```

> 注：迁移脚本仅供新建环境参考。运行时数据源是 PostgreSQL，由各服务通过 `db_utils` 直连。

---

## 五、`docs/` — 文档

| 文件 | 说明 |
|------|------|
| `ARCHITECTURE.md` | 系统架构说明 |
| `DIRECTORY_STRUCTURE.md` | 本文档 |
| `DEVELOPMENT_STANDARDS.md` | 开发规范（含 API/DB/前端规范） |
| `JP_PAYROLL_CALCULATION_FORMULAS.md` | 日本薪资计算公式 |
| `migration_schema.sql` | 统一数据库 Schema 参考 |

---

## 六、命名规范总览

| 层级 | 规范 | 示例 |
|------|------|------|
| 服务目录 | `snake_case` | `user_admin/`, `employee_admin/`, `datadict/` |
| Python 文件 | `snake_case` | `db_utils.py`, `api_utils.py` |
| Vue 组件文件 | `PascalCase` | `EmployeeList.vue`, `DataDictionaryList.vue` |
| 前端模块目录 | `kebab-case` 或 `snake_case` | `employees/`, `datadict/` |
| TypeScript 文件 | `camelCase` | `client.ts`, `auth.ts` |
| 数据库表 | `{prefix}_{name}` | `ua_users`, `emp_employees`, `dd_data_dictionary` |
| 迁移文件 | `{序号}_{描述}.sql` | `001_payroll_jp_schema.sql` |
| 环境文件 | `.env.{env}` | `.env.dev`, `.env.stg`, `.env.prd` |

---

## 七、环境配置

| 环境 | 文件 | 前端端口 | Portal 端口 | Auth 端口 |
|------|------|---------|------------|----------|
| 开发 (DEV) | `.env.dev` | 5173 (Vite) | 3000 | 3001 |
| 预发布 (STG) | `.env.stg` | 4173 (Preview) | 4000 | 4001 |
| 生产 (PRD) | `.env.prd` | 构建产物 | 6000 | 6001 |

所有共享服务（masterdata、messaging 等）端口在所有环境中固定不变。

---

## 八、技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端运行时 | Python 3.9+ | 标准库 `http.server` + `ThreadingHTTPServer` |
| 数据库 | PostgreSQL | 通过 `psycopg2` 访问 |
| 前端框架 | Vue 3 (Composition API) | `<script setup lang="ts">` |
| UI 组件库 | Element Plus 2.x | 统一 UI 风格 |
| 状态管理 | Pinia | 认证状态 + 语言偏好 |
| 多语言 | vue-i18n 9.x | ja / zh / en 三语 |
| 构建工具 | Vite 5.x | 开发代理 + 生产构建 |
| 语言 | TypeScript 5.x | 前端类型安全 |
