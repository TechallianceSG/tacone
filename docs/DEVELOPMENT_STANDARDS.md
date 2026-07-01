# TACAI 开发规范

> 版本: 1.0  
> 适用范围: 本项目所有前后端代码

---

## 一、后端开发规范（Python）

### 1.1 服务结构

每个服务位于 `backend/services/<service_name>/`，标准目录：

```
service_name/
├── app.py              # 入口（必须），包含 RequestHandler
├── README.md           # 服务说明
└── tests/              # 测试（规划中）
```

### 1.2 入口文件 `app.py` 模板

```python
#!/usr/bin/env python3
"""Service description."""

from __future__ import annotations

import argparse, json, os, sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── Shared libraries (backend/shared/) ──
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))
from db_utils import load_table, save_table, insert_record, update_record, delete_record, require_pg
from config import get_portal_port, get_auth_port, ALLOWED_PORTS
from cors_middleware import add_cors_headers, handle_preflight

# ── Constants ──
ROOT_DIR = Path(__file__).resolve().parent

# ── Handler ──
class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        handle_preflight(self)

    def do_GET(self):
        # route handling
        pass

    def do_POST(self):
        # route handling
        pass

    def send_response(self, status):
        super().send_response(status)
        add_cors_headers(self)

# ── Main ──
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    if not require_pg():
        sys.exit(1)

    server = ThreadingHTTPServer((args.host, args.port), RequestHandler)
    print(f'Service running at http://{args.host}:{args.port}')
    server.serve_forever()
```

### 1.3 数据库操作

**必须使用 `db_utils` 进行所有数据操作，禁止直接读写 JSON 文件。**

```python
from db_utils import load_table, save_table, insert_record, update_record, delete_record

# 读取
records = load_table("ua_users")
records = load_table("ua_users", where="status = 'active'", order_by="created_at DESC")

# 全量替换
save_table("ua_users", records)

# 单条插入
insert_record("ua_users", {"user_id": "USR-0001", "username": "admin"})

# 单条更新
update_record("ua_users", "user_id", "USR-0001", {"status": "inactive"})

# 单条删除
delete_record("ua_users", "user_id", "USR-0001")
```

### 1.4 API 响应格式

使用 `api_utils` 统一响应（推荐），或直接构造标准 JSON：

```python
from api_utils import success, error, paginated, bad_request, not_found, parse_json_body, get_query_param

# 成功响应
success(self, {"user_id": "USR-0001"})                        # 200
success(self, {"user_id": "USR-0001"}, status=201)            # 201

# 分页列表
paginated(self, data, page=1, page_size=20, total=100)

# 错误响应
bad_request(self, "Validation failed", errors=["Name required"])
not_found(self, "User not found")

# 解析请求
body = parse_json_body(self)          # JSON body → dict or None
q = get_query_param(self, "q")        # ?q=xxx
```

**标准 JSON 结构：**

```json
// 成功（单条）
{ "success": true, "data": { ... } }

// 成功（列表）
{ "success": true, "data": [...], "pagination": { "page": 1, "page_size": 20, "total": 100 } }

// 错误
{ "success": false, "error": "错误描述", "errors": ["字段级错误1", "字段级错误2"] }
```

### 1.5 HTTP 状态码

| 状态码 | 场景 |
|--------|------|
| 200 | 成功读取/更新 |
| 201 | 成功创建 |
| 400 | 请求参数错误/验证失败 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 1.6 Session 验证

需要认证的接口，通过 User_admin 验证 `tacai_session_id` cookie：

```python
def current_user(self) -> dict | None:
    """Validate session with User_admin and return user dict."""
    cookie = self.headers.get("Cookie", "")
    # Call user_admin /api/validate-session with the cookie
    # Return user dict or None
    pass
```

### 1.7 日志

使用 `print(..., file=sys.stderr)` 输出日志，格式：

```
[service_name] 日志内容
```

示例：
```
[user_admin] User created: USR-0001
[portal] FATAL: db_utils is required.
```

---

## 二、前端开发规范（Vue 3 + TypeScript）

### 2.1 模块目录结构

```
src/modules/<module_name>/
├── <PageName>.vue       # 页面组件
├── <PageName>Detail.vue # 详情页
└── <PageName>Form.vue   # 表单页
```

### 2.2 组件规范

**必须使用 Element Plus 组件**，禁止裸写 `<table>` / `<form>` / `<button>`：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const loading = ref(false)
const data = ref([])
</script>

<template>
  <!-- ✅ 使用 Element Plus -->
  <el-table :data="data" v-loading="loading" stripe border>
    <el-table-column prop="name" :label="t('field.name')" />
    <el-table-column :label="t('field.actions')">
      <template #default="{ row }">
        <el-button type="primary" link @click="handleEdit(row)">{{ t('action.edit') }}</el-button>
      </template>
    </el-table-column>
  </el-table>

  <!-- ❌ 禁止原生 table -->
  <!-- <table><tr><td>...</td></tr></table> -->
</template>
```

### 2.3 API 调用

所有 API 接口统一定义在 `src/api/client.ts`：

```typescript
export const exampleApi = {
  list: (params?: Record<string, any>) => client.get('/api/example', { params }),
  get: (id: string) => client.get(`/api/example/${id}`),
  create: (data: Record<string, unknown>) => client.post('/api/example', data),
  update: (id: string, data: Record<string, unknown>) => client.post(`/api/example/${id}`, data),
}
```

**页面中调用：**
```typescript
import { exampleApi } from '@/api/client'

