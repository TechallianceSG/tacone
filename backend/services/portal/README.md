# TACAI Portal

统一入口服务，为所有 TACAI 业务模块提供导航和认证入口。

## 启动

```bash
cd backend/services/portal
python3 app.py --host 127.0.0.1 --port 3000
```

| 环境 | 端口 |
|------|------|
| DEV | 3000 |
| STG | 4000 |
| PRD | 6000 |

## 健康检查

```bash
curl -s http://127.0.0.1:3000/health
```

## 认证

Portal 不持有用户数据。认证通过 `user_admin` 服务的 `tacai_session_id` cookie 验证。登录流程：

```
Portal → redirect to User_admin /login?next=...
       → User_admin 验证身份，设置 cookie
       → redirect back to Portal /dashboard
```

## API

| 端点 | 说明 |
|------|------|
| `GET /api/portal/modules` | 获取模块列表（权限过滤） |
| `GET /api/portal/health` | 健康检查 |

## 依赖

- `user_admin` — 认证和权限
- `backend/shared/db_utils.py` — PostgreSQL 访问
- `backend/shared/config.py` — 端口配置
