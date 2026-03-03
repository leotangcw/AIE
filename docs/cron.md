# 定时任务系统 (Cron)

> CountBot 的定时任务调度系统，支持 Cron 表达式调度、Agent 执行、渠道投递。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [核心组件](#核心组件)
  - [CronService](#cronservice)
  - [CronScheduler](#cronscheduler)
  - [CronExecutor](#cronexecutor)
- [任务生命周期](#任务生命周期)
- [调度机制](#调度机制)
- [任务执行](#任务执行)
- [渠道投递](#渠道投递)
- [API 接口](#api-接口)
- [数据模型](#数据模型)
- [配置参数](#配置参数)
- [相关文件](#相关文件)

## 设计理念

1. **精确唤醒** — 不使用固定间隔轮询，而是计算最近任务的执行时间精确 sleep
2. **Agent 驱动** — 任务消息由 Agent Loop 处理，可调用任何工具
3. **渠道投递** — 任务结果可投递到指定渠道（Telegram、钉钉等）
4. **数据库持久化** — 任务定义存储在 SQLite，重启后自动恢复
5. **动态调度** — 任务增删改后自动重新计算调度

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Cron 系统                              │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  CronService │    │ CronScheduler│                   │
│  │  (CRUD)      │◄──►│  (调度)      │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         │ SQLite            │ 定时触发                    │
│         ▼                   ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │   CronJob    │    │ CronExecutor │                   │
│  │   (模型)     │    │  (执行)      │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                    ┌────────┴────────┐                   │
│                    │   AgentLoop     │                   │
│                    │ process_direct()│                   │
│                    └────────┬────────┘                   │
│                             │                            │
│                    ┌────────┴────────┐                   │
│                    │ ChannelManager  │ (可选投递)         │
│                    │  send_message() │                   │
│                    └─────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### CronService

**文件**: `backend/modules/cron/service.py`

任务服务层，提供 CRUD 操作。

```python
from backend.modules.cron.service import CronService

service = CronService(db=async_session, scheduler=scheduler)
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `add_job(name, schedule, message, ...)` | 创建定时任务 |
| `get_job(job_id)` | 获取任务 |
| `list_jobs(enabled_only=False)` | 列出任务 |
| `update_job(job_id, ...)` | 更新任务 |
| `delete_job(job_id)` | 删除任务 |
| `get_due_jobs()` | 获取到期任务 |
| `validate_schedule(schedule)` | 验证 Cron 表达式 |
| `calculate_next_run(schedule)` | 计算下次运行时间 |
| `get_schedule_description(schedule)` | 获取表达式中文描述 |

#### 创建任务示例

```python
job = await service.add_job(
    name="每日报告",
    schedule="0 9 * * *",          # 每天 9:00
    message="生成今日工作报告并发送",
    enabled=True,
    channel="dingtalk",             # 投递渠道
    chat_id="group_xxx",           # 投递目标
    deliver_response=True,          # 是否投递结果
)
```

### CronScheduler

**文件**: `backend/modules/cron/scheduler.py`

智能调度器，精确按需唤醒。

```python
scheduler = CronScheduler(
    db_session_factory=get_db_session_factory(),
    on_execute=on_cron_execute,  # 执行回调
)
await scheduler.start()
```

#### 调度算法

```
start()
  │
  ├─ _recompute_next_runs()
  │   └─ 遍历所有启用任务，计算 next_run
  │
  └─ _arm_timer()
      │
      ├─ _get_next_wake_time()
      │   └─ 取所有任务中最早的 next_run
      │
      ├─ asyncio.sleep(delay)
      │   └─ 精确等待到下次执行时间
      │
      └─ _on_timer()
          ├─ get_due_jobs()
          ├─ 并发执行到期任务
          └─ _arm_timer() (重新调度)
```

关键特性：
- 不使用固定间隔轮询，而是精确 sleep 到下次任务时间
- 无任务时每 60 秒检查一次
- 任务增删改后通过 `trigger_reschedule()` 重新计算
- 任务过期时立即执行（`delay < 0` 时 `delay = 0`）

#### 并发控制与健壮性

调度器内置了多层保护机制，确保在高并发场景下稳定运行：

| 机制 | 说明 |
|------|------|
| `asyncio.Semaphore(3)` | 最大并发执行数为 3，防止同一时刻大量任务耗尽资源 |
| `_active_jobs` 集合 | 记录正在执行的 job_id，防止同一任务重复执行 |
| `asyncio.wait_for(timeout=300)` | 单个任务最大执行时间 300 秒，超时自动标记失败 |
| `_safe_commit()` | 带重试的数据库提交，应对 SQLite `database is locked` 错误（最多重试 3 次） |
| 独立 db session | 每个任务使用独立的数据库会话，避免会话冲突 |
| `is_job_active(job_id)` | 提供查询接口，手动触发 API 可检查任务是否正在执行 |

##### 并发执行示例

当 8:00 同时有 10 个定时任务到期时：
1. 调度器取出 10 个到期任务
2. 过滤掉 `_active_jobs` 中已在执行的任务
3. 通过 `Semaphore(3)` 控制，最多 3 个任务同时执行
4. 其余任务排队等待信号量释放
5. 每个任务独立 session、独立超时，互不影响

##### 手动触发防重复

`POST /api/cron/jobs/{id}/execute` 在执行前会调用 `scheduler.is_job_active(job_id)` 检查：
- 如果任务正在执行，返回 `409 Conflict`
- 如果任务空闲，正常触发执行

##### 优雅关闭

调度器停止时：
1. 取消定时器
2. 等待所有 `_active_tasks` 完成（最多 30 秒）
3. 超时后强制取消剩余任务

### CronExecutor

**文件**: `backend/modules/cron/executor.py`

任务执行器，调用 Agent Loop 处理任务消息。

```python
executor = CronExecutor(
    agent=agent_loop,
    bus=message_queue,
    session_manager=session_manager,
    channel_manager=channel_manager,
)
```

执行流程：
1. 调用 `AgentLoop.process_direct(message)` 处理任务消息
2. Agent 可调用任何工具（文件、Shell、Web 等）
3. 如果 `deliver_response=True`，将结果发送到指定渠道

## 任务生命周期

```
创建 → 启用 → 等待调度 → 执行 → 更新状态 → 重新调度
                                    │
                                    ├─ 成功: last_status="ok", run_count++
                                    └─ 失败: last_status="error", error_count++
```

### 任务状态字段

| 字段 | 说明 |
|------|------|
| `enabled` | 是否启用 |
| `next_run` | 下次运行时间 |
| `last_run` | 上次运行时间 |
| `last_status` | 上次状态（ok/error/skipped） |
| `last_error` | 上次错误信息 |
| `last_response` | 上次响应（截断到 1000 字符） |
| `run_count` | 成功执行次数 |
| `error_count` | 失败次数 |

## 调度机制

### Cron 表达式

使用标准 5 字段 Cron 表达式（通过 `croniter` 库解析）：

```
┌───────────── 分钟 (0-59)
│ ┌───────────── 小时 (0-23)
│ │ ┌───────────── 日 (1-31)
│ │ │ ┌───────────── 月 (1-12)
│ │ │ │ ┌───────────── 星期 (0-6, 0=周日)
│ │ │ │ │
* * * * *
```

### 常用表达式

| 表达式 | 说明 |
|--------|------|
| `0 9 * * *` | 每天 9:00 |
| `*/30 * * * *` | 每 30 分钟 |
| `0 9 * * 1-5` | 工作日 9:00 |
| `0 0 1 * *` | 每月 1 日 0:00 |
| `0 */2 * * *` | 每 2 小时 |

### 中文描述

`CronService.get_schedule_description()` 将表达式转换为中文：

```python
service.get_schedule_description("0 9 * * *")
# → "在第 0 分钟 在 9 点"

service.get_schedule_description("*/30 * * * *")
# → "每 30 分钟 每小时"
```

## 任务执行

### 执行流程

```
CronScheduler._on_timer()
  │
  ├─ CronService.get_due_jobs()
  │   └─ SELECT * FROM cron_jobs WHERE enabled=1 AND next_run <= now()
  │
  ├─ 过滤 _active_jobs（防止重复执行）
  │
  ├─ 为每个任务创建 asyncio.Task → _execute_job_safe()
  │   │
  │   └─ _execute_job_safe(job):
  │       ├─ async with semaphore (最多 3 并发)
  │       ├─ 加入 _active_jobs
  │       ├─ 独立 db session
  │       ├─ asyncio.wait_for(timeout=300s)
  │       │   └─ _execute_job(job, service)
  │       │       ├─ on_execute(job_id, message, channel, chat_id, deliver_response)
  │       │       │   └─ CronExecutor.execute()
  │       │       │       └─ AgentLoop.process_direct(message)
  │       │       ├─ 更新 job 状态 (last_run, last_status, run_count)
  │       │       ├─ 计算 next_run
  │       │       └─ _safe_commit (带重试)
  │       └─ 移出 _active_jobs
  │
  └─ _arm_timer() (重新调度)
```

### 错误处理

- 任务执行失败时记录 `last_error` 和 `error_count`
- 失败后仍然计算下次运行时间（不会禁用任务）
- 如果 Cron 表达式无效导致无法计算下次时间，自动禁用任务
- 任务超时（默认 300 秒）后自动标记为 `error`，记录超时信息
- 数据库写入使用 `_safe_commit()` 带重试机制，应对 SQLite 并发锁

## 渠道投递

当任务配置了 `channel` 和 `deliver_response=True` 时，执行结果会发送到指定渠道：

```python
job = await service.add_job(
    name="天气播报",
    schedule="0 8 * * *",
    message="查询今天的天气并生成播报",
    channel="telegram",
    chat_id="123456789",
    deliver_response=True,
)
```

投递流程：
1. Agent 处理任务消息，生成响应
2. CronExecutor 通过 `ChannelManager.send_message()` 发送
3. 消息到达指定渠道的指定聊天

## API 接口

**文件**: `backend/api/cron.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cron/jobs` | GET | 列出所有任务 |
| `/api/cron/jobs` | POST | 创建任务 |
| `/api/cron/jobs/{id}` | GET | 获取任务详情 |
| `/api/cron/jobs/{id}` | PUT | 更新任务 |
| `/api/cron/jobs/{id}` | DELETE | 删除任务 |
| `/api/cron/jobs/{id}/run` | POST | 手动触发执行（正在执行时返回 409） |
| `/api/cron/validate` | POST | 验证 Cron 表达式 |

### 通过聊天管理定时任务

CountBot 提供 `cron-manager` 技能，用户可以通过自然语言对话创建和管理定时任务。AI 会调用 `skills/cron-manager/scripts/cron_manager.py` 脚本执行操作。

示例对话：
- "帮我设置一个每天早上9点查天气的任务" -> AI 调用 create 命令
- "看看我有哪些定时任务" -> AI 调用 list 命令
- "把天气任务改成每2小时执行" -> AI 调用 update 命令
- "删掉新闻任务" -> AI 调用 delete 命令

详见 [技能系统 - cron-manager](skills.md)。

### 创建任务

```
POST /api/cron/jobs
{
  "name": "每日报告",
  "schedule": "0 9 * * *",
  "message": "生成今日工作报告",
  "enabled": true,
  "channel": "dingtalk",
  "chat_id": "group_xxx",
  "deliver_response": true
}
```

### 任务详情

```
GET /api/cron/jobs/{id}
```

响应：
```json
{
  "id": "uuid",
  "name": "每日报告",
  "schedule": "0 9 * * *",
  "message": "生成今日工作报告",
  "enabled": true,
  "channel": "dingtalk",
  "chat_id": "group_xxx",
  "deliver_response": true,
  "last_run": "2026-02-15T09:00:00",
  "next_run": "2026-02-16T09:00:00",
  "last_status": "ok",
  "run_count": 15,
  "error_count": 0,
  "created_at": "2026-02-01T10:00:00"
}
```

## 数据模型

**文件**: `backend/models/cron_job.py`

```python
class CronJob(Base):
    id: str              # UUID
    name: str            # 任务名称
    schedule: str        # Cron 表达式
    message: str         # 任务消息（发送给 Agent）
    enabled: bool        # 是否启用
    channel: str         # 投递渠道（可选）
    chat_id: str         # 投递目标（可选）
    deliver_response: bool  # 是否投递结果
    next_run: datetime   # 下次运行时间
    last_run: datetime   # 上次运行时间
    last_status: str     # 上次状态
    last_error: str      # 上次错误
    last_response: str   # 上次响应
    run_count: int       # 成功次数
    error_count: int     # 失败次数
    created_at: datetime
    updated_at: datetime
```

### 类型定义

**文件**: `backend/modules/cron/types.py`

| 类型 | 说明 |
|------|------|
| `CronJobInfo` | 任务信息数据类（用于 API 响应） |
| `JobExecutionResult` | 执行结果数据类 |
| `CronSchedule` | 调度表达式数据类 |
| `JobStatus` | 任务状态枚举（pending/running/completed/failed/disabled） |

## 配置参数

Cron 系统在应用启动时自动初始化，无需额外配置。任务通过 API 或 Agent 工具创建管理。

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| 调度检查间隔 | CronScheduler | 精确计算 | 无固定间隔，按需唤醒 |
| 空闲检查间隔 | CronScheduler | 60s | 无任务时的检查间隔 |
| 响应截断长度 | CronScheduler | 1000 字符 | `last_response` 最大长度 |
| 最大并发数 | CronScheduler | 3 | 同时执行的最大任务数 |
| 任务超时 | CronScheduler | 300s | 单个任务最大执行时间 |
| 提交重试次数 | CronScheduler | 3 | SQLite 锁定时的重试次数 |
| 优雅关闭超时 | CronScheduler | 30s | 停止时等待活跃任务的最大时间 |

## 内置 Heartbeat 问候任务

CountBot 内置了一个 Heartbeat 主动问候任务，通过复用 Cron 系统实现定时检查和自动问候。

### 工作原理

```
app.py 启动
  │
  ├─ 创建 HeartbeatService 实例（传入性格、用户信息）
  ├─ 传入 CronExecutor（heartbeat_service 参数）
  ├─ ensure_heartbeat_job() → 注册内置 cron job
  │   └─ job_id: "builtin:heartbeat"
  │   └─ schedule: "0 * * * *"（每小时整点，可配置）
  │   └─ message: "__heartbeat__"（特殊标记）
  │
  └─ 每小时整点触发:
      CronScheduler → CronExecutor.execute()
        │
        ├─ 识别 "__heartbeat__" 标记
        ├─ 路由到 HeartbeatService.execute()
        │
        └─ HeartbeatService 执行检查链:
            ├─ 1. 免打扰时段: 不在 quiet_start ~ quiet_end（默认 21:00-08:00）
            ├─ 2. 今日次数: 未达每日上限（默认 2 次）
            ├─ 3. 用户空闲: ≥ idle_threshold_hours（默认 4 小时）
            ├─ 4. 随机概率: 50%（让时间分布自然）
            ├─ 5. LLM 生成问候语（结合性格、用户信息、记忆）
            ├─ 6. 发送到配置的渠道
            └─ 7. 保存到会话历史（role=assistant）
```

### 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | false | 是否启用问候功能 |
| `channel` | "" | 推送渠道（feishu/telegram/dingtalk/wechat/qq） |
| `chat_id` | "" | 推送目标 ID（群组或用户 ID） |
| `schedule` | "0 * * * *" | 检查频率（Cron 表达式） |
| `idle_threshold_hours` | 4 | 用户空闲多久后才可能问候 |
| `quiet_start` | 21 | 免打扰开始时间（小时，北京时间） |
| `quiet_end` | 8 | 免打扰结束时间（小时，北京时间） |
| `max_greets_per_day` | 2 | 每天最多问候次数（1-5） |

### 核心特性

| 特性 | 说明 |
|------|------|
| 固定 Job ID | `builtin:heartbeat`，启动时去重检查避免重复创建 |
| 北京时区 | 所有时间判断使用 UTC+8（`SHANGHAI_TZ`） |
| 问候投递 | 发送到配置的渠道，并保存到会话历史 |
| 上下文感知 | 结合 AI 性格、用户信息、地址、最近记忆生成问候 |
| 会话连贯 | 问候语保存为 assistant 消息，用户回复时能看到上下文 |
| 随机分布 | 50% 概率 + 每日次数限制，避免固定时间发送 |

### 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/agent/heartbeat.py` | HeartbeatService + ensure_heartbeat_job() |
| `backend/modules/cron/executor.py` | CronExecutor（识别 heartbeat 标记并路由） |
| `backend/modules/agent/prompts.py` | HEARTBEAT_GREETING_PROMPT |
| `backend/modules/agent/personalities.py` | 性格描述（get_personality_prompt） |
| `backend/app.py` | 启动时创建 HeartbeatService 并注册 cron job |

## 内置任务保护

所有以 `builtin:` 前缀开头的任务为系统内置任务，受到 API 层和脚本层的双重保护：

### API 保护（`backend/api/cron.py`）

| 操作 | 保护策略 |
|------|----------|
| DELETE | 返回 403 Forbidden，禁止删除 |
| PUT（name/message） | 返回 403 Forbidden，禁止修改名称和消息内容 |
| PUT（enabled/schedule/channel 等） | 允许修改，用于调整运行参数 |

### 脚本保护（`skills/cron-manager/scripts/cron_manager.py`）

所有子命令自动排除 `builtin:` 前缀的任务。`_find_job_id` 在匹配到内置任务时会提示"是内置系统任务，不可操作"并退出。列表命令完全隐藏内置任务。

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/cron/service.py` | 任务服务层（CRUD） |
| `backend/modules/cron/scheduler.py` | 智能调度器 |
| `backend/modules/cron/executor.py` | 任务执行器（含 heartbeat 路由） |
| `backend/modules/cron/types.py` | 类型定义 |
| `backend/models/cron_job.py` | 数据库模型 |
| `backend/api/cron.py` | REST API |
| `backend/app.py` | 生命周期管理（启动/停止调度器 + heartbeat 注册） |
| `backend/modules/agent/heartbeat.py` | HeartbeatService 主动问候服务 |
| `backend/modules/agent/prompts.py` | 提示词模板（含 HEARTBEAT_GREETING_PROMPT） |
| `backend/modules/agent/personalities.py` | AI 性格预设配置 |
| `skills/cron-manager/` | 定时任务管理技能（含会话管理） |
