# TACAI Project — Architecture & Module Reference

> Updated: 2026-07-03
>
> **注意**: 本文档部分内容引用旧项目结构（TACAI-Core），待全面重写。
> 当前端口、服务、路径以 [CLAUDE.md](../CLAUDE.md) 和 [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) 为准。
>
> **Shared Config:** [backend/shared/config.py](../backend/shared/config.py) — single source of truth for all port definitions.
>
> **📖 Specialized Docs:**
> - [Session & Authentication Architecture](SESSION_AUTH_ARCHITECTURE.md) — auth flow, caching, circuit breaker, anti-patterns
> - [Session Auth Root Cause Analysis](SESSION_AUTH_ROOT_CAUSE_ANALYSIS.md) — why the initial design had these flaws

---

## 1. 启动方式 / Startup

### 1.1 一键启动（推荐）

```bash
cd /Users/wangchen/Desktop/TACAI/tacai-project

# DEV 环境（Portal :3000, Auth :3001, DB: tacai_dev）
bash start_tacai_lan.sh start dev

# STG 环境（Portal :4000, Auth :4001, DB: tacai_stg）
bash start_tacai_lan.sh start stg

# PRD 环境（Portal :6000, Auth :6001, DB: tacai_prd）
bash start_tacai_lan.sh start prd

# 三环境同时启动
bash start_tacai_lan.sh start all

# 查看状态
bash start_tacai_lan.sh status

# 停止
bash start_tacai_lan.sh stop dev
```

### 1.2 启动 Vue 3 前端开发服务器

```bash
cd frontend
nvm use v20.19.5          # 需要 Node ≥18
npm install                # 首次或依赖变更后

# DEV 环境（默认，连接 Portal:3000 + Auth:3001）
npm run dev                # 或 npx vite --host 0.0.0.0

# STG 环境（连接 Portal:4000 + Auth:4001）
npm run dev:stg            # 或 npx vite --mode staging --host 0.0.0.0

# PRD 环境（连接 Portal:6000 + Auth:6001）
npm run dev:prd            # 或 npx vite --mode production --host 0.0.0.0
```

> **环境切换原理:** Vite 自动加载 `.env.development` / `.env.staging` / `.env.production`，`vite.config.ts` 读取 `VITE_PORTAL_PORT` 和 `VITE_AUTH_PORT` 来动态设置代理目标。

### 1.3 完整启动流程（DEV 环境）

```bash
# 1. 启动所有后端服务
cd /Users/wangchen/Desktop/TACAI/tacai-project
bash start_tacai_lan.sh start dev

# 2. 启动 Vue 3 前端（另一个终端）
cd /Users/wangchen/Desktop/TACAI/tacai-project/frontend
nvm use v20.19.5
npm run dev
```

---

## 2. 两个登录入口 / Two Login Entry Points

### 2.1 Vue 3 SPA 登录（新）

| 项目 | 说明 |
|------|------|
| URL | `http://localhost:5173/login` |
| 技术栈 | Vue 3 + TypeScript + Pinia + Vue Router + Vue I18n + Axios |
| 登录方式 | JSON API: `POST /api/auth/login` |
| 登录后 | 自动跳转至原始 Portal Dashboard |

```
用户打开 :5173/login → Vue 3 登录表单
    → POST /api/auth/login {email, password, entity_code}
    → Set-Cookie: tacai_session_id
    → window.location → :3000/dashboard（原始 Portal）
```

**核心文件：**

