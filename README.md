# TACAI Project

TACAI 是一套面向人力资源/薪资/招聘业务的企业级管理系统，采用前后端分离架构。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.9+ 标准库 (`http.server` + `ThreadingHTTPServer`) |
| 数据库 | PostgreSQL（通过 `psycopg2`） |
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia |
| 构建 | Vite 5 |
| 多语言 | vue-i18n 9（日/中/英三语） |

## 目录结构

```
tacai-project/
├── backend/                         # 后端
│   ├── shared/                      #   共享库 (db_utils, api_utils, config, cors)
│   └── services/                    #   业务服务
│       ├── user_admin/              #     用户管理 & 认证 (port 3001)
│       ├── portal/                  #     统一入口 (port 3000)
│       ├── masterdata/              #     主数据管理 (port 8007)
│       └── messaging/               #     消息中心 (port 8012)
├── frontend/                        # 前端 Vue 3 SPA
├── database/                        # 数据库迁移脚本
├── docs/                            # 项目文档
│   ├── ARCHITECTURE.md              #   架构说明
│   ├── DIRECTORY_STRUCTURE.md       #   目录结构说明
│   └── DEVELOPMENT_STANDARDS.md     #   开发规范
├── deployment/                      # 部署配置
├── .env.dev / .env.stg / .env.prd   # 环境配置
└── start_tacai_lan.sh               # 一键启动脚本
```

> 完整目录说明见 [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md)

## 快速开始

### 1. 环境准备

```bash
# PostgreSQL 必须运行
brew services start postgresql@16   # macOS

# 前端依赖
cd frontend && npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env.dev
# 编辑 .env.dev，确认 DB_HOST / DB_NAME / DB_USER / DB_PASS 正确
```

### 3. 启动服务

```bash
# 一键启动所有服务
bash start_tacai_lan.sh start dev

# 或手动启动核心服务
cd backend/services/user_admin && python3 app.py --port 3001 &
cd backend/services/portal && python3 app.py --port 3000 &
cd backend/services/masterdata && python3 app.py --port 8007 &

# 前端开发服务器
cd frontend && npm run dev
```

### 4. 访问

| 服务 | URL |
|------|-----|
| 前端 SPA | http://localhost:5173 |
| Portal | http://localhost:3000 |
| User_admin API | http://localhost:3001 |

### 5. 健康检查

```bash
curl http://localhost:3001/health
curl http://localhost:3000/health
curl http://localhost:8007/health
```

## 当前模块状态

| 模块 | 前端 | 后端 | 端口 |
|------|------|------|------|
| 仪表盘 | ✅ Dashboard | ✅ portal | 3000 |
| 员工管理 | ✅ EmployeeList/Detail/Form | ✅ employee_admin | 8004 |
| 用户管理 | ✅ UserList/Detail/Form | ✅ user_admin | 3001 |
| 主数据管理 | — | ✅ masterdata | 8007 |
| 消息中心 | — | ✅ messaging | 8012 |
| 工时管理 | 🔲 规划中 | 🔲 | 8002 |
| 费用报销 | 🔲 规划中 | 🔲 | 8003 |
| 薪资计算 | 🔲 规划中 | 🔲 | 8016 |
| 员工自助 | 🔲 规划中 | 🔲 | 8018 |

## 开发文档

- [目录结构说明](docs/DIRECTORY_STRUCTURE.md) — 完整目录树和命名规范
- [开发规范](docs/DEVELOPMENT_STANDARDS.md) — 前后端开发标准、API 规范、数据库规范
- [架构说明](docs/ARCHITECTURE.md) — 系统架构设计
- [安全策略](SECURITY.md) — 安全和隐私策略

## 环境端口约定

| 环境 | 配置文件 | Portal | User_admin |
|------|---------|--------|-----------|
| DEV | `.env.dev` | 3000 | 3001 |
| STG | `.env.stg` | 4000 | 4001 |
| PRD | `.env.prd` | 6000 | 6001 |

共享服务（masterdata:8007、messaging:8012）所有环境端口固定。
