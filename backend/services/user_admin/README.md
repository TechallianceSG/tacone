# TACAI User Admin

用户管理和认证服务。所有业务模块的认证、授权、角色管理、权限控制的唯一来源。

## 启动

```bash
cd backend/services/user_admin
python3 app.py --host 127.0.0.1 --port 3001
```

| 环境 | 端口 |
|------|------|
| DEV | 3001 |
| STG | 4001 |
| PRD | 6001 |

## 健康检查

```bash
curl -s http://127.0.0.1:3001/health
```

## 初始账号

```
Email: admin@tacai.local
```

首次登录后请修改密码。

## 主要 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/session` | 验证当前会话 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/auth/change-password` | 修改密码 |
| GET | `/api/users` | 用户列表（分页+搜索） |
| GET | `/api/users/{id}` | 用户详情 |
| POST | `/api/users` | 创建用户 |
| POST | `/api/users/{id}` | 更新用户 |
| POST | `/api/users/{id}/deactivate` | 停用用户 |
| GET | `/api/public/entities` | 公开实体列表（登录页用） |

## 内置角色

| 角色 | 说明 |
|------|------|
| system_admin | 系统管理员，拥有所有权限 |
| hr_manager | HR 经理 |
| finance | 财务 |
| manager | 管理者 |
| employee | 普通员工 |

## 安全

- 密码使用 PBKDF2-SHA256 哈希（120,000 次迭代）
- Session 超时：480 分钟
- 登录失败锁定：5 次后锁定
- 所有敏感操作记录审计日志

## 依赖

- `backend/shared/db_utils.py` — PostgreSQL 访问
- `backend/shared/config.py` — 端口配置
- `backend/shared/api_utils.py` — API 响应工具
- `backend/shared/cors_middleware.py` — CORS 中间件