| 文件 | 行数 | 功能 |
|------|------|------|
| [frontend/src/modules/auth/Login.vue](frontend/src/modules/auth/Login.vue) | 296 | 登录表单组件（法人选择、邮箱、密码、语言切换） |
| [frontend/src/stores/auth.ts](frontend/src/stores/auth.ts) | 87 | Pinia 认证状态管理（login/logout/init） |
| [frontend/src/stores/i18n.ts](frontend/src/stores/i18n.ts) | 37 | 语言偏好管理（ja/zh/en，localStorage 持久化） |
| [frontend/src/api/client.ts](frontend/src/api/client.ts) | 132 | Axios HTTP 客户端（拦截器、withCredentials） |
| [frontend/src/router/index.ts](frontend/src/router/index.ts) | 30 | Vue Router（仅 /login 路由，其余跳转 Portal） |
| [frontend/src/main.ts](frontend/src/main.ts) | 68 | 应用入口（i18n 初始化、路由守卫） |
| [frontend/src/App.vue](frontend/src/App.vue) | 14 | 根组件（RouterView） |
| [frontend/src/types/index.ts](frontend/src/types/index.ts) | 72 | TypeScript 类型定义 |
| [frontend/vite.config.ts](frontend/vite.config.ts) | 87 | Vite 配置 + API 代理到后端 |
| [frontend/index.html](frontend/index.html) | 12 | HTML 入口 |
| [frontend/package.json](frontend/package.json) | 26 | 依赖定义 |
| [frontend/tsconfig.json](frontend/tsconfig.json) | 21 | TypeScript 配置 |

**i18n 语言文件：**

| 文件 | 用途 |
|------|------|
| [frontend/src/i18n/ja.json](frontend/src/i18n/ja.json) | 日本語（1523 条目） |
| [frontend/src/i18n/zh.json](frontend/src/i18n/zh.json) | 简体中文（1380 条目） |
| [frontend/src/i18n/en.json](frontend/src/i18n/en.json) | English（1522 条目） |

**样式文件：**

| 文件 | 用途 |
|------|------|
| [frontend/src/styles/variables.css](frontend/src/styles/variables.css) | CSS 变量（颜色、圆角、阴影） |
| [frontend/src/styles/base.css](frontend/src/styles/base.css) | 全局基础样式 |

### 2.2 后端 API 服务

| 项目 | 说明 |
|------|------|
| URL | `http://localhost:8000` (DEV) |
| 技术栈 | FastAPI (Uvicorn) — 单进程 monolith |
| 认证方式 | Session Cookie → `dependencies.get_current_user` |
| API 文档 | `http://localhost:8000/docs` (Swagger UI) |

```
用户打开 :3000 → Portal 检查 session
    → 无 session: 重定向到 :3001/login（User_admin HTML 登录页）
    → 有 session: 直接显示 Dashboard
```

**核心文件：**

| 文件 | 行数 | 功能 |
|------|------|------|
| [TACAI-Core/tacai-portal/backend/app.py](TACAI-Core/tacai-portal/backend/app.py) | 991 | Portal 主服务（路由、HTML 渲染、模块加载） |
| [TACAI-Core/tacai-portal/frontend/app.css](TACAI-Core/tacai-portal/frontend/app.css) | 161 | Portal 样式表 |

**Portal 关键函数：**

| 函数 | 行号 | 功能 |
|------|------|------|
| `render_login()` | 621 | 渲染登录页 HTML（引导用户跳转 User_admin） |
| `render_dashboard()` | 655 | 渲染仪表盘 HTML（侧边栏 + 模块卡片 + 用户 Chip） |
| `render_module_placeholder()` | 718 | 渲染模块占位页 |
| `user_admin_login_url()` | 377 | 生成跳转 User_admin 登录的 URL |
| `user_admin_logout_url()` | 385 | 生成跳转 User_admin 登出的 URL |
| `visible_modules_for()` | 437 | 按用户权限过滤可见模块 |
| `validate_user_admin_session()` | 582 | 向 User_admin 验证 session_id |
| `current_user()` | 837 | 从 Cookie 提取当前用户 |
| `load_modules()` | 412 | 加载模块配置（modules.json 或默认值） |

---

## 3. User_admin — 认证 & 用户管理核心