const { data } = await exampleApi.list({ page: 1, page_size: 20 })
items.value = data?.data || []
total.value = data?.pagination?.total || 0
```

### 2.4 路由规范

路由名称使用 PascalCase，路径使用 kebab-case：

```typescript
{
  path: 'example-items',       // kebab-case URL
  name: 'ExampleItemList',      // PascalCase 路由名
  component: () => import('@/modules/example/ExampleItemList.vue'),
  meta: {
    requiresAuth: true,
    permission: 'example.access',   // 权限 key
    titleKey: 'nav.example_items',  // i18n key
  },
}
```

### 2.5 多语言 (i18n)

**所有用户可见文本必须通过 `t()` 函数输出，禁止硬编码中文/英文/日文：**

```vue
<!-- ✅ 正确 -->
<h1>{{ t('users.title') }}</h1>
<el-button>{{ t('action.save') }}</el-button>

<!-- ❌ 错误 -->
<h1>用户列表</h1>
<el-button>保存</el-button>
```

**新增 key 时，必须在 `en.json` / `ja.json` / `zh.json` 三个文件中同时添加。**

命名规范：`{module}.{section}.{key}` 或 `{category}.{key}`

```json
"users.title": "User Management",
"users.create": "Create User",
"action.save": "Save",
"field.username": "Username"
```

### 2.6 样式

优先使用 Element Plus 内置样式和 CSS 变量，避免自定义颜色：

```css
/* ✅ Element Plus CSS 变量 */
.page { background: var(--el-bg-color-page); }
.title { color: var(--el-text-color-primary); }
.muted { color: var(--el-text-color-secondary); }

/* ❌ 硬编码颜色 */
.page { background: #f5f5f5; }
```

### 2.7 共享组件

跨模块复用的 UI 组件放在 `src/components/`：

```
src/components/
├── EntitySelector.vue     # 法人实体选择器
├── StatusTag.vue          # 状态标签
├── PageHeader.vue         # 页面标题栏
└── ConfirmDialog.vue      # 确认对话框
```

### 2.8 共享逻辑 (Composables)

跨模块复用的逻辑放在 `src/composables/`：

```typescript
// src/composables/usePagination.ts
export function usePagination(defaultPageSize = 20) {
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  // ...
  return { page, pageSize, handlePageChange, handleSizeChange }
}
```

---

## 三、数据库规范

### 3.1 表命名

```
{模块前缀}_{表名}

ua_users         — User_admin 用户表
ua_roles         — User_admin 角色表
ua_sessions      — User_admin 会话表
md_entities      — Masterdata 法人实体表
md_departments   — Masterdata 部门表
emp_employees    — Employee_admin 员工表
msg_messages     — Messaging 消息表
pt_modules       — Portal 模块配置表
ts_timesheet     — Timesheet 工时表
rmb_expense      — Reimbursement 报销表
pay_salary       — Payroll 薪资表
ss_leave         — Self_service 请假表
```

### 3.2 字段规范

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PRIMARY KEY | 自增主键 |
| `created_at` | TIMESTAMP DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMP DEFAULT NOW() | 更新时间 |
| `deleted_at` | TIMESTAMP NULL | 软删除标记 |

### 3.3 迁移文件

迁移脚本放在 `database/migrations/`，按序号命名：

```
001_user_admin_schema.sql
002_masterdata_schema.sql
003_employee_schema.sql
```

每个迁移包含该模块所有建表语句。

---

## 四、新增模块开发流程

### 4.1 后端

1. 创建目录 `backend/services/<module_name>/`
2. 创建 `app.py`，按模板添加共享库导入和路由
3. 在 `backend/shared/config.py` 的 `SHARED_SERVICES` 中注册服务
4. 分配端口，更新 `vite.config.ts` 代理配置
5. 创建数据库迁移脚本 `database/migrations/<NNN>_<module>.sql`
6. 执行迁移，验证 `python3 -m py_compile`

### 4.2 前端

1. 创建目录 `frontend/src/modules/<module_name>/`
2. 创建页面组件（List / Detail / Form）
3. 在 `src/api/client.ts` 添加 API 接口
4. 在 `src/router/index.ts` 添加路由
5. 在 `src/i18n/` 三语文件添加翻译 key
6. 运行 `npx vue-tsc --noEmit` 验证类型

### 4.3 启动脚本

在 `start_tacai_lan.sh` 的 `SHARED_SERVICES` 数组中添加新服务。

---

## 五、代码规范

### 5.1 Python

- 遵循 PEP 8
- 使用 `snake_case` 命名变量/函数/文件
- 类型注解：函数参数和返回值加类型
- 文件编码：UTF-8
- 缩进：4 空格

### 5.2 TypeScript / Vue

- 使用 `<script setup lang="ts">`
- 接口和类型使用 PascalCase
- 变量/函数使用 camelCase
- 组件文件使用 PascalCase
- 目录使用 snake_case 或 kebab-case
- 缩进：2 空格

### 5.3 Git

- 分支命名：`feature/<name>` / `fix/<name>` / `develop_<name>`
- Commit 信息：简洁描述改动内容
- 不要提交：`node_modules/`、`dist/`、`.env` 中的真实密码、运行时数据

---

## 六、安全规范

- 密码使用 PBKDF2-SHA256 哈希存储，禁止明文
- API 使用 session cookie (`tacai_session_id`) 认证
- 敏感操作必须记录审计日志
- 数据库连接信息通过环境变量读取，禁止硬编码
- 所有模块需要 `employee_management.access` 或对应权限才能访问

详见 [SECURITY.md](../SECURITY.md)
