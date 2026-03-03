# CountBot 功能开通指南

> 本文档详细说明 CountBot 各项核心功能的配置方法，包括具体的文件路径、配置格式和获取密钥的步骤。按照本指南操作即可逐步开通所有功能。

## 目录

- [1. 大模型 API 配置（必需）](#1-大模型-api-配置必需)
- [2. 渠道接入配置](#2-渠道接入配置)
  - [2.1 飞书](#21-飞书)
  - [2.2 钉钉](#22-钉钉)
  - [2.3 Telegram](#23-telegram)
  - [2.4 QQ](#24-qq)
  - [2.5 微信公众号](#25-微信公众号)
- [3. 技能配置](#3-技能配置)
  - [3.1 图片分析（image-analysis）](#31-图片分析image-analysis)
  - [3.2 百度搜索（baidu-search）](#32-百度搜索baidu-search)
  - [3.3 邮箱管理（email）](#33-邮箱管理email)
  - [3.4 地图导航（map）](#34-地图导航map)
  - [3.5 天气查询（weather）](#35-天气查询weather)
  - [3.6 AI 图片生成（image-gen）](#36-ai-图片生成image-gen)
  - [3.7 网页设计与部署（web-design）](#37-网页设计与部署web-design)
  - [3.8 新闻查询（news）](#38-新闻查询news)
  - [3.9 定时任务管理（cron-manager）](#39-定时任务管理cron-manager)
  - [3.10 浏览器自动化（agent-browser）](#310-浏览器自动化agent-browser)
- [4. 功能开通状态检查](#4-功能开通状态检查)

---

## 1. 大模型 API 配置（必需）

这是 CountBot 运行的前提条件。没有大模型 API，所有 AI 功能都无法使用。

### 推荐方案：智谱 GLM-5、Qwen3.5-Plus、Kimi K2.5、MiniMax-M2.5

智谱 AI 提供免费的 GLM-4.7-Flash 模型，能力足够满足大部分 AI Agent 任务（对话、工具调用、代码生成、文件分析等），是零成本上手的最佳选择。

### 获取 API Key

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 注册账号并登录
3. 进入「API 密钥」页面，创建一个新的 API Key
4. 复制 API Key（格式类似 `xxxxxxxx.xxxxxxxxxxxxxxxx`）

### 配置方式

#### 方式一：通过 Web UI 配置（推荐）

1. 启动 CountBot：`python start_app.py`
2. 打开浏览器访问 `http://localhost:8000`
3. 点击左下角「设置」图标
4. 进入「提供商」标签页
5. 选择「智谱 AI」，填入 API Key
6. 进入「模型」标签页，确认：
   - 提供商：`zhipu`
   - 模型：`glm-5`
7. 点击「保存」

#### 方式二：通过 API 配置

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "providers": {
      "zhipu": {
        "api_key": "你的API Key",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "enabled": true
      }
    },
    "model": {
      "provider": "zhipu",
      "model": "glm-5"
    }
  }'
```

### 验证配置

在 Web UI 设置页面点击「测试连接」，显示「成功连接」即表示配置正确。

### 其他可选提供商

| 提供商 | 模型 | 费用 | 适用场景 |
|--------|------|------|----------|
| 智谱 AI | glm-4.7-flash | 免费 | 通用任务，推荐入门 |
| DeepSeek | deepseek-chat | 低价 | 代码生成、推理 |
| OpenAI | gpt-5.3 | 付费 | 高质量对话 |
| Anthropic | claude-sonnet-4-20250514 | 付费 | 长文本、分析 |
| Moonshot | kimi-k2.5 | 付费 | 中文对话 |
| Ollama | 本地部署 | 免费（本地） | 隐私敏感场景 |

配置方式相同，在设置页面选择对应提供商并填入 API Key 即可。

---

## 2. 渠道接入配置

渠道是 CountBot 连接外部即时通讯平台的桥梁。配置渠道后，你可以通过飞书、钉钉、Telegram、QQ、微信等平台与 CountBot 对话。

所有渠道的配置方式统一：通过 Web UI → 设置 → 渠道标签页，或通过 `PUT /api/settings` 接口的 `channels` 字段。

配置数据模型定义在 `backend/modules/config/schema.py`，渠道管理器在 `backend/modules/channels/manager.py`。

### 2.1 飞书

推荐使用飞书接入，飞书使用 WebSocket 长连接模式，无需公网 IP 或域名。

#### 获取凭证

1. 访问 [飞书开放平台](https://open.feishu.cn/)，注册并登录
2. 创建自建应用
3. 在应用的「凭证与基础信息」页面获取：
   - `App ID`（应用 ID）
   - `App Secret`（应用密钥）
4. 在「事件与回调」→「加密策略」中获取：
   - `Encrypt Key`（加密密钥）
   - `Verification Token`（验证令牌）
5. 在「权限管理」中开通以下权限：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message.group_at_msg`（接收群聊中 @ 机器人消息）
   - `im:resource`（获取消息中的资源文件）
6. 发布应用版本，等待管理员审批通过

#### 配置方式

Web UI → 设置 → 渠道 → 飞书，填入以下字段：

| 字段 | 说明 |
|------|------|
| `app_id` | 飞书应用 App ID |
| `app_secret` | 飞书应用 App Secret |
| `encrypt_key` | 事件加密密钥（可选） |
| `verification_token` | 事件验证令牌（可选） |
| `enabled` | 设为 `true` 开启 |
| `allow_from` | 允许的用户 ID 白名单（可选，空数组表示允许所有人） |

API 配置示例：

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "channels": {
      "feishu": {
        "enabled": true,
        "app_id": "cli_xxxxxxxxxx",
        "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
        "encrypt_key": "xxxxxxxxxxxxxxxx",
        "verification_token": "xxxxxxxxxxxxxxxx",
        "allow_from": []
      }
    }
  }'
```

#### 依赖安装

```bash
pip install lark-oapi
```

#### 连接方式

飞书渠道使用 WebSocket 模式（`feishu_websocket_worker.py`），启动后自动建立长连接，无需配置回调地址。

---

### 2.2 钉钉

钉钉同样使用 Stream Mode（WebSocket），无需公网 IP。

#### 获取凭证

1. 访问 [钉钉开放平台](https://open.dingtalk.com/)，登录
2. 创建内部应用（机器人类型）
3. 在「应用凭证」页面获取：
   - `Client ID`（AppKey）
   - `Client Secret`（AppSecret）
4. 在「消息接收模式」中选择「Stream 模式」
5. 在「机器人配置」中开启机器人功能

#### 配置方式

Web UI → 设置 → 渠道 → 钉钉，填入以下字段：

| 字段 | 说明 |
|------|------|
| `client_id` | 钉钉应用 Client ID（AppKey） |
| `client_secret` | 钉钉应用 Client Secret（AppSecret） |
| `enabled` | 设为 `true` 开启 |
| `allow_from` | 允许的用户 ID 白名单（可选） |

API 配置示例：

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "channels": {
      "dingtalk": {
        "enabled": true,
        "client_id": "dingxxxxxxxxxx",
        "client_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
        "allow_from": []
      }
    }
  }'
```

#### 依赖安装

```bash
pip install dingtalk-stream
```

---

### 2.3 Telegram

Telegram 使用 Long Polling 模式，需要网络能访问 Telegram API（可配置代理）。

#### 获取凭证

1. 在 Telegram 中搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示创建机器人
3. 获取 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

#### 配置方式

Web UI → 设置 → 渠道 → Telegram，填入以下字段：

| 字段 | 说明 |
|------|------|
| `token` | Telegram Bot Token |
| `proxy` | 代理地址（可选，如 `socks5://127.0.0.1:1080`） |
| `enabled` | 设为 `true` 开启 |
| `allow_from` | 允许的用户 ID 白名单 |

API 配置示例：

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "channels": {
      "telegram": {
        "enabled": true,
        "token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "proxy": null,
        "allow_from": []
      }
    }
  }'
```

#### 依赖安装

```bash
pip install python-telegram-bot
```

#### 注意事项

- 如果在中国大陆使用，需要配置 `proxy` 字段
- `allow_from` 填写 Telegram 用户 ID（数字），可通过 @userinfobot 获取

---

### 2.4 QQ

QQ 机器人基于 QQ 开放平台官方 SDK。

#### 获取凭证

1. 访问 [QQ 开放平台](https://q.qq.com/)，注册开发者账号
2. 创建机器人应用
3. 在应用管理页面获取：
   - `App ID`
   - `Secret`（App Secret）
4. 配置沙箱环境或正式环境

#### 配置方式

Web UI → 设置 → 渠道 → QQ，填入以下字段：
注意：MarkDown格式支持需要在QQ开放平台申请
| 字段 | 说明 |
|------|------|
| `app_id` | QQ 机器人 App ID |
| `secret` | QQ 机器人 App Secret |
| `enabled` | 设为 `true` 开启 |
| `allow_from` | 允许的用户 ID 白名单 （可选）|
| `oss` | 腾讯云 OSS 配置（可选，用于图片发送） |

API 配置示例：

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "channels": {
      "qq": {
        "enabled": true,
        "app_id": "你的AppID",
        "secret": "你的AppSecret",
        "allow_from": [],
        "markdown_enabled": true,
        "oss": {
          "secret_id": "",
          "secret_key": "",
          "bucket": "",
          "region": "ap-guangzhou"
        }
      }
    }
  }'
```

#### 依赖安装

```bash
pip install qq-botpy
```

#### 图片发送（可选）

飞书、钉钉已经实图片的接收和发送，如果需要通过 QQ 渠道发送图片，需要配置腾讯云 OSS：

1. 访问 [腾讯云对象存储](https://console.cloud.tencent.com/cos)
2. 创建存储桶（Bucket）
3. 在「密钥管理」获取 `SecretId` 和 `SecretKey`
4. 填入 `oss` 配置项

---

### 2.5 微信公众号（待实现）

微信公众号渠道需要公网可访问的回调地址。

#### 获取凭证

1. 访问 [微信公众平台](https://mp.weixin.qq.com/)，注册公众号
2. 在「设置与开发」→「基本配置」中获取：
   - `AppID`（开发者 ID）
   - `AppSecret`（开发者密码）
3. 在「服务器配置」中设置：
   - `Token`（自定义令牌）
   - `EncodingAESKey`（消息加解密密钥，可随机生成）
   - 服务器地址（URL）：`http://你的公网地址:8000/api/channels/wechat/callback`

#### 配置方式

Web UI → 设置 → 渠道 → 微信，填入以下字段：

| 字段 | 说明 |
|------|------|
| `app_id` | 微信公众号 AppID |
| `app_secret` | 微信公众号 AppSecret |
| `token` | 服务器配置中的 Token |
| `encoding_aes_key` | 消息加解密密钥 |
| `enabled` | 设为 `true` 开启 |
| `allow_from` | 允许的用户 OpenID 白名单 |

API 配置示例：

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "channels": {
      "wechat": {
        "enabled": true,
        "app_id": "wx_xxxxxxxxxx",
        "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "token": "your_custom_token",
        "encoding_aes_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "allow_from": []
      }
    }
  }'
```

#### 注意事项

- 微信公众号需要公网可访问的服务器地址
- 如果在本地开发，可使用 ngrok 等内网穿透工具
- 微信公众号有 5 秒响应超时限制，复杂任务可能需要异步处理

---

### 渠道安全：allow_from 白名单

所有渠道都支持 `allow_from` 字段，用于限制哪些用户可以与机器人交互：

- 空数组 `[]`：允许所有人（适合测试）
- 填写用户 ID：只允许指定用户（推荐生产环境使用）

```json
"allow_from": ["user_id_1", "user_id_2"]
```

各渠道的用户 ID 格式不同：
- 飞书：用户的 Open ID（如 `ou_xxxxxxxxxx`）
- 钉钉：用户的 staffId
- Telegram：用户数字 ID（如 `123456789`）
- QQ：用户 ID
- 微信：用户 OpenID


---

## 3. 技能配置

技能（Skills）是 CountBot 的可插拔功能模块，每个技能有独立的配置文件。技能目录位于项目根目录的 `skills/` 文件夹下。

配置流程：
1. 找到技能目录下的 `scripts/config.json.example`
2. 复制为 `scripts/config.json`
3. 编辑 `config.json`，填入所需的 API Key 等信息
4. 在 Web UI → 技能页面启用该技能

### 3.1 图片分析（image-analysis）

图片分析技能支持 OCR 文字识别、物体识别、场景理解等功能，基于视觉大模型实现。

#### 配置文件

```
skills/image-analysis/scripts/config.json
```

从示例文件复制：

```bash
cp skills/image-analysis/scripts/config.json.example skills/image-analysis/scripts/config.json
```

#### 配置内容

```json
{
  "default_model": "zhipu",
  "zhipu": {
    "api_key": "你的智谱API Key",
    "model": "glm-4.6v-flash",
    "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"
  },
  "qwen": {
    "api_key": "你的千问API Key",
    "model": "qwen3-vl-plus",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "region": "beijing"
  }
}
```

#### 获取 API Key

**方案一：智谱 GLM-4V（推荐，免费）**

如果你已经在第 1 步配置了智谱 API Key，这里可以直接复用同一个 Key。

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 使用已有的 API Key 即可
3. 默认模型 `glm-4.6v-flash` 是免费的视觉模型

**方案二：千问 Qwen-VL**

1. 访问 [阿里云百炼平台](https://help.aliyun.com/zh/model-studio/get-api-key)
2. 开通模型服务并获取 API Key
3. 将 `default_model` 改为 `"qwen"`

#### 启用技能

在 Web UI → 技能页面，找到「图片分析」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 图片描述 | `analyze --image 图片路径 --prompt "描述图片内容"` |
| OCR 文字识别 | `analyze --image 图片路径 --prompt "提取图片中的文字"` |
| 多图对比 | `analyze --image img1.jpg --image img2.jpg --prompt "对比差异"` |
| 视频分析 | `analyze --video video.mp4 --prompt "总结视频内容"` |
| 思考模式（智谱） | 添加 `--thinking` 参数，提升复杂推理准确度 |

---

### 3.2 百度搜索（baidu-search）

百度 AI 搜索技能，支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。

#### 配置文件

```
skills/baidu-search/scripts/config.json
```

从示例文件复制：

```bash
cp skills/baidu-search/scripts/config.json.example skills/baidu-search/scripts/config.json
```

#### 配置内容

```json
{
  "api_key": "你的API Key",
  "default_max_results": 10,
  "safe_search": false
}
```

#### 获取 API Key

1. 访问 [百度千帆平台](https://console.bce.baidu.com/qianfan/ais/console/onlineService)
2. 注册并登录百度智能云账号
3. 进入「千帆大模型平台」→「在线服务」
4. 找到「AI 搜索」服务，开通
5. 在「应用接入」→「API Key」页面创建密钥
6. 复制 API Key，格式为 `bce-v3/ALTAK-xxxxxxxxxxxxxxxx`

> **免费额度**：每天有免费调用，足够个人日常使用。

#### 启用技能

在 Web UI → 技能页面，找到「百度搜索」技能，点击启用。

#### 搜索模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `web_search` | 网页搜索（默认） | 通用信息查询 |
| `baike` | 百度百科 | 概念、人物、事件查询 |
| `miaodong_baike` | 秒懂百科（视频） | 视频形式的知识科普 |
| `ai_chat` | AI 智能搜索生成 | 需要 AI 总结的复杂问题 |

#### 注意事项

- 网页搜索查询最长 72 个字符
- 搜索自动包含当前日期上下文，方便处理时效性查询
- 超出免费额度后按量计费

---

### 3.3 邮箱管理（email）

邮箱技能支持通过 QQ 邮箱和 163 邮箱发送、接收邮件。

> **重要**：邮箱配置使用的是「授权码」而非登录密码。授权码是邮箱专门为第三方客户端生成的安全密码。

#### 配置文件

```
skills/email/scripts/config.json
```

从示例文件复制：

```bash
cp skills/email/scripts/config.json.example skills/email/scripts/config.json
```

#### 配置内容

```json
{
  "default_mailbox": "qq",
  "qq_email": {
    "email": "你的QQ邮箱@qq.com",
    "auth_code": "你的QQ邮箱授权码",
    "imap_server": "imap.qq.com",
    "imap_port": 993,
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465
  },
  "163_email": {
    "email": "你的163邮箱@163.com",
    "auth_password": "你的163邮箱授权密码",
    "pop_server": "pop.163.com",
    "pop_port": 995,
    "smtp_server": "smtp.163.com",
    "smtp_port": 465,
    "note": "163 uses POP3 for receiving (not IMAP due to security restrictions)"
  },
  "last_check_time": null
}
```

#### QQ 邮箱授权码获取步骤

1. 登录 [QQ 邮箱](https://mail.qq.com/)
2. 点击「设置」→「账户」标签页
3. 向下滚动找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务」
4. 开启「IMAP/SMTP 服务」（如果未开启）
5. 点击「生成授权码」
6. 按提示用手机发送短信验证
7. 获得 16 位授权码（如 `abcdefghijklmnop`）
8. 将授权码填入 `auth_code` 字段

> **注意**：授权码只显示一次，请妥善保存。如果忘记可以重新生成。

#### 163 邮箱授权密码获取步骤

1. 登录 [163 邮箱](https://mail.163.com/)
2. 点击「设置」→「POP3/SMTP/IMAP」
3. 开启「POP3/SMTP 服务」
4. 按提示设置「客户端授权密码」
5. 将授权密码填入 `auth_password` 字段

> **注意**：163 邮箱由于安全限制，收件使用 POP3 协议（而非 IMAP），发件使用 SMTP。

#### 协议和端口说明

| 邮箱 | 收件协议 | 收件服务器 | 收件端口 | 发件服务器 | 发件端口 |
|------|----------|-----------|----------|-----------|----------|
| QQ | IMAP（SSL） | imap.qq.com | 993 | smtp.qq.com | 465 |
| 163 | POP3（SSL） | pop.163.com | 995 | smtp.163.com | 465 |

#### 默认邮箱设置

`default_mailbox` 字段决定默认使用哪个邮箱：
- `"qq"` — 默认使用 QQ 邮箱
- `"163"` — 默认使用 163 邮箱

你也可以只配置其中一个邮箱，将 `default_mailbox` 设为对应值即可。

#### 启用技能

在 Web UI → 技能页面，找到「邮件管理」技能，点击启用。

#### 支持的功能

| 功能 | 说明 |
|------|------|
| 发送邮件 | 支持纯文本和带附件邮件 |
| 接收邮件 | 获取最新邮件列表 |
| 检查新邮件 | 检查指定天数内的新邮件 |
| 切换邮箱 | 运行时可指定使用 QQ 或 163 邮箱 |

---

### 3.4 地图导航（map）

地图技能基于高德地图 API，支持路线规划（驾车、步行、骑行、公交）和 POI 搜索（景点、餐厅等）。

#### 配置文件

```
skills/map/scripts/config.json
```

从示例文件复制：

```bash
cp skills/map/scripts/config.json.example skills/map/scripts/config.json
```

#### 配置内容

```json
{
  "amap_key": "你的高德地图API Key"
}
```

#### 获取高德地图 API Key

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册并登录账号
3. 进入「控制台」→「应用管理」→「我的应用」
4. 点击「创建新应用」，填写应用名称和类型
5. 在应用下点击「添加 Key」
6. 服务平台选择「Web 服务」
7. 提交后获取 Key（32 位字符串）
8. 将 Key 填入 `amap_key` 字段

> **免费额度**：高德地图 Web 服务 API 每天有 5000 次免费调用额度。

#### 启用技能

在 Web UI → 技能页面，找到「地图导航」技能，点击启用。

#### 支持的功能

| 功能 | 说明 |
|------|------|
| 驾车路线 | 起终点驾车导航，含距离和时间 |
| 步行路线 | 步行导航 |
| 公交路线 | 公交/地铁换乘方案 |
| 景点搜索 | 搜索城市景点（风景名胜 + 博物馆） |
| 餐厅搜索 | 搜索城市餐厅（排除快餐） |
| 通用 POI 搜索 | 按关键词搜索任意地点 |

---

### 3.5 天气查询（weather）

天气查询技能基于 wttr.in 免费服务，无需配置任何 API Key。

#### 无需配置

此技能开箱即用，无需创建配置文件。

#### 启用技能

在 Web UI → 技能页面，找到「天气查询」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 当前天气 | `python skills/weather/scripts/weather.py query 北京` |
| 天气预报 | `python skills/weather/scripts/weather.py forecast 上海` |
| 简洁模式 | 添加 `--brief` 参数 |
| JSON 输出 | 添加 `--json` 参数 |
| 指定语言 | 添加 `--lang zh` 参数 |

---

### 3.6 AI 图片生成（image-gen）

AI 图片生成技能基于 ModelScope API，支持文生图、LoRA 风格叠加。

#### 配置文件

```
skills/image-gen/scripts/config.json
```

从示例文件复制：

```bash
cp skills/image-gen/scripts/config.json.example skills/image-gen/scripts/config.json
```

#### 配置内容

```json
{
  "api_token": "你的 ModelScope Token"
}
```

#### 获取 Token （需要绑定阿里云账号）

1. 访问 [ModelScope 控制台](https://modelscope.cn/my/myaccesstoken)
2. 注册并登录账号
3. 创建 Access Token
4. 将 Token 填入 `api_token` 字段

#### 启用技能

在 Web UI → 技能页面，找到「AI 图片生成」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 文生图 | `generate --prompt "A golden cat" --output cat.jpg` |
| 指定尺寸 | `generate --prompt "壁纸" --size 1920x1080` |
| LoRA 风格 | `generate --prompt "风景" --lora "repo/model"` |
| 查询任务 | `status --task-id TASK_ID` |

#### 频道联动

在频道会话（飞书/QQ/钉钉等）中，图片生成后会自动通过 `send_media` 工具发送到对应频道，用户无需手动下载。

---

### 3.7 网页设计与部署（web-design）

网页设计技能可生成精美单页 HTML 并一键部署到 Cloudflare Pages。支持使用 Tailwind CSS、Chart.js、Font Awesome 等现代前端技术栈。

#### 配置文件

```
skills/web-design/scripts/config.json
```

从示例文件复制：

```bash
cp skills/web-design/scripts/config.json.example skills/web-design/scripts/config.json
```

#### 配置内容

```json
{
  "api_token": "你的 Cloudflare API Token"
}
```

> **注意**：`account_id` 无需手动配置，部署脚本会通过 API 自动获取。

#### 获取 Cloudflare API Token

1. 访问 [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
2. 登录你的 Cloudflare 账号
3. 点击「Create Token」（创建令牌）
4. 选择「Create Custom Token」（创建自定义令牌）
5. 配置令牌：
   - **Token name**：随意命名（如 `CountBot Pages Deploy`）
   - **Permissions**（权限）：
     - Account → Cloudflare Pages → Edit
   - **Account Resources**（账户资源）：
     - Include → All accounts（或选择特定账户）
6. 点击「Continue to summary」→「Create Token」
7. 复制生成的 Token（格式类似 `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）
8. 将 Token 填入 `config.json` 的 `api_token` 字段

> **重要说明**：
> - `account_id` 无需手动配置，部署脚本会通过 API 自动获取
> - Token 只显示一次，请妥善保存
> - 如果 Token 泄露，请立即在 Cloudflare Dashboard 中撤销并重新创建

#### 启用技能

在 Web UI → 技能页面，找到「网页设计与部署」技能，点击启用。

> **免费额度**：Cloudflare Pages 提供免费托管服务，每月 500 次构建，无限带宽。

#### 技术栈与设计规范

网页设计技能使用以下技术栈：

| 技术 | 用途 | CDN 引入 |
|------|------|----------|
| Tailwind CSS | 样式框架 | `https://cdn.tailwindcss.com` |
| Chart.js | 数据可视化 | `https://cdn.jsdelivr.net/npm/chart.js` |
| Font Awesome | 图标库 | `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css` |
| Animate.css | 动画效果（可选） | `https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css` |
| AOS | 滚动动画（可选） | `https://unpkg.com/aos@2.3.4/dist/aos.js` |

**设计约束**：
- 不使用紫色渐变配色
- 不使用 Emoji 表情符号，统一使用 Font Awesome 图标
- 布局灵活运用 Tailwind CSS 的 Grid/Flex 布局
- 确保响应式设计，支持移动端和桌面端

#### 支持的功能

| 功能 | 命令示例 | 说明 |
|------|----------|------|
| 部署单个 HTML | `deploy index.html --project my-site` | 自动作为 index.html 部署 |
| 部署整个目录 | `deploy ./dist --project my-site` | 部署包含多个文件的网站 |
| 部署到预览分支 | `deploy ./dist --project my-site --branch preview` | 创建预览环境 |
| 查看项目列表 | `list` | 列出所有已部署的项目 |
| 查看部署历史 | `deployments --project my-site` | 查看指定项目的部署记录 |

#### 项目命名规则

**重要**：为避免项目名冲突，系统采用以下命名策略：

- **用户未指定项目名**：自动生成「8位随机前缀 + 内容名称」
  - 示例：`a3f8k2m1-product-intro`、`x7b9d4e2-annual-report`
- **用户明确指定项目名**：使用指定的项目名
  - 示例：用户说"部署到 my-website 项目"，则使用 `my-website`

随机前缀使用小写字母和数字混合，确保每次部署都是新项目，不会覆盖已有内容。

#### 使用场景示例

**场景 1：生成产品介绍页**

用户：「帮我做一个产品介绍页，产品名叫 SmartHome」

AI 会：
1. 根据需求设计独特的页面风格
2. 生成 HTML 文件并保存到本地（如 `smarthome-intro.html`）
3. 询问是否需要部署到线上

**场景 2：部署到线上（首次）**

用户：「部署到线上」

AI 会执行：
```bash
python3 skills/web-design/scripts/deploy.py deploy smarthome-intro.html --project a3f8k2m1-smarthome-intro
```

部署成功后返回访问地址：`https://a3f8k2m1-smarthome-intro.pages.dev`

**场景 3：更新已有项目**

用户：「更新 my-website 项目」

AI 会执行：
```bash
python3 skills/web-design/scripts/deploy.py deploy updated-page.html --project my-website
```

这会更新已有的 `my-website` 项目，而不是创建新项目。

#### 部署限制

- 单文件大小限制：10MB
- 项目名会作为子域名：`<project>.pages.dev`
- 首次部署会自动创建项目
- 纯 Python 标准库实现，无需 Node.js 或 wrangler CLI

#### 常见问题

**Q: 部署失败提示 "Unauthorized"**  
A: 检查 API Token 是否正确，确认权限包含 Cloudflare Pages Edit

**Q: 如何删除已部署的项目？**  
A: 登录 Cloudflare Dashboard → Pages，手动删除项目

**Q: 可以使用自定义域名吗？**  
A: 可以，在 Cloudflare Pages 项目设置中添加自定义域名

**Q: 部署的网页可以包含后端逻辑吗？**  
A: 此技能专注于静态单页 HTML，如需后端可使用 Cloudflare Workers 或 Pages Functions

---

### 3.8 新闻查询（news）

新闻查询技能基于公开 RSS 源和网页抓取，无需配置任何 API Key。

#### 无需配置

此技能开箱即用，无需创建配置文件。

#### 启用技能

在 Web UI → 技能页面，找到「新闻查询」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 热点新闻 | `python skills/news/scripts/news.py hot` |
| 分类查询 | `python skills/news/scripts/news.py category --cat tech` |
| AI 资讯 | `python skills/news/scripts/news.py category --cat ai` |
| AI 社区 | `python skills/news/scripts/news.py category --cat ai-community` |
| 关键词搜索 | `python skills/news/scripts/news.py hot --keyword AI` |
| 查看新闻源 | `python skills/news/scripts/news.py sources` |

支持分类：热点、时政、财经、科技、社会、国际、体育、娱乐、AI 技术、AI 社区。

---

### 3.9 定时任务管理（cron-manager）

定时任务管理技能通过命令行管理 CountBot 的定时任务系统，支持完整的 CRUD 操作和会话数据管理。

#### 无需配置

此技能开箱即用，无需创建配置文件。脚本路径：`skills/cron-manager/scripts/cron_manager.py`。

#### 启用技能

在 Web UI → 技能页面，找到「定时任务管理」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 创建任务 | `python3 skills/cron-manager/scripts/cron_manager.py create --name "每日天气" --schedule "0 9 * * *" --message "查询天气"` |
| 列出任务 | `python3 skills/cron-manager/scripts/cron_manager.py list` |
| 修改任务 | `python3 skills/cron-manager/scripts/cron_manager.py update <job_id> --schedule "0 */2 * * *"` |
| 删除任务 | `python3 skills/cron-manager/scripts/cron_manager.py delete <job_id>` |
| 启用/禁用 | `python3 skills/cron-manager/scripts/cron_manager.py enable/disable <job_id>` |
| 手动触发 | `python3 skills/cron-manager/scripts/cron_manager.py run <job_id>` |
| 查看会话消息 | `python3 skills/cron-manager/scripts/cron_manager.py messages <job_id>` |
| 清理会话 | `python3 skills/cron-manager/scripts/cron_manager.py clean <job_id> --keep 10` |

#### 注意事项

- job_id 支持前缀匹配，输入前几位即可
- 创建任务时如需推送结果到渠道，需同时指定 `--channel`、`--chat-id` 和 `--deliver`
- 通过渠道对话时，系统会自动提供当前渠道信息，可自动设置投递目标

---

### 3.10 浏览器自动化（agent-browser）

浏览器自动化技能基于 agent-browser CLI，支持网页导航、表单填写、截图、数据提取等操作。

#### 安装

需要手动安装 agent-browser CLI：

```bash
npm install -g agent-browser
```

#### 无需配置文件

安装完成后即可使用，无需创建配置文件。

#### 启用技能

在 Web UI → 技能页面，找到「浏览器自动化」技能，点击启用。

#### 支持的功能

| 功能 | 命令示例 |
|------|----------|
| 打开网页 | `agent-browser open https://example.com` |
| 获取元素快照 | `agent-browser snapshot -i` |
| 点击元素 | `agent-browser click @e1` |
| 填写表单 | `agent-browser fill @e2 "text"` |
| 截图 | `agent-browser screenshot` |
| 获取文本 | `agent-browser get text @e1` |
| 保存/加载状态 | `agent-browser state save/load auth.json` |

#### 注意事项

- 需要 Node.js 环境
- 元素引用（`@e1`）在页面变化后失效，需重新 snapshot
- 支持 iOS 模拟器（需 macOS + Xcode + Appium）
- 详细文档见 `skills/agent-browser/SKILL.md`

---

## 4. 功能开通状态检查

### 4.0 远程访问安全配置

如果你需要通过局域网或公网 IP（非 `127.0.0.1`）访问 CountBot，系统会自动启用远程访问认证保护。

#### 工作原理

- 本地访问（`127.0.0.1` / `::1`）：无需任何认证，零摩擦
- 远程访问（如 `192.168.x.x:8000`）：首次访问时引导设置管理员账号密码，之后每次远程访问需要登录

#### 首次远程访问

1. 通过远程 IP 访问 CountBot（如 `http://192.168.1.100:8000`）
2. 系统自动跳转到登录页面，显示「首次设置」模式
3. 设置管理员账号和密码（密码要求：至少 8 位，必须包含大写字母、小写字母和数字）
4. 设置完成后自动登录

#### 密码管理

- 修改密码：通过本地访问或已登录状态调用 `POST /api/auth/change-password`
- 忘记密码：通过本地访问（`http://127.0.0.1:8000`）进入系统修改
- Session 有效期：24 小时，应用重启后需重新登录

#### 渠道不受影响

Telegram、钉钉、飞书、QQ、微信等渠道使用主动连接模式，不经过 HTTP 认证中间件，完全不受远程认证影响。

详细说明参见 [认证文档](./auth.md)。

配置完成后，可以通过以下方式验证各项功能是否正常工作。

### 4.1 通过 Web UI 检查

1. 启动 CountBot：`python start_app.py`
2. 打开 `http://localhost:8000`
3. 检查以下页面：
   - **设置页面**：确认提供商连接状态显示「已连接」
   - **技能页面**：确认已启用的技能显示为「已启用」状态
   - **聊天页面**：发送一条消息，确认 AI 正常回复

### 4.2 通过 API 检查

#### 检查已注册的工具

```bash
curl http://localhost:8000/api/tools/list | python -m json.tool
```

返回结果中应包含你期望的工具，包括 `web_fetch`（网页抓取）等内置工具。

#### 检查技能列表

```bash
curl http://localhost:8000/api/skills | python -m json.tool
```

返回所有已安装的技能及其启用状态。

#### 检查渠道状态

```bash
curl http://localhost:8000/api/channels/status | python -m json.tool
```

返回各渠道的连接状态。已配置并启用的渠道应显示为 `connected`。

#### 检查系统健康

```bash
curl http://localhost:8000/api/health
```

返回 `{"status": "ok"}` 表示后端服务正常运行。

### 4.3 功能验证清单

| 功能 | 验证方法 | 预期结果 |
|------|----------|----------|
| 大模型 API | 在聊天页面发送「你好」 | AI 正常回复 |
| 图片分析 | 发送一张图片并说「分析这张图」 | 返回图片描述 |
| 图片生成 | 说「帮我画一只猫」 | 生成图片并发送（频道）或返回路径（网页） |
| 百度搜索 | 说「搜索一下今天的新闻」 | 返回搜索结果 |
| 邮箱管理 | 说「检查我的新邮件」 | 返回邮件列表或提示无新邮件 |
| 地图导航 | 说「从北京到上海怎么走」 | 返回路线规划 |
| 天气查询 | 说「北京今天天气怎么样」 | 返回天气信息 |
| 新闻查询 | 说「今天有什么新闻」 | 返回最新新闻列表 |
| 网页设计 | 说「帮我做一个产品介绍页」 | 生成 HTML 页面 |
| 定时任务管理 | 说「每天早上9点提醒我看天气」 | 创建定时任务 |
| 浏览器自动化 | 说「打开百度首页并截图」 | 打开网页并返回截图 |
| 飞书/钉钉等 | 在对应平台 @ 机器人发消息 | 机器人正常回复 |

### 4.4 常见问题排查

| 问题 | 可能原因 | 解决方法 |
|------|----------|----------|
| AI 不回复 | API Key 未配置或无效 | 检查设置页面提供商配置 |
| 技能调用失败 | 技能 config.json 未创建 | 从 config.json.example 复制并填写 |
| 渠道连接失败 | 凭证错误或依赖未安装 | 检查凭证，运行 `pip install` 安装依赖 |
| 邮件发送失败 | 使用了登录密码而非授权码 | 按照 3.3 节步骤获取授权码 |
| 163 收件失败 | IMAP 被安全限制 | 163 使用 POP3 协议，确认配置正确 |
| 图片生成超时 | 网络问题或模型繁忙 | 重试，或通过 `status --task-id` 查询任务状态 |
| 图片未发送到频道 | 非频道会话 | `send_media` 仅支持飞书/QQ/钉钉等频道会话 |