| 项目 | 说明 |
|------|------|
| URL | `http://localhost:3001`（DEV） |
| 文件 | [TACAI-Core/User_admin/backend/app.py](TACAI-Core/User_admin/backend/app.py)（2847 行） |
| 数据库 | `TACAI-Core/User_admin/database/`（7 个 JSON 文件 + PostgreSQL 可选） |

### 3.1 认证相关 API（供 Vue 3 SPA 使用）

| 端点 | 方法 | 行号 | 功能 |
|------|------|------|------|
| `/api/auth/login` | POST | `handle_api_login()` L2665 | JSON 登录（Vue 3 使用） |
| `/api/auth/logout` | POST | `handle_api_logout()` L2707 | JSON 登出 |
| `/api/auth/session` | GET | L1571 | 获取当前会话信息 |
| `/api/auth/me` | GET | L1573 | 获取当前用户信息 |
| `/api/validate-session` | POST | `handle_api_validate_session()` | 验证 session_id |
| `/api/public/entities` | GET | L1555 | 获取活跃法人列表（无需认证） |

### 3.2 传统 HTML 页面（服务端渲染）

| 端点 | 行号 | 功能 |
|------|------|------|
| `/` `/login` | `send_login()` L1704 | 登录页（HTML form） |
| `/dashboard` | `send_dashboard()` | 仪表盘 |
| `/users` | `send_users()` | 用户列表 |
| `/roles` | `send_roles()` | 角色管理 |
| `/audit-logs` | `send_audit_logs()` | 审计日志 |
| `/login-sessions` | `send_login_sessions()` | 登录会话监控 |
| `/change-password` | `send_change_password()` | 修改密码 |

### 3.3 核心数据模型

| 数据文件 | 内容 |
|------|------|
| `database/users.json` | 用户主数据 |
| `database/roles.json` | 角色定义（6 个角色） |
| `database/permissions.json` | 权限定义（87 个权限） |
| `database/user_role_mapping.json` | 用户↔角色映射 |
| `database/role_permission_mapping.json` | 角色↔权限映射 |
| `database/user_entity_mapping.json` | 用户↔法人映射 |
| `database/user_sessions.json` | 登录会话记录 |
| `database/user_audit_logs.json` | 审计日志 |

### 3.4 角色定义

| 角色 Key | 角色名 | 权限数 |
|------|------|------|
| `system_admin` | System Admin | 全部 |
| `hr_manager` | HR Manager | 60+ |
| `finance` | Finance | 28+ |
| `manager` | Manager | 13+ |
| `employee` | Employee | 9+ |
| `remote_consultant` | Remote Consultant | 10+ |

---

## 4. CORS 中间件（共享）

| 文件 | 行数 | 功能 |
|------|------|------|
| [TACAI-Core/cors_middleware.py](TACAI-Core/cors_middleware.py) | 62 | 为所有 Python 后端提供 CORS 支持 |

