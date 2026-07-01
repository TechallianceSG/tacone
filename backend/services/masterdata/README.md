# TACAI Master Data Management

主数据管理服务，所有业务模块的法人实体、部门、团队、客户、供应商等组织主数据的唯一来源。

## 启动

```bash
cd backend/services/masterdata
python3 app.py --host 127.0.0.1 --port 8007
```

端口：8007（所有环境固定）

## 健康检查

```bash
curl -s http://127.0.0.1:8007/health
```

## 管理的主数据

| 类型 | 表名 | 说明 |
|------|------|------|
| 法人实体 | `md_entities` | TASG / TANJ / TAKK 等 |
| 部门 | `md_departments` | 各部门 |
| 团队 | `md_teams` | 各团队 |
| 客户 | `md_customers` | 客户主数据 |
| 供应商 | `md_vendors` | 供应商主数据 |

## API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/entities` | 实体列表 |
| GET | `/api/entities/{id}` | 实体详情 |
| POST | `/api/entities` | 创建实体 |
| GET | `/api/departments` | 部门列表 |
| GET | `/api/departments/{id}` | 部门详情 |
| GET | `/api/teams` | 团队列表 |

## 原则

- Masterdata 是所有组织主数据的**唯一真实来源**
- 其他模块不得自行维护组织架构数据
- 所有变更记录审计日志，支持软删除和版本历史

## 依赖

- `user_admin` — 认证和权限验证
- `backend/shared/db_utils.py` — PostgreSQL 访问
- `backend/shared/config.py` — 端口配置
