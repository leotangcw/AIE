# 部署与运维 (Deployment)

> CountBot 的安装、启动、部署和运维指南。

## 目录

- [环境要求](#环境要求)
- [安装](#安装)
- [启动](#启动)
- [启动流程详解](#启动流程详解)
- [环境变量](#环境变量)
- [数据库](#数据库)
- [SSL 兼容性](#ssl-兼容性)
- [生产部署](#生产部署)
- [目录结构](#目录结构)
- [日志](#日志)
- [故障排查](#故障排查)

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 必需 |
| Node.js | 18+ | 仅开发前端时需要 |
| pip | 最新 | Python 包管理 |

### 系统支持

| 平台 | 状态 | 说明 |
|------|------|------|
| macOS | ✅ 完整支持 | 自动处理 SSL 证书 |
| Linux | ✅ 完整支持 | 无需额外配置 |
| Windows | ✅ 支持 | 自动注入系统证书 |

## 安装

### 基础安装

```bash
# 克隆仓库
git clone https://github.com/countbot-ai/countbot.git
cd CountBot

# 安装 Python 依赖
pip install -r requirements.txt
```

### 核心依赖

```
fastapi==0.104.1          # Web 框架
uvicorn[standard]==0.24.0 # ASGI 服务器
sqlalchemy==2.0.23        # ORM
aiosqlite==0.19.0         # SQLite 异步驱动
litellm==1.3.1            # LLM 统一接口
pydantic==2.5.0           # 数据验证
loguru==0.7.2             # 日志
```

### 桌面运行环境

```
pywebview           # 桌面容器 CountBot Desktop
```

### 渠道 SDK（可选）

```
qq-botpy>=1.2.1           # QQ 机器人
dingtalk-stream>=0.24.3   # 钉钉 Stream
lark-oapi>=1.5.3          # 飞书
```

如果不需要某个渠道，可以不安装对应 SDK，系统会自动跳过。

### 前端构建（可选）

```bash
cd frontend
npm install
npm run build
cd ..
```

构建产物在 `frontend/dist/`，后端会自动挂载为静态文件。

## 启动

### 快速启动

```bash
python start_app.py
```

默认监听 `127.0.0.1:8000`


### 开发模式

```bash
# 后端热重载
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

# 前端开发服务器（另一个终端）
cd frontend
npm install
npm run dev
```

### 桌面模式（pywebview）

CountBot 支持通过 pywebview 以原生桌面窗口运行，无需浏览器：

```bash
# 安装 pywebview 依赖（已包含在 requirements.txt）
pip install pywebview>=5.0

# 启动桌面应用
python start_desktop.py
```

桌面模式特性：
- 自动构建前端（如果 `frontend/dist/` 不存在或 `--rebuild` 参数）
- 原生窗口，默认尺寸 960×680，最小 720×480
- 后端自动启动，窗口关闭时优雅退出
- 支持 macOS、Windows、Linux

## 启动流程详解

`start_app.py` 和 `backend/app.py` 的完整启动流程：

```
python start_app.py
  │
  ├─ 1. SSL 证书配置
  │     ensure_ssl_certificates()
  │     ├─ macOS: 通过 certifi 设置 SSL_CERT_FILE
  │     ├─ Windows: 从系统证书库加载证书
  │     └─ Linux: 无需处理
  │
  ├─ 2. 启动 uvicorn 服务器
  │     uvicorn.run("backend.app:app", ...)
  │
  └─ 3. 延迟 2 秒后打开浏览器
        webbrowser.open("http://localhost:8000")

backend.app:app lifespan:
  │
  ├─ 4. 数据库初始化
  │     init_db() → 创建表（通过 SQLAlchemy）
  │
  ├─ 5. 加载配置
  │     config_loader.load() → 从 settings 表读取
  │
  ├─ 6. 创建共享组件
  │     _create_shared_components(config)
  │     ├─ LiteLLMProvider (LLM 提供商)
  │     ├─ MemoryStore (记忆存储)
  │     ├─ SkillsLoader (技能加载器)
  │     ├─ ContextBuilder (上下文构建器)
  │     ├─ SubagentManager (子代理管理器)
  │     └─ ToolRegistry (工具注册表，9+ 工具)
  │
  ├─ 7. 初始化消息系统
  │     ├─ EnterpriseMessageQueue (消息队列)
  │     ├─ RateLimiter (流量控制)
  │     └─ ChannelMessageHandler (消息处理器)
  │
  ├─ 8. 初始化渠道
  │     ChannelManager(config, bus)
  │     └─ 按配置初始化已启用的渠道
  │
  ├─ 9. 启动后台任务
  │     ├─ channel_manager.start_all() (启动渠道)
  │     └─ message_handler.start_processing() (启动消息处理)
  │
  ├─ 10. 初始化 Cron 系统
  │      ├─ CronExecutor (任务执行器)
  │      ├─ CronScheduler (调度器)
  │      └─ scheduler.start() (开始调度)
  │
  └─ 11. 就绪
         "Backend started successfully"
```

### 关闭流程

```
收到 SIGTERM / Ctrl+C
  │
  ├─ channel_manager.stop_all()  # 停止所有渠道
  ├─ scheduler.stop()            # 停止 Cron 调度器
  └─ "Backend shutdown complete"
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `BRAVE_API_KEY` | — | Brave Search API 密钥（可选） |
| `SSL_CERT_FILE` | 自动配置 | SSL 证书路径（macOS 自动设置） |

大部分配置通过 Web UI 的设置页面管理，存储在数据库中，不需要环境变量。

## 数据库

### 存储位置

```
data/
├── countbot.db        # SQLite 数据库
└── audit_logs/       # 审计日志文件
```

`data/` 目录在首次启动时自动创建。

### 数据库表

| 表 | 说明 |
|----|------|
| `sessions` | 聊天会话 |
| `messages` | 聊天消息 |
| `settings` | 配置键值对 |
| `cron_jobs` | 定时任务 |
| `tasks` | 后台任务 |
| `tool_conversations` | 工具调用记录 |

### 迁移

数据库表通过 SQLAlchemy 的 `Base.metadata.create_all` 自动创建。

如需执行数据库迁移，可在 `backend/migrations/` 目录下添加迁移脚本。

### 备份

```bash
# 备份数据库
cp data/countbot.db data/countbot.db.bak

# 备份记忆
cp memory/MEMORY.md memory/MEMORY.md.bak
```

## SSL 兼容性

**文件**: `backend/utils/ssl_compat.py`

CountBot 在启动时自动处理 SSL 证书问题：

### macOS

Python 在 macOS 上默认不使用系统 SSL 证书，导致 HTTPS 请求失败。CountBot 通过 `certifi` 包自动配置：

```python
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
```

如果遇到 SSL 错误，确保安装了 `certifi`：

```bash
pip install certifi
```

### Windows

自动从系统证书库（CA、ROOT、MY）加载证书到 Python SSL 上下文，支持自签名证书。

### Linux

通常无需额外处理。

## 生产部署

### 远程访问认证

当通过非本地 IP 访问 CountBot 时（如局域网 `192.168.x.x` 或公网 IP），系统自动启用认证保护：

- 首次远程访问时引导设置管理员账号密码
- 密码要求：至少 8 位，包含大写字母、小写字母和数字
- 认证 token 有效期 24 小时，应用重启后需重新登录
- 本地访问（`127.0.0.1` / `::1`）完全不受影响
- 渠道交互（Telegram/钉钉/飞书/QQ/微信）不受影响

详见 [auth.md](./auth.md)。

### 使用 systemd（Linux）

```ini
# /etc/systemd/system/CountBot.service
[Unit]
Description=CountBot AI Assistant
After=network.target

[Service]
Type=simple
User=CountBot
WorkingDirectory=/opt/CountBot
ExecStart=/opt/CountBot/venv/bin/python start_app.py
Restart=always
RestartSec=5
Environment=PORT=8000

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable CountBot
sudo systemctl start CountBot
```

### 使用 Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 构建前端（如果需要）
# RUN cd frontend && npm install && npm run build

EXPOSE 8000
CMD ["python", "start_app.py"]
```

```bash
docker build -t CountBot .
docker run -d -p 8000:8000 -v ./data:/app/data CountBot
```

### 反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name CountBot.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

注意 WebSocket 需要 `Upgrade` 和 `Connection` 头。

> **认证注意**：如果使用 Nginx 反向代理，CountBot 的认证中间件会检测 `X-Forwarded-For` 头。当存在此头时，即使 `client.host` 是 `127.0.0.1`，也不会被视为本地请求，需要正常认证。这是为了防止通过代理绕过认证。

## 目录结构

运行时目录：

```
CountBot/
├── data/                  # 运行时数据（自动创建）
│   ├── countbot.db         # SQLite 数据库
│   └── audit_logs/        # 审计日志
├── memory/                # 记忆存储（自动创建）
│   └── MEMORY.md          # 长期记忆文件
├── skills/                # 技能目录
├── screenshots/           # 截图输出（自动创建）
├── frontend/dist/         # 前端构建产物
└── botpy.log              # QQ SDK 日志
```

## 日志

CountBot 使用 `loguru` 记录日志，输出到 stderr。

### 日志级别

| 级别 | 说明 |
|------|------|
| DEBUG | 详细调试信息（工具定义、消息构建） |
| INFO | 正常运行信息（启动、工具执行、会话） |
| WARNING | 警告（可选功能不可用、非致命错误） |
| ERROR | 错误（工具执行失败、渠道连接失败） |

### 审计日志

工具调用审计日志存储在 `data/audit_logs/` 目录，按日期分文件。

可通过 `SecurityConfig.audit_log_enabled` 开关。

## 故障排查

### SSL 证书错误

```
ssl.SSLCertVerificationError: certificate verify failed
```

解决：
```bash
pip install certifi
# 或手动设置
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")
```

### 钉钉连接失败

```
socket.gaierror: [Errno 8] nodename nor servname provided
```

这是 DNS 解析失败，检查网络连接。钉钉 SDK 的日志格式有 bug（`self.logger.exception('unknown exception', e)` 缺少格式占位符），不影响功能。

### 端口被占用

```
OSError: [Errno 48] Address already in use
```

解决：
```bash
# 查找占用端口的进程
lsof -i :8000
# 或使用其他端口
PORT=9000 python start_app.py
```

### 数据库锁定

```
sqlite3.OperationalError: database is locked
```

SQLite 不支持高并发写入。确保只有一个 CountBot 实例在运行。

### LLM API 错误

```
litellm.exceptions.AuthenticationError
```

检查 Web UI → 设置 → 提供商配置中的 API Key 是否正确。

### 渠道 SDK 缺失

```
ImportError: No module named 'dingtalk_stream'
```

安装对应 SDK：
```bash
pip install dingtalk-stream  # 钉钉
pip install qq-botpy         # QQ
pip install lark-oapi        # 飞书
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `start_app.py` | 应用入口（浏览器模式） |
| `start_desktop.py` | 桌面应用入口（pywebview） |
| `backend/app.py` | FastAPI 应用和生命周期 |
| `backend/database.py` | 数据库配置 |
| `backend/utils/ssl_compat.py` | SSL 兼容性 |
| `backend/utils/logger.py` | 日志配置 |
| `requirements.txt` | Python 依赖 |