**使用方式**（`backend/app.py` 中统一配置）：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Cookie", "Accept", "Accept-Language"],
)
```

---

## 5. 数据库工具（共享）

| 文件 | 行数 | 功能 |
|------|------|------|
| [TACAI-Core/db_utils.py](TACAI-Core/db_utils.py) | 444 | PostgreSQL ↔ JSON 双模式数据访问层 |

---

## 6. 业务模块地图

### 6.1 Portal — 统一入口

| 属性 | 值 |
|------|-----|
| DEV 端口 | `3000` |
| STG 端口 | `4000` |
| PRD 端口 | `6000` |
| 代码 | [TACAI-Core/tacai-portal/backend/app.py](TACAI-Core/tacai-portal/backend/app.py) |
| 样式 | [TACAI-Core/tacai-portal/frontend/app.css](TACAI-Core/tacai-portal/frontend/app.css) |

### 6.2 User_admin — 认证 & 用户管理

| 属性 | 值 |
|------|-----|
| DEV 端口 | `3001` |
| STG 端口 | `4001` |
| PRD 端口 | `6001` |
| 代码 | [TACAI-Core/User_admin/backend/app.py](TACAI-Core/User_admin/backend/app.py) |

### 6.3 MasterData — 组织主数据

| 属性 | 值 |
|------|-----|
| 端口 | `8007` |
| 代码 | [TACAI-Core/masterdata/backend/app.py](TACAI-Core/masterdata/backend/app.py)（4356 行） |
| 数据 | Entity / Department / Team 三层组织架构 |

### 6.4 TACAI Msg Center — 消息中心

| 属性 | 值 |
|------|-----|
| 端口 | `8012` |
| 代码 | [TACAI-Core/tacaimsg/backend/app.py](TACAI-Core/tacaimsg/backend/app.py)（2358 行） |
| 工作流 | [TACAI-Core/tacaimsg/backend/workflow.py](TACAI-Core/tacaimsg/backend/workflow.py) |

### 6.5 Timesheet — 工时管理

| 属性 | 值 |
|------|-----|
| 端口 | `8002` |
| 代码 | [TAC-timesheet/backend/app.py](TAC-timesheet/backend/app.py)（5550 行） |

### 6.6 Reimbursement — 费用报销

| 属性 | 值 |
|------|-----|
| 端口 | `8003` |
| 代码 | [TAC-reimbursement/backend/app.py](TAC-reimbursement/backend/app.py)（3322 行） |

### 6.7 Employee Admin — 员工管理

| 属性 | 值 |
|------|-----|
| 端口 | `8004` |
| 代码 | [TAC-employeeadmin/backend/app.py](TAC-employeeadmin/backend/app.py)（8444 行） |

### 6.8 TACAI Pay SG — 新加坡薪资

| 属性 | 值 |
|------|-----|
| 端口 | `8016` |
| 代码 | [TACAIPAY/tacaipaysg/backend/app.py](TACAIPAY/tacaipaysg/backend/app.py)（8472 行） |

### 6.9 Self-Service — 员工自助（请假）

| 属性 | 值 |
|------|-----|
| 端口 | `8018` |
| 代码 | [TacSelfService/TacSelfVacation/backend/app.py](TacSelfService/TacSelfVacation/backend/app.py)（1872 行） |

### 6.10 InterviewReady — AI 面试工具

| 属性 | 值 |
|------|-----|
| 端口 | `8000` |
| 代码 | [InterviewReady/app/web.py](InterviewReady/app/web.py) |

---

## 7. 端口分配总览

```
环境       Portal    Auth      DB
─────────────────────────────────
DEV        3000      3001      tacai_dev
STG        4000      4001      tacai_stg
PRD        6000      6001      tacai_prd

共享服务   端口
─────────────────
InterviewReady   8000
Payroll Legacy   8001 (backup/TACAI-PRJ, 暂不可用)
Timesheet        8002
Expense          8003
Employee Admin   8004
MasterData       8007
TACAI Msg        8012
TACAI Pay SG     8016
Self-Service     8018
Gateway          8010

前端开发服务器
─────────────────
Vue 3 SPA        5173
Vite Preview     4173
```

---

## 8. 认证流程图

```
┌─────────────────────────────────────────────────────────────────┐
│  Vue 3 登录（新）                                                │
│                                                                  │
│  :5173/login                                                     │
│    │                                                             │
│    ▼ POST /api/auth/login (proxy → :3001)                       │
│  User_admin.handle_api_login()                                   │
│    │ 验证 email + password + entity_code                         │
│    │ Set-Cookie: tacai_session_id                                │
│    ▼                                                             │
│  window.location → :3000/dashboard                               │
│    │                                                             │
│    ▼ GET /dashboard (Cookie: tacai_session_id)                   │
│  Portal.render_dashboard()                                       │
│    │ validate_user_admin_session() → POST :3001/api/validate-...│
│    │ visible_modules_for(user) → 按权限过滤                       │
│    ▼                                                             │
│  完整 HTML Dashboard（侧边栏 + 4 模块卡片 + 用户信息）            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  原始登录（旧，完全保留）                                         │
│                                                                  │
│  :3000 → 无 session → 重定向到 :3001/login                       │
│    │                                                             │
│    ▼ GET :3001/login                                             │
│  User_admin.send_login() → HTML 登录表单                         │
│    │                                                             │
│    ▼ POST :3001/login (form data)                                │
│  User_admin.handle_login()                                       │
│    │ Set-Cookie: tacai_session_id                                │
│    │ 302 → :3000/dashboard                                       │
│    ▼                                                             │
│  Portal.render_dashboard() → HTML Dashboard                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. 环境配置文件

