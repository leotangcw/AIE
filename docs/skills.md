# 技能系统 (Skills)

> CountBot 的可插拔技能插件系统，支持内置技能和自定义技能的热加载、启用/禁用管理。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [技能结构](#技能结构)
- [核心组件](#核心组件)
  - [Skill](#skill)
  - [SkillsLoader](#skillsloader)
- [技能加载机制](#技能加载机制)
- [技能管理 API](#技能管理-api)
- [内置技能](#内置技能)
- [自定义技能开发](#自定义技能开发)
- [配置管理](#配置管理)
- [相关文件](#相关文件)

## 设计理念

1. **Prompt 注入** — 技能以 Markdown 文本注入系统提示词，不依赖特定 LLM 的 Function Calling
2. **Provider 无关** — 技能内容是纯文本，任何 LLM 都能理解
3. **热插拔** — 技能可在运行时启用/禁用，无需重启
4. **两级目录** — 内置技能（`skills/`）和工作空间技能，逻辑隔离
5. **按需加载** — 仅 `always=true` 的技能自动加载，其他技能按需读取

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    SkillsLoader                          │
│                                                          │
│  skills/                    .skills_config.json          │
│  ├── baidu-search/          {"disabled": ["skill-x"]}   │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── cron-manager/                                      │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── email/                                             │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── image-analysis/                                    │
│  │   └── SKILL.md                                       │
│  ├── image-gen/                                         │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── map/                                               │
│  │   └── SKILL.md                                       │
│  ├── news/                                              │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── weather/                                           │
│  │   ├── SKILL.md                                       │
│  │   └── scripts/                                       │
│  ├── web-design/                                        │
│  │   ├── SKILL.md                                       │
│  │   ├── scripts/                                       │
│  │   └── assets/                                        │
│  └── agent-browser/                                     │
│      ├── SKILL.md                                       │
│      ├── references/                                    │
│      └── templates/                                     │
│                                                          │
│  加载流程:                                               │
│  1. 扫描 skills/ 目录                                    │
│  2. 解析 SKILL.md frontmatter                           │
│  3. 读取 .skills_config.json 禁用列表                    │
│  4. 构建技能索引                                         │
│                                                          │
│  注入流程:                                               │
│  ContextBuilder.build_system_prompt()                    │
│    ├─ always=true 技能 → 完整内容注入                    │
│    └─ 其他技能 → 摘要列表（按需 read_file 加载）         │
└─────────────────────────────────────────────────────────┘
```

## 技能结构

每个技能是一个目录，包含 `SKILL.md` 文件和可选的脚本：

```
skills/
└── my-skill/
    ├── SKILL.md           # 技能定义文件（必需）
    └── scripts/           # 辅助脚本（可选）
        └── helper.py
```

### SKILL.md 格式

```markdown
---
name: baidu-search
description: 百度 AI 搜索。支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。
version: 1.0.0
always: false
requirements:
  - requests
---

# 百度 AI 搜索

## 使用说明
当用户需要搜索信息时，使用此技能...

## 工具调用
使用 exec 工具执行 scripts/search.py...
```

### Frontmatter 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ | — | 技能显示名称 |
| `description` | string | ✅ | — | 技能描述 |
| `version` | string | ❌ | `"1.0.0"` | 版本号 |
| `author` | string | ❌ | `""` | 作者 |
| `always` | boolean | ❌ | `false` | 是否自动加载到系统提示词 |
| `requirements` | list[str] | ❌ | `[]` | Python 依赖包列表 |

## 核心组件

### Skill

**文件**: `backend/modules/agent/skills.py`

技能数据类，封装单个技能的元数据和内容。

```python
skill = Skill(
    name="baidu-search",
    path=Path("skills/baidu-search"),
    content="SKILL.md 完整内容",
)
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `get_summary()` | 返回技能摘要（名称 + 描述） |
| `check_requirements()` | 检查 Python 依赖是否已安装 |
| `get_missing_requirements()` | 返回缺失的依赖列表 |

#### 依赖检查

```python
skill.check_requirements()
# → True (所有依赖已安装)
# → False (有缺失依赖)

skill.get_missing_requirements()
# → "requests, beautifulsoup4"
```

### SkillsLoader

**文件**: `backend/modules/agent/skills.py`

技能加载器，管理技能的发现、加载、启用/禁用。

```python
from backend.modules.agent.skills import SkillsLoader

loader = SkillsLoader(
    skills_dir=Path("skills"),
    builtin_skills_dir=Path("skills"),  # 可选
)
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `list_skills()` | 列出所有技能 |
| `load_skill(name)` | 加载技能完整内容 |
| `toggle_skill(name, enabled)` | 启用/禁用技能 |
| `get_always_skills()` | 获取自动加载的技能列表 |
| `build_skills_summary()` | 构建技能摘要（用于系统提示词） |
| `load_skills_for_context(names)` | 加载指定技能内容（用于注入） |
| `add_skill(name, content)` | 创建新技能 |
| `update_skill(name, content)` | 更新技能内容 |
| `delete_skill(name)` | 删除技能 |
| `reload()` | 重新扫描技能目录 |
| `get_stats()` | 获取统计信息 |

## 技能加载机制

### 启动时加载

```
SkillsLoader.__init__()
  │
  ├─ _load_disabled_skills()
  │   └─ 读取 .skills_config.json → disabled set
  │
  └─ _load_all_skills()
      └─ 遍历 skills/ 目录
          ├─ 读取 SKILL.md
          ├─ 解析 frontmatter
          └─ 创建 Skill 对象 → _skills dict
```

### 系统提示词注入

```
ContextBuilder.build_system_prompt()
  │
  ├─ get_always_skills()
  │   └─ 返回 always=true 且已启用的技能名列表
  │
  ├─ load_skills_for_context(always_skills)
  │   └─ 拼接技能完整内容（去除 frontmatter）
  │
  └─ build_skills_summary()
      └─ 返回所有已启用技能的摘要列表
          "- baidu-search: baidu-search — 百度 AI 搜索。支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。"
```

### 按需加载

非 `always` 技能不会注入系统提示词，而是在摘要中列出。Agent 需要时通过 `read_file` 工具读取：

```
Agent: read_file("skills/baidu-search/SKILL.md")
→ ReadFileTool 检测到技能路径
→ 通过 SkillsLoader.load_skill() 加载
→ 返回完整技能内容
```

## 技能管理 API

**文件**: `backend/api/skills.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能 |
| `/api/skills` | POST | 创建新技能 |
| `/api/skills/{name}` | GET | 获取技能详情 |
| `/api/skills/{name}` | PUT | 更新技能 |
| `/api/skills/{name}` | DELETE | 删除技能 |
| `/api/skills/{name}/toggle` | POST | 启用/禁用技能 |

### 列出技能

```
GET /api/skills
```

响应：
```json
[
  {
    "name": "baidu-search",
    "display_name": "baidu-search",
    "description": "百度 AI 搜索。支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。",
    "version": "1.0.0",
    "enabled": true,
    "always": false,
    "requirements_met": true
  }
]
```

### 创建技能

```
POST /api/skills
{
  "name": "my-skill",
  "content": "---\nname: 我的技能\n..."
}
```

### 启用/禁用

```
POST /api/skills/baidu-search/toggle
{
  "enabled": false
}
```

## 内置技能

| 技能 | 说明 | always |
|------|------|--------|
| `baidu-search` | 百度 AI 搜索，支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式 | false |
| `cron-manager` | 定时任务管理，创建、查看、修改、删除定时任务，管理任务会话数据 | false |
| `email` | 通过 QQ 或 163 邮箱发送和接收邮件，支持附件 | false |
| `image-analysis` | 图片分析与识别，支持 OCR、物体识别、场景理解，基于智谱/千问视觉模型 | false |
| `image-gen` | AI 图片生成，基于 ModelScope API，支持文生图、LoRA 风格叠加 | false |
| `map` | 高德地图路线规划与 POI 搜索，支持驾车、步行、骑行、公交 | false |
| `news` | 新闻与资讯查询，支持中文新闻和全球 AI 技术资讯，多分类 | false |
| `weather` | 天气查询与预报，基于 wttr.in 免费服务，无需 API Key | false |
| `web-design` | 网页设计与部署，生成单页 HTML 并部署到 Cloudflare Pages | false |
| `agent-browser` | 浏览器自动化 CLI，支持网页导航、表单填写、截图、数据提取 | false |

## 自定义技能开发

### 步骤

1. 在 `skills/` 目录创建技能文件夹：

```bash
mkdir skills/my-skill
```

2. 创建 `SKILL.md`：

```markdown
---
name: 我的技能
description: 技能描述
version: 1.0.0
always: false
---

# 我的技能

## 使用说明
当用户需要 XXX 时，按以下步骤操作...

## 步骤
1. 使用 exec 工具执行 `python skills/my-skill/scripts/main.py`
2. 解析输出结果
3. 返回给用户
```

3. （可选）添加辅助脚本：

```bash
mkdir skills/my-skill/scripts
# 创建 Python 脚本
```

4. 通过 Web UI 或 API 启用技能

### 最佳实践

- 技能描述要清晰，让 LLM 知道何时使用
- `always=true` 仅用于高频使用的技能，避免系统提示词过长
- 脚本放在 `scripts/` 子目录，保持结构清晰
- 在 `requirements` 中声明 Python 依赖
- 技能内容应包含完整的使用说明和示例

## 配置管理

### .skills_config.json

技能启用/禁用状态存储在工作空间根目录的 `.skills_config.json`：

```json
{
  "disabled": ["skill-x", "skill-y"]
}
```

- 不在 `disabled` 列表中的技能默认启用
- 此文件由 `SkillsLoader` 自动管理
- 可手动编辑

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/agent/skills.py` | Skill + SkillsLoader |
| `backend/api/skills.py` | 技能管理 API |
| `backend/modules/agent/context.py` | 技能注入系统提示词 |
| `backend/modules/tools/filesystem.py` | ReadFileTool 技能加载集成 |
| `.skills_config.json` | 技能启用/禁用配置 |
| `skills/` | 技能目录 |

## 技能配置参考

部分技能需要配置 API Key 才能使用，配置文件位于各技能的 `scripts/config.json`。

### baidu-search

```json
// skills/baidu-search/scripts/config.json
{
  "api_key": "bce-v3/YOUR_API_KEY_HERE"
}
```

API Key 从 [百度千帆平台](https://console.bce.baidu.com/qianfan/ais/console/onlineService) 获取，免费额度 100 次/天。

### email

```json
// skills/email/scripts/config.json
{
  "qq": { "email": "your@qq.com", "auth_code": "授权码" },
  "163": { "email": "your@163.com", "auth_code": "授权码" },
  "default_mailbox": "qq"
}
```

授权码从邮箱设置中获取（QQ 邮箱：设置 > 账户 > IMAP/SMTP；163 邮箱：设置 > POP3/SMTP/IMAP）。

### image-analysis

```json
// skills/image-analysis/scripts/config.json
{
  "default_model": "zhipu",
  "zhipu": { "api_key": "your-zhipu-api-key", "model": "glm-4.6v-flash" },
  "qwen": { "api_key": "your-qwen-api-key", "model": "qwen3-vl-plus" }
}
```

智谱（免费）：https://open.bigmodel.cn/ ；千问：https://help.aliyun.com/zh/model-studio/get-api-key

### image-gen

```json
// skills/image-gen/scripts/config.json
{
  "api_token": "YOUR_MODELSCOPE_TOKEN"
}
```

Token 从 [ModelScope 控制台](https://modelscope.cn/my/myaccesstoken) 获取。默认使用 `Tongyi-MAI/Z-Image-Turbo` 模型。

### map

```json
// skills/map/scripts/config.json
{
  "amap_key": "YOUR_AMAP_KEY"
}
```

高德地图 API Key 从 [高德开放平台](https://lbs.amap.com/) 获取。

### news

无需配置，免费使用。基于公开 RSS 源和网页抓取，支持中文新闻（热点/时政/财经/科技/社会/国际/体育/娱乐）和全球 AI 资讯（AI 技术/AI 社区）。

AI 技术源包括：MIT Tech Review、OpenAI Blog、Google AI Blog、DeepMind Blog、Latent Space、Interconnects、One Useful Thing、KDnuggets。

AI 社区源包括：AI News Daily、Sebastian Raschka、Hacker News、Product Hunt。

### weather

无需配置，免费使用。基于 wttr.in 服务。

### cron-manager

无需配置。通过 REST API 管理定时任务，支持创建、修改、删除、启用/禁用、手动触发，以及会话消息查看、清理、重置。脚本路径: `skills/cron-manager/scripts/cron_manager.py`。

### web-design

```json
// skills/web-design/scripts/config.json
{
  "api_token": "YOUR_CLOUDFLARE_API_TOKEN"
}
```

- `api_token`：从 [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens) 创建，权限需包含 Account > Cloudflare Pages > Edit
- `account_id` 无需配置，脚本通过 API 自动获取

### agent-browser

需要手动安装 agent-browser CLI：

```bash
npm install -g agent-browser
```

无需配置文件。支持浏览器自动化操作：网页导航、表单填写、截图、数据提取等。详见 `skills/agent-browser/SKILL.md`。
