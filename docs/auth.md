# 远程访问认证 (Remote Access Authentication)

> CountBot 内置远程访问认证模块，当通过非本地 IP 访问时自动触发认证保护，防止未授权的远程访问。

## 目录

- [设计理念](#设计理念)
- [工作原理](#工作原理)
- [认证流程](#认证流程)
- [密码要求](#密码要求)
- [API 接口](#api-接口)
- [安全机制](#安全机制)
- [前端集成](#前端集成)
- [WebSocket 认证](#websocket-认证)
- [常见问题](#常见问题)
- [相关文件](#相关文件)

## 设计理念

1. **本地访问零摩擦** — `127.0.0.1` / `::1` 访问完全不受影响，无需任何认证
2. **远程访问自动保护** — 通过 LAN IP（如 `192.168.x.x`）或公网 IP 访问时自动触发认证
3. **首次引导设置** — 远程用户首次访问时引导设置账号密码，设置后自动登录
4. **渠道不受影响** — Telegram、钉钉、飞书、QQ、微信等渠道交互完全不受认证影响（渠道使用主动连接模式，不经过 HTTP 中间件）

## 工作原理

### 架构

```
远程请求 (192.168.x.x)
  │
  ▼
┌─────────────────────────────────────────┐
│         RemoteAuthMiddleware            │
│                                         │
│  1. 非 /api/ 和 /ws/ 路径 → 放行       │
│  2. 白名单路径 → 放行                   │
│  3. 本地 IP (127.0.0.1/::1) → 放行     │
│  4. 未设置密码 → 放行（日志警告）        │
│  5. 有密码 + 有效 token → 放行          │
│  6. 有密码 + 无效 token → 401 AUTH_REQUIRED│
└─────────────────────────────────────────┘

本地请求 (127.0.0.1)
  │
  ▼ 直接放行，无任何拦截
```

### 判断逻辑

| 条件 | 结果 |
|------|------|
| 本地 IP (`127.0.0.1` / `::1`) | 直接放行 |
| 白名单路径 (`/api/auth/*`, `/api/health`) | 直接放行 |
| 远程 IP + 未设置密码 | 放行（前端显示安全警告提示设置密码） |
| 远程 IP + 已设置密码 + 有效 token | 放行 |
| 远程 IP + 已设置密码 + 无效/无 token | 401 `AUTH_REQUIRED` |

### 白名单路径

以下路径不需要认证即可访问：

```
/api/auth/*        — 认证相关接口（登录、注册、状态查询）
/api/health        — 健康检查
/docs              — API 文档
/openapi.json      — OpenAPI 规范
/login             — 登录页面
/assets/*          — 前端静态资源
```

## 认证流程

### 首次远程访问（未设置密码）

```
1. 用户访问 http://192.168.x.x:8000/
2. 前端加载 → App.vue 调用 GET /api/auth/status
3. 返回 { is_local: false, auth_enabled: false, authenticated: false }
4. 前端跳转到 /login 页面
5. LoginView 检测到 auth_enabled=false → 显示「设置密码」模式
6. 用户输入账号 + 密码 + 确认密码
7. POST /api/auth/setup → 保存凭据 → 返回 token
8. 前端保存 token 到 localStorage → 跳转到主页
```

### 已设置密码的远程访问

```
1. 用户访问 http://192.168.x.x:8000/
2. 前端加载 → App.vue 调用 GET /api/auth/status
3. 返回 { is_local: false, auth_enabled: true, authenticated: false }
4. 前端跳转到 /login 页面
5. LoginView 检测到 auth_enabled=true → 显示「登录」模式
6. 用户输入账号 + 密码
7. POST /api/auth/login → 验证凭据 → 返回 token
8. 前端保存 token 到 localStorage → 跳转到主页
```

### 已登录的远程访问

```
1. 用户访问 http://192.168.x.x:8000/
2. 前端加载 → axios 拦截器自动附带 Bearer token
3. 所有 API 请求携带 Authorization header
4. 中间件验证 token 有效 → 放行
```

## 密码要求

- 至少 8 位字符
- 必须同时包含：大写字母、小写字母、数字（三种缺一不可）
- 示例合格密码：`MyPass123`、`Admin2024`、`Test1234`

## API 接口

### GET /api/auth/status

查询当前认证状态。

**响应**:
```json
{
  "is_local": false,
  "auth_enabled": true,
  "authenticated": false
}
```

| 字段 | 说明 |
|------|------|
| `is_local` | 是否为本地访问 |
| `auth_enabled` | 是否已设置密码（启用远程认证） |
| `authenticated` | 当前请求是否已认证 |

### POST /api/auth/setup

首次设置密码（仅当未设置密码时可用）。

**请求体**:
```json
{
  "username": "admin",
  "password": "MyPass123"
}
```

**响应**:
```json
{
  "success": true,
  "message": "密码设置成功",
  "token": "session_token_xxx"
}
```

### POST /api/auth/login

登录。

**请求体**:
```json
{
  "username": "admin",
  "password": "MyPass123"
}
```

**响应**:
```json
{
  "success": true,
  "message": "登录成功",
  "token": "session_token_xxx"
}
```

### POST /api/auth/logout

登出（清除 session）。

### POST /api/auth/change-password

修改密码（需要已认证或本地访问）。

**请求体**:
```json
{
  "old_password": "MyPass123",
  "new_password": "NewPass456"
}
```

## 安全机制

### IP 判断基于 TCP Socket

中间件通过 `request.client.host` 获取客户端 IP，这是 TCP 连接层的对端 IP，不可通过 HTTP 头伪造。

### 防代理绕过

如果请求中包含 `X-Forwarded-For` 头，即使 `client.host` 是本地 IP，也不会被视为本地请求。这防止了通过反向代理伪造本地访问的攻击。

### 本地 IP 白名单

仅信任以下 IP 为本地访问：
- `127.0.0.1` — IPv4 回环地址
- `::1` — IPv6 回环地址

不包含 `localhost` 字符串（因为 `client.host` 始终是解析后的 IP 地址）。

### 密码存储

- 使用 SHA-256 + 随机 salt 哈希存储
- 凭据保存在 SQLite `settings` 表（`auth.username` 和 `auth.password_hash`）
- 密码验证使用 `secrets.compare_digest` 防止时序攻击

### Session Token

- 使用 `secrets.token_urlsafe(32)` 生成
- 内存存储，24 小时过期
- 支持通过 Cookie（`CountBot_token`）或 Authorization Header（`Bearer xxx`）传递
- 应用重启后所有 session 失效（需重新登录）

## 前端集成

### Token 管理

- 登录成功后 token 保存到 `localStorage.CountBot_token`
- axios 请求拦截器自动附带 `Authorization: Bearer {token}`
- 响应拦截器捕获 401 + `AUTH_REQUIRED`/`AUTH_SETUP_REQUIRED` → 跳转 `/login`

### WebSocket 认证

WebSocket 连接时通过 URL query 参数传递 token：

```
ws://192.168.x.x:8000/ws/chat?token=xxx
```

如果 token 无效，服务端关闭连接（code 4001），前端自动跳转登录页。

### 登录页面

`/login` 路由渲染 `LoginView.vue`，根据 `/api/auth/status` 返回的 `auth_enabled` 字段自动切换：
- `auth_enabled=false` → 显示「首次设置」模式（含确认密码）
- `auth_enabled=true` → 显示「登录」模式

## 常见问题

### Q: 本地访问会受影响吗？

不会。`127.0.0.1` 和 `::1` 的访问完全不经过认证检查。

### Q: 渠道（Telegram/钉钉等）会受影响吗？

不会。所有渠道使用主动连接模式（长轮询或 WebSocket Stream），不通过 HTTP 中间件。

### Q: 忘记密码怎么办？

通过本地访问 `http://127.0.0.1:8000` 进入系统，在设置中修改密码，或直接清除数据库中的 `auth.password_hash` 记录。

### Q: 重启后需要重新登录吗？

是的。Session token 存储在内存中，应用重启后失效。

### Q: 如何禁用远程认证？

通过本地访问清除密码即可。未设置密码时，远程访问会提示设置密码但不会阻止前端页面加载。

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/auth/middleware.py` | 认证中间件（`RemoteAuthMiddleware`） |
| `backend/modules/auth/router.py` | 认证 API 端点 |
| `backend/modules/auth/utils.py` | 密码验证、哈希、session 管理 |
| `backend/api/auth.py` | API 路由注册 |
| `backend/app.py` | 中间件注册、WebSocket 认证 |
| `frontend/src/views/LoginView.vue` | 登录/设置密码页面 |
| `frontend/src/api/client.ts` | axios 拦截器（token 注入、401 处理） |
| `frontend/src/api/websocket.ts` | WebSocket token 传递 |
| `frontend/src/App.vue` | 启动时认证状态检查 |
| `tests/test_auth.py` | 认证模块单元测试 |