| 文件 | 用途 |
|------|------|
| [.env.dev](.env.dev) | DEV 环境（PORT=3000, AUTH_PORT=3001, DB=tacai_dev） |
| [.env.stg](.env.stg) | STG 环境（PORT=4000, AUTH_PORT=4001, DB=tacai_stg） |
| [.env.prd](.env.prd) | PRD 环境（PORT=6000, AUTH_PORT=6001, DB=tacai_prd） |

每个 `.env` 文件格式：

```bash
NODE_ENV=dev|stg|prd
PORT=3000              # Portal 端口
AUTH_PORT=3001         # User_admin 端口
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tacai_dev
DB_USER=tacai_user
DB_PASS=...
TACAI_DB_ENABLED=true  # false 则回退到 JSON 文件存储
```

---

## 10. 常用命令速查

```bash
# 启动
bash start_tacai_lan.sh start dev      # DEV 环境
bash start_tacai_lan.sh start all      # 全部三环境

# 停止
bash start_tacai_lan.sh stop dev
bash start_tacai_lan.sh stop all

# 重启
bash start_tacai_lan.sh restart dev

# 状态
bash start_tacai_lan.sh status

# Vue 3 前端
cd frontend && npx vite --host 0.0.0.0

# 单模块启动（手动）
cd TACAI-Core/User_admin && python3 backend/app.py --host 0.0.0.0 --port 3001
cd TACAI-Core/tacai-portal && python3 backend/app.py --host 0.0.0.0 --port 3000

# 健康检查
curl http://127.0.0.1:3000/health
curl http://127.0.0.1:3001/health

# 语法检查
python3 -m py_compile TACAI-Core/tacai-portal/backend/app.py
python3 -m py_compile TACAI-Core/User_admin/backend/app.py

# Vue 构建
cd frontend && npm run build
```

---

## 11. 共享端口配置 (tacai_config.py)

**文件:** [TACAI-Core/tacai_config.py](TACAI-Core/tacai_config.py)

所有后端模块的端口配置唯一真相源（Single Source of Truth）。

### 使用方式

```python
# 在 backend/ 中:
from config import (
    ALLOWED_PORTS,        # 所有有效本地端口集合
    ALLOWED_HOSTS,         # 所有允许的主机名集合
    get_portal_port,       # 当前环境的 Portal 端口
    get_auth_port,         # 当前环境的 User_admin 端口
)
```

### 环境感知

| 变量 | 来源 | DEV 值 | STG 值 | PRD 值 |
|------|------|--------|--------|--------|
| `PORTAL_PORT` | `PORT` env var | 3000 | 4000 | 6000 |
| `AUTH_PORT` | `AUTH_PORT` env var | 3001 | 4001 | 6001 |

`start_tacai_lan.sh` 从 `.env.{dev,stg,prd}` 读取并导出这些环境变量。

### 前端环境切换

| 命令 | Env 文件 | 连接后端 |
|------|----------|---------|
| `npm run dev` | `.env.development` | DEV (3000/3001) |
| `npm run dev:stg` | `.env.staging` | STG (4000/4001) |
| `npm run dev:prd` | `.env.production` | PRD (6000/6001) |

Vite proxy 自动从 `.env.*` 文件读取端口，无需手动修改 `vite.config.ts`。```
