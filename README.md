# TACAI Project

TACAI 是一套面向人力资源/薪资/招聘业务的企业级管理系统，采用前后端分离架构。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.9+ / FastAPI + uvicorn（Monolith 架构）|
| 数据库 | PostgreSQL（通过 `psycopg2`） |
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia |
| 构建 | Vite 5 |
| 多语言 | vue-i18n 9（日/中/英三语） |

## 目录结构

```
tacai-project/
├── backend/                         # 后端 FastAPI Monolith
│   ├── app.py                       #   入口（单进程，端口 8000）
│   ├── dependencies.py              #   认证/权限依赖注入
│   ├── start.sh                     #   后端启动脚本
│   ├── shared/                      #   共享库 (db_utils, logger)
│   ├── modules/                     #   业务模块（原 9 个独立服务已合并）
│   │   ├── auth/                    #     用户管理 & 认证
│   │   ├── masterdata/              #     主数据管理
│   │   ├── employees/               #     员工管理
│   │   ├── datadict/                #     数据字典
│   │   ├── messaging/               #     消息中心
│   │   ├── payroll_jp/              #     日本薪资
│   │   ├── payroll_sg/              #     新加坡薪资
│   │   └── invoice/                 #     发票管理
│   └── services/                    #   [归档] 原独立服务
├── frontend/                        # 前端 Vue 3 SPA
├── docs/                            # 项目文档
├── .env.dev / .env.stg / .env.prd   # 环境配置
└── start_tacai_lan.sh               # 一键管理脚本（前后端）
```

> 完整目录说明见 [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md)

## 快速开始

### 1. 环境准备

```bash
# PostgreSQL 必须运行
brew services start postgresql@16   # macOS

# Python 依赖
pip3 install fastapi uvicorn psycopg2-binary pydantic python-multipart python-dotenv

# 前端依赖
cd frontend && npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env.dev
# 编辑 .env.dev，确认 DB_HOST / DB_NAME / DB_USER / DB_PASS 正确
```

### 3. 启动服务

**前后端分开启动（推荐开发时使用）：**

```bash
# 后端（终端 1）
cd backend && bash start.sh          # dev 环境，端口 8000
# 或 bash start.sh stg / bash start.sh prd

# 前端（终端 2）
cd frontend && npm start             # Vite 热加载，端口 5173
```

**一键启动：**

```bash
bash start_tacai_lan.sh start dev    # 同时启动后端 + 前端
bash start_tacai_lan.sh stop         # 停止全部
bash start_tacai_lan.sh status       # 查看状态
```

### 4. 访问

| 服务 | URL |
|------|-----|
| 前端 SPA | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |

### 5. 健康检查

```bash
curl http://localhost:8000/health
```

## 当前模块状态

| 模块 | 前端 | 后端 | 端口 |
|------|------|------|------|
| 仪表盘 | ✅ Dashboard | ✅ portal | 3000 |
| 员工管理 | ✅ EmployeeList/Detail/Form | ✅ employee_admin | 8004 |
| 用户管理 | ✅ UserList/Detail/Form | ✅ user_admin | 3001 |
| 主数据管理 | ✅ Entity/Dept/Team | ✅ masterdata | 8007 |
| 数据字典 | ✅ DataDictionaryList | ✅ datadict | 8005 |
| 消息中心 | ✅ Workflow | ✅ messaging | 8012 |
| 日本薪资 | ✅ Payroll JP | ✅ payroll/jp | 8013 |
| 发票管理 | ✅ Invoice | ✅ invoice | 8019 |

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

共享服务（8004~8019）所有环境端口固定，详见 [CLAUDE.md](CLAUDE.md)。
