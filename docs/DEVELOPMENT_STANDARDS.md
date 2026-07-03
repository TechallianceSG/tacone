# TACAI 开发规范

> 版本: 2.0  
> 更新日: 2026-07-03
> 适用范围: 本项目所有前后端代码
>
> **AI 协作规则**: CLAUDE.md 和本文档是 AI 编码的强制参考。实现任何功能前，AI 必须参考 §4 的新增模块流程和 §1.2 的 app.py 模板。违反规范的实施应被拒绝或重构。

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

**必须使用以下模板创建新服务**（参考 `employee_admin/app.py` 和 `datadict/app.py`）：

```python
#!/usr/bin/env python3
"""TACAI <Module Name> — standalone JSON API service.

Provides CRUD API for <table_name> (PostgreSQL).
Accessed via Portal API Gateway at /api/<prefix>/* → port <PORT>.
"""

from __future__ import annotations

import argparse, json, os, re, sys as _sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── Shared libraries (backend/shared/) ──
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))
import db_utils as _db
from auth_utils import validate_session, has_permission, is_system_admin

# ── Constants ──
MODULE_NAME = "tacai-<module>"
DEFAULT_PORT = <PORT>
TABLE_NAME = "<table_name>"
REQUIRED_PERMISSION = "<module>.access"

class <Module>Handler(BaseHTTPRequestHandler):
    server_version = "TACAI<Module>/0.1"

    _CORS_ORIGINS = {
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    }

    def add_cors(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = origin if origin in self._CORS_ORIGINS else "http://localhost:5173"
        self.send_header("Access-Control-Allow-Origin", allowed)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.add_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def log_message(self, format: str, *args) -> None:
        return  # suppress default logging

    def _current_user(self) -> dict | None:
        return validate_session(self.headers.get("Cookie", ""))

    def _require_user(self) -> dict | None:
        user = self._current_user()
        if not user:
            self.send_error_json("Unauthorized — invalid or expired session", 401)
            return None
        if not has_permission(user, REQUIRED_PERMISSION) and not is_system_admin(user):
            self.send_error_json("Forbidden — insufficient permissions", 403)
            return None
        return user

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.add_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/health":
            self.send_json({"status": "ok", "module": MODULE_NAME})
            return

        user = self._require_user()
        if not user:
            return

        # Route to handlers...
        self.send_error_json("Not Found", 404)

    def do_POST(self) -> None:
        user = self._require_user()
        if not user:
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = json.loads(self.rfile.read(length)) if length else {}
        # Route to handlers...
        self.send_error_json("Not Found", 404)

    def do_DELETE(self) -> None:
        user = self._require_user()
        if not user:
            return
        # Route to handlers...
        self.send_error_json("Not Found", 404)

# ── Main ──
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TACAI <Module>")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", str(DEFAULT_PORT))))
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), <Module>Handler)
    print(f"TACAI <Module> running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\nStopping TACAI <Module>")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
```

**关键规则:**
- 每个服务 **必须** 是 `backend/services/<name>/app.py` 下的独立文件
- 每个服务 **必须** 有自己的端口、自己的表前缀、自己的权限 key
- **禁止** 将新功能嵌入到现有服务的 app.py 中（如把字典塞进 masterdata）
- Handler 方法命名: `_handle_list`, `_handle_get_one`, `_handle_create`, `_handle_update`, `_handle_delete`

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

ua_users              — User_admin 用户表
ua_roles              — User_admin 角色表
ua_permissions        — User_admin 权限表
ua_sessions           — User_admin 会话表
md_entities           — Masterdata 法人实体表
md_departments        — Masterdata 部门表
md_teams              — Masterdata 团队表
emp_employees         — Employee_admin 员工表
dd_data_dictionary    — Data Dictionary 数据字典表
msg_workflow_templates— Messaging 工作流模板表
pt_modules            — Portal 模块配置表
pay_jp_salary_master  — Payroll JP 薪资主数据表
pay_jp_payroll_batches— Payroll JP 批次表
pay_jp_rate_type_labels— Payroll JP 费率标签字典
inv_invoices          — Invoice 发票表
```

### 3.2 字段规范

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PRIMARY KEY | 自增主键 |
| `created_at` | TIMESTAMP DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMP DEFAULT NOW() | 更新时间 |
| `deleted_at` | TIMESTAMP NULL | 软删除标记 |

### 3.3 迁移文件

迁移脚本放在 `database/migrations/`，按序号命名。每个迁移应包含该模块的**完整建表语句**（合并增量变更），避免冗余：

```
001_payroll_jp_schema.sql      — 日本薪资全部表
002_data_dictionary.sql        — 数据字典表 + 种子数据
```

**规则：**
- 新模块 = 新增一个迁移文件（下一个序号）
- 迁移文件是可重复执行的（使用 `CREATE TABLE IF NOT EXISTS` / `ON CONFLICT DO NOTHING`）
- 不再保留增量 ALTER TABLE 迁移（如 007_xxx, 008_xxx），应合并到主建表脚本中
- 迁移文件放在 `.gitignore` 中（`database/`），不作为源代码跟踪
- PostgreSQL 是运行时唯一数据源，迁移文件仅供新建环境参考

---

## 四、新增模块开发流程

### 4.1 后端（必须按顺序执行）

1. 创建目录 `backend/services/<module_name>/`
2. 创建 `app.py`，**严格按 §1.2 模板**编写（含 auth_utils、CORS、CRUD handler）
3. 分配端口（下一个可用端口，见 CLAUDE.md 端口表）
4. 在 `backend/shared/config.py` 中：
   - `SHARED_PORT` 添加端口映射
   - `GATEWAY_ROUTES` 添加 `/api/<prefix>/` → 端口
   - `SHARED_SERVICES` 添加 ServiceInfo 注册
5. 在 `start_tacai_lan.sh` 的 `SHARED_SERVICES` 数组中添加启动条目
6. 创建数据库迁移 `database/migrations/<NNN>_<module>.sql`（下一个序号）
7. 如需要新权限，在 `ua_permissions` 表中添加并分配给对应角色
8. 验证：`python3 -m py_compile app.py` → 启动服务 → `curl /health`

### 4.2 前端（必须按顺序执行）

1. 创建目录 `frontend/src/modules/<module_name>/`
2. 创建页面组件（List 页含 toolbar + table + dialog + pagination）
3. 在 `src/api/client.ts` 添加 API 对象（命名：`<module>Api`）
4. 在 `src/router/index.ts` 添加路由（含 `permission` 和 `titleKey` meta）
5. 在 Dashboard.vue 的 `allModules` 数组中添加入口卡片
6. 在 `src/i18n/` 三语文件同时添加翻译 key（`nav.<module>`, `module.<module>`, `<module>.*`）
7. 运行 `npx vue-tsc --noEmit` 验证类型

### 4.3 启动脚本

在 `start_tacai_lan.sh` 的 `SHARED_SERVICES` 数组中添加新服务（格式：`"<name>|<port>|<dir>|<command>"`）。

### 4.4 检查清单

新增模块必须满足以下所有条件才能合并：

- [ ] 独立的 `backend/services/<name>/app.py` 文件（非嵌入现有服务）
- [ ] 独立的数据库表前缀
- [ ] 独立的权限 key（`<module>.access`）
- [ ] 在 config.py 中完整注册（SHARED_PORT + GATEWAY_ROUTES + SHARED_SERVICES）
- [ ] 在 start_tacai_lan.sh 中添加启动条目
- [ ] 前端 API client、router、Dashboard、i18n 三语文件全部更新
- [ ] `python3 -m py_compile` 和 `npx vue-tsc --noEmit` 通过

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
