# AIE 子Agent长程任务管理架构设计

## 1. 概述

### 1.1 目标

重新设计AIE的子Agent长程任务管理系统，实现：

- 主Agent只负责规划和启动任务，不阻塞后续工作
- 子Agent启动后台进程后进入"休眠"状态，由心跳系统定期唤醒做LLM智能分析
- 多个子Agent并行工作，各自独立管理
- 前端实时展示每个子任务的进展（聊天内嵌卡片 + 侧边栏TaskBoard）
- 双模型策略：心跳/子Agent用子模型（低成本），故障时降级到主模型
- 前端模型状态灯显示模型可用性

### 1.2 核心设计原则

- **启动即分离**：子Agent的LLM只负责启动任务，启动后立即释放
- **心跳即分析**：每次心跳唤醒是一次独立的LLM调用，不累积上下文
- **零阻塞**：主Agent spawn 后立即返回，心跳在独立调度循环中运行
- **全持久化**：任务信息全部存DB，重启后可从DB恢复监控

---

## 2. 子Agent生命周期

### 2.1 状态机

```
PENDING → STARTING → RUNNING → SLEEPING ⇄ ANALYZING → COMPLETED / FAILED
                                    ↑          ↓
                                    └──────────┘ (唤醒)
```

| 状态 | 说明 | 触发 |
|------|------|------|
| PENDING | 已创建，等待执行 | spawn 调用 |
| STARTING | 子Agent LLM 正在启动任务 | execute_task |
| RUNNING | 后台进程已启动，正在执行 | start_background 成功 |
| SLEEPING | 等待下次心跳唤醒 | 子Agent标记[TASK_SUCCESS]后 |
| ANALYZING | 心跳正在用LLM分析进展 | 心跳调度器唤醒 |
| COMPLETED | 任务成功完成 | LLM分析确认完成 / 退出码0 |
| FAILED | 任务失败 | 退出码非0 / 卡死 / LLM判断失败 |

### 2.2 生命周期流程

```
1. 主Agent → spawn(type="long_running", task="下载xxx模型")
2. SubagentManager 创建 SubagentTask(PENDING)
3. 子Agent LLM 启动(STARTING)：
   a. 分析任务，决定执行方案
   b. 调用 start_background 启动后台进程
   c. 记录 monitoring_info (pid, log_file, target_dir 等)
   d. 标记 [TASK_SUCCESS] → 退出LLM循环
4. 任务状态 → RUNNING → SLEEPING
5. 心跳调度器按动态频率唤醒：
   a. 读取日志尾部
   b. 调用子模型LLM分析进展
   c. 更新进度 + 推送WS
   d. 计算下次检查时间
6. 后台进程退出 → 心跳检测到 → 最终分析 → COMPLETED/FAILED
```

---

## 3. 心跳调度器 (HeartbeatScheduler)

### 3.1 架构

替换当前基于Cron的心跳，改为独立的 asyncio Task 循环。

```python
class HeartbeatScheduler:
    """独立心跳调度器，不依赖Cron"""

    def __init__(self, subagent_manager, provider, sub_model: str):
        self.subagent_manager = subagent_manager
        self.provider = provider
        self.sub_model = sub_model
        self._task = None  # asyncio.Task

    async def start(self):
        """启动心跳循环"""
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """停止心跳循环"""
        if self._task:
            self._task.cancel()

    async def _loop(self):
        """主循环：每次唤醒一个任务，避免并发LLM调用"""
        while True:
            # 获取所有 SLEEPING 状态的任务，按 next_check_at 排序
            tasks = await self._get_sleeping_tasks()
            if not tasks:
                await asyncio.sleep(30)
                continue

            for task in tasks:
                # 等到该任务的下次检查时间（带30秒抖动）
                wait = max(0, task.next_check_at - datetime.utcnow())
                await asyncio.sleep(wait)

                # 串行唤醒，一次只分析一个
                await self._analyze_task(task)

    async def _analyze_task(self, task: SubagentTask):
        """分析单个任务的进展"""
        task.status = "ANALYZING"
        try:
            # 1. 纯规则检查：进程是否存活
            alive = self._check_pid_alive(task)
            if not alive:
                # 进程已退出，读取完整日志做最终分析
                analysis = await self._llm_analyze(task, final=True)
                if analysis.success:
                    task.status = "COMPLETED"
                    task.progress = 100
                else:
                    task.status = "FAILED"
                    task.error = analysis.summary
                await self._notify_completion(task, analysis)
                return

            # 2. LLM智能分析：读日志尾部
            analysis = await self._llm_analyze(task, final=False)

            # 3. 更新任务状态
            task.progress = analysis.progress
            task.last_analysis = analysis.summary
            await self._notify_progress(task, analysis)

            # 4. 计算下次检查时间（动态频率）
            task.next_check_at = self._calc_next_check(task, analysis)

        except Exception as e:
            logger.error(f"Heartbeat analysis failed for {task.task_id}: {e}")
            # 失败不影响调度，30秒后重试
            task.next_check_at = datetime.utcnow() + timedelta(seconds=30)
        finally:
            if task.status == "ANALYZING":
                task.status = "SLEEPING"
            await self._sync_to_db(task)
```

### 3.2 动态频率策略

```python
def _calc_next_check(self, task, analysis) -> datetime:
    """根据任务状态动态计算下次检查间隔"""
    now = datetime.utcnow()
    elapsed = (now - task.started_at).total_seconds()

    # 刚启动（5分钟内）：每2分钟检查
    if elapsed < 300:
        return now + timedelta(minutes=2)

    # 进度 > 80% 或 LLM 报告即将完成：每1分钟
    if task.progress > 80 or analysis.near_completion:
        return now + timedelta(minutes=1)

    # 进度无变化超过15分钟：每1分钟（可疑状态）
    if task.progress == task.prev_progress and elapsed > 900:
        return now + timedelta(minutes=1)

    # 稳定运行中：每5分钟
    return now + timedelta(minutes=5)
```

### 3.3 LLM分析：滑窗上下文管理

每次唤醒不是全新调用，而是**携带最近 N 次分析历史**，让 LLM 能对比进展变化。

#### 历史存储结构

每个任务维护一个 `analysis_history` 列表，记录最近 5 次分析结果：

```python
# SubagentTask 新增字段
analysis_history: list[dict] = []  # 最近5次分析记录

# 每条记录结构
{
    "time": "2026-03-28T10:05:00Z",      # 分析时间
    "progress": 30,                        # 当时的进度
    "summary": "正在下载第2个文件...",      # 分析结论
    "log_bytes": 45000,                    # 当时日志文件大小
}
```

**滑窗规则**：
- 最多保留 5 条（可配置）
- 每次新分析后追加，超出时丢弃最旧的
- 原始任务目标始终保留（不在滑窗内）

#### 构建分析提示词

```python
async def _llm_analyze(self, task, final=False) -> AnalysisResult:
    """用LLM分析任务进展，携带历史分析供对比"""

    # 读取日志尾部（最多100行）
    log_tail = self._read_log_tail(task, max_lines=100)
    current_log_bytes = self._get_log_size(task)

    # 构建历史分析文本（最近5次）
    history_text = self._format_analysis_history(task.analysis_history)

    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": f"""## 原始任务目标
{task.message}

## 已运行时间
{format_duration(task.started_at)}

## 历史分析记录（最近{len(task.analysis_history)}次，按时间顺序）
{history_text or '（首次分析，无历史记录）'}

## 最新日志（最后100行，日志总大小: {format_bytes(current_log_bytes)}）
```
{log_tail}
```

## {'最终分析（进程已退出）' if final else '当前进展分析'}

请对比历史分析记录，判断：
1. 进展是否有变化（对比上次进度和日志内容）
2. 是否存在停滞（进度无变化+日志内容无新产出）
3. 预估剩余时间

返回JSON。"""}
    ]

    response = await self._call_with_fallback(messages)
    result = self._parse_analysis(response)

    # 追加到历史（滑窗：最多5条）
    task.analysis_history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "progress": result.progress,
        "summary": result.summary,
        "log_bytes": current_log_bytes,
    })
    if len(task.analysis_history) > 5:
        task.analysis_history = task.analysis_history[-5:]

    return result

def _format_analysis_history(self, history: list[dict]) -> str:
    """格式化历史分析记录"""
    if not history:
        return ""
    lines = []
    for i, h in enumerate(history):
        lines.append(
            f"### 第{i+1}次 ({h['time']})\n"
            f"- 进度: {h['progress']}%\n"
            f"- 日志大小: {format_bytes(h.get('log_bytes', 0))}\n"
            f"- 结论: {h['summary']}"
        )
    return "\n\n".join(lines)
```

#### ANALYSIS_SYSTEM_PROMPT

要求LLM返回结构化JSON，并利用历史记录做对比：

```
你是任务进展监控器。每次你会收到：
1. 原始任务目标
2. 历史分析记录（最近几次的进度和结论）
3. 最新日志尾部

你的职责：
- 对比历史记录，判断进展是否有实质变化
- 如果进度和日志都与上次相同，标记为可能停滞
- 给出准确的进度百分比和分析结论

返回JSON格式：
{
  "progress": 45,
  "status": "running",
  "summary": "正在下载第3个模型文件(v3-large.bin)，已下载1.2GB/3.5GB，比上次增加0.3GB",
  "near_completion": false,
  "stuck": false,
  "stuck_reason": null,
  "estimated_remaining_minutes": 15,
  "progress_delta": "+5%",   // 与上次对比的变化
  "log_delta": "日志增加了15行，有新的下载活动"
}
```

#### Token 成本

因为有历史记录，每次调用的 token 会随时间增长到上限后稳定：
- 首次分析: ~1800 tokens（无历史）
- 稳定后: ~2500 tokens（5条历史 × ~140 tokens/条 + 日志1500 + 任务200）
- 最终分析: ~2500 tokens

每次调用token成本有上限，不会无限增长。

---

## 4. 双模型策略

### 4.1 模型角色

| 角色 | 使用场景 | 默认模型 |
|------|---------|---------|
| 主模型 (main) | 主Agent对话、子Agent启动 | 配置中的 `model` |
| 子模型 (sub) | 心跳分析、子Agent重试 | 配置中的 `sub_model` (新增) |

### 4.2 降级逻辑

```python
async def _call_with_fallback(self, messages) -> str:
    """子模型优先，失败降级到主模型"""
    # 尝试子模型
    try:
        result = await self._call_llm(self.sub_model, messages)
        model_health_tracker.report_success("sub")
        return result
    except Exception as e:
        logger.warning(f"Sub-model failed, falling back to main: {e}")
        model_health_tracker.report_failure("sub")

    # 降级到主模型
    try:
        result = await self._call_llm(self.main_model, messages)
        model_health_tracker.report_success("main")
        return result
    except Exception as e:
        model_health_tracker.report_failure("main")
        raise
```

### 4.3 ModelHealthTracker

```python
class ModelHealthTracker:
    """模型健康状态追踪"""

    def __init__(self):
        self.status = {
            "main": {"healthy": True, "last_success": None, "last_failure": None, "failures": 0},
            "sub": {"healthy": True, "last_success": None, "last_failure": None, "failures": 0},
        }

    def report_success(self, model_role: str):
        """报告模型调用成功"""
        self.status[model_role]["healthy"] = True
        self.status[model_role]["last_success"] = datetime.utcnow()
        self.status[model_role]["failures"] = 0
        self._broadcast_status()

    def report_failure(self, model_role: str):
        """报告模型调用失败"""
        self.status[model_role]["failures"] += 1
        self.status[model_role]["last_failure"] = datetime.utcnow()
        # 连续3次失败标记为不健康
        if self.status[model_role]["failures"] >= 3:
            self.status[model_role]["healthy"] = False
        self._broadcast_status()

    async def _broadcast_status(self):
        """通过WS广播模型状态变化"""
        await connection_manager.broadcast(ModelStatusMessage(
            type="model_status",
            models=self.status
        ))

    def get_status(self) -> dict:
        """获取当前模型状态"""
        return {
            k: {
                "healthy": v["healthy"],
                "model_name": v.get("model_name", ""),
            }
            for k, v in self.status.items()
        }
```

### 4.4 配置

在 `Settings` 中新增：

```python
# config.py
sub_model: str = ""  # 子模型名称，为空则与主模型相同
```

---

## 5. 子Agent启动流程改造

### 5.1 _run_agent_task 改造

当前 `_run_agent_task` 对 LONG_RUNNING 类型执行最多50次LLM迭代。改造后：

- LONG_RUNNING 类型子Agent只执行1-3次LLM迭代（启动任务）
- 启动后台进程后，子Agent LLM立即退出
- 后续监控完全由心跳调度器接管

```python
async def _run_agent_task(self, task, handler=None):
    if task.subagent_type == SubagentType.LONG_RUNNING:
        await self._run_long_running_task(task, handler)
    else:
        # 原有逻辑保持不变
        await self._run_standard_agent_task(task, handler)

async def _run_long_running_task(self, task, handler):
    """长时任务：启动即分离"""
    # 1. 构建提示词（强调启动后立即退出）
    system_prompt = self._build_subagent_prompt(task.message, SubagentType.LONG_RUNNING)

    # 2. 注册工具（含 start_background）
    tools = self._build_long_running_tools(task)

    # 3. LLM 执行（最多3轮：规划 → 启动 → 确认）
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task.message},
    ]

    for iteration in range(3):
        # ... 流式调用LLM，执行工具 ...
        if task.monitoring_info:
            # start_background 已调用，进程已启动
            break

    # 4. 检查是否成功启动
    if not task.monitoring_info:
        task.status = "FAILED"
        task.error = "子Agent未能启动后台进程"
        return

    # 5. 转入 SLEEPING 状态，心跳接管
    task.status = "SLEEPING"
    task.last_analysis = "任务已启动，等待首次心跳分析"
    task.next_check_at = datetime.utcnow() + timedelta(minutes=1)  # 1分钟后首次检查

    # 6. 通知前端
    if handler:
        await handler.notify_status("sleeping", progress=5, message="后台进程已启动，心跳监控中")
```

### 5.2 LONG_RUNNING 系统提示词调整

```
你是长时任务启动器。
- 分析任务，决定最佳执行方案
- 使用 start_background 启动耗时命令
- 启动成功后立即标记 [TASK_SUCCESS] 并退出（不需要等待完成）
- 如果启动失败，标记 [TASK_FAILED: 原因]
- 指定 target_dir 让心跳系统监控目标目录变化
- 不要用 exec 阻塞等待
```

---

## 6. 数据模型变更

### 6.1 TaskItem 新增字段

```python
class TaskItem(Base):
    # ... 现有字段 ...

    # 心跳分析相关
    last_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # LLM分析结论
    analysis_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: 最近5次分析记录
    next_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # 下次心跳时间
    check_interval: Mapped[int] = mapped_column(Integer, default=120)  # 当前检查间隔(秒)
    wake_count: Mapped[int] = mapped_column(Integer, default=0)  # 被心跳唤醒次数
    prev_progress: Mapped[int] = mapped_column(Integer, default=0)  # 上次进度（用于检测停滞）
```

### 6.2 SubagentTask 新增字段

```python
class SubagentTask:
    # ... 现有字段 ...

    # 心跳分析
    last_analysis: str = ""  # 上次LLM分析结论
    analysis_history: list[dict] = []  # 最近5次分析记录（滑窗）
    next_check_at: datetime = None  # 下次检查时间
    check_interval: int = 120  # 检查间隔(秒)
    wake_count: int = 0  # 唤醒次数
    prev_progress: int = 0  # 上次进度
```

---

## 7. 重启恢复

### 7.1 问题

当前架构重启后 SubagentManager.tasks 为空，所有后台进程失去监控。

### 7.2 方案

启动时从DB加载 SLEEPING/RUNNING 状态的 TaskItem，恢复到 SubagentManager：

```python
async def recover_tasks(self):
    """从DB恢复未完成的任务"""
    db = AsyncSessionLocal()
    try:
        result = await db.execute(
            select(TaskItem).where(
                TaskItem.status.in_(["running", "sleeping"])
            )
        )
        items = result.scalars().all()

        for item in items:
            task = SubagentTask(
                task_id=item.id,  # 用DB的ID作为task_id
                label=item.title,
                message=item.description,
                session_id=item.session_id,
                subagent_type=SubagentType.LONG_RUNNING,
            )
            task.status = item.status  # "running" 或 "sleeping"
            task.progress = item.progress
            task.started_at = item.started_at
            task.monitoring_info = json.loads(item.monitoring_info or "{}")
            task.last_analysis = item.last_analysis or ""
            task.next_check_at = item.next_check_at
            task.wake_count = item.wake_count or 0
            task.task_board_item_id = item.id

            # 重建通知处理器
            handler = task_notification_manager.create_handler(task.task_id, task.label)
            task._notification_handler = handler

            self.tasks[task.task_id] = task
            logger.info(f"Recovered task: {task.task_id} (status={item.status})")
    finally:
        await db.close()
```

心跳调度器启动时，这些恢复的任务会自动按 next_check_at 排队等待检查。

---

## 8. WebSocket消息扩展

### 8.1 新增消息类型

```python
# 心跳分析结果推送
class TaskAnalysisMessage(ServerMessage):
    type: str = "task_analysis"
    task_id: str
    progress: int
    summary: str  # LLM分析的文本结论
    elapsed_minutes: int

# 模型状态变化
class ModelStatusMessage(ServerMessage):
    type: str = "model_status"
    models: dict  # {"main": {"healthy": True}, "sub": {"healthy": True}}
```

### 8.2 推送时机

| 事件 | WS消息类型 |
|------|-----------|
| 子Agent创建 | task_created (已有) |
| 子Agent启动后台进程，进入SLEEPING | task_status("sleeping") |
| 心跳LLM分析完成 | task_analysis (新增) |
| 进程退出，最终分析 | task_complete / task_failed (已有) |
| 模型健康状态变化 | model_status (新增) |

---

## 9. 前端设计

### 9.1 模型状态灯

在主界面头部显示两个状态指示灯：

```
[🟢 主模型: claude-sonnet-4-6]  [🟢 子模型: gpt-4o-mini]
```

- 绿灯：最近调用成功
- 红灯：连续3次失败
- 黄灯：最近有失败但未达阈值
- 点击可查看详情（最后成功/失败时间、连续失败次数）

### 9.2 聊天内嵌进度卡片 (SubtaskProgress 改造)

每个 spawn 消息下方嵌入一个进度卡片：

```
┌─────────────────────────────────────────┐
│ 🔄 下载Qwen模型                          │
│ ━━━━━━━━━━━━━━━━━░░░░░░░  45%          │
│ 正在下载第3个模型文件，已下载1.2GB/3.5GB   │
│ 已运行 12分钟 · 预计剩余 15分钟             │
│ 检查模型: 子模型                          │
└─────────────────────────────────────────┘
```

状态变体：
- SLEEPING: 灰色脉动动画 + "等待检查..."
- ANALYZING: 蓝色旋转 + "正在分析进展..."
- COMPLETED: 绿色勾 + 最终结论
- FAILED: 红色叉 + 失败原因

### 9.3 侧边栏 TaskBoard 增强

- RUNNING 区域显示 `task_analysis` 的 summary 文本
- 新增"下次检查"倒计时
- 新增"检查次数"标记
- 点击卡片可展开查看完整分析历史

---

## 10. 文件修改清单

| 文件 | 改动 |
|------|------|
| `backend/modules/agent/subagent.py` | 新增 SLEEPING/ANALYZING 状态支持；拆分 `_run_long_running_task`；新增 `recover_tasks`；SubagentTask 新增字段 |
| `backend/modules/agent/task_board.py` | 新增 `HeartbeatScheduler` 类（替代 cron 心跳）；新增 `_llm_analyze`、`_calc_next_check`、`_read_log_tail` 方法 |
| `backend/models/task_item.py` | 新增 `last_analysis`、`next_check_at`、`check_interval`、`wake_count`、`prev_progress` 字段 |
| `backend/ws/task_notifications.py` | 新增 `TaskAnalysisMessage`、`ModelStatusMessage` |
| `backend/modules/model_health.py` | **新文件** - `ModelHealthTracker` 类 |
| `backend/api/model_health.py` | **新文件** - 模型状态查询API `/api/model-status` |
| `backend/app.py` | 初始化 HeartbeatScheduler + ModelHealthTracker；启动恢复逻辑；新增API路由 |
| `backend/config.py` | 新增 `sub_model` 配置项 |
| `frontend/src/components/chat/SubtaskProgress.vue` | 支持 SLEEPING/ANALYZING 状态；显示 summary 文本 |
| `frontend/src/store/tasks.ts` | 处理 `task_analysis`、`model_status` WS消息 |
| `frontend/src/components/common/ModelStatusLights.vue` | **新文件** - 模型状态灯组件 |

---

## 11. 与现有系统的兼容

### 11.1 非长时任务不受影响

- GENERAL/EXPLORE/RESEARCH 等类型保持原有 _run_standard_agent_task 逻辑
- tool_task 模式完全不受影响
- cron 心跳仍保留用于定时问候等非子Agent场景

### 11.2 渐进迁移

- HeartbeatScheduler 只管理 SLEEPING 状态的 LONG_RUNNING 任务
- 原有的 scan_running_tasks、check_long_waiting_tasks 等保留为安全网
- 可以通过配置开关控制是否启用新心跳系统

---

## 12. Token消耗估算

| 操作 | Token/次 | 频率 | 日成本估算(10任务) |
|------|---------|------|-------------------|
| 子Agent启动 | ~3000 | 1次/任务 | 可忽略 |
| 心跳分析（首次） | ~1800 | 1次/任务 | 可忽略 |
| 心跳分析（稳定后） | ~2500 | 2-5min/次 | ~70K tokens/hour |
| 日志尾部输入 | ~1500 | 含在上面的2500中 | - |
| 历史记录(5条) | ~700 | 含在上面的2500中 | - |
| LLM输出(JSON) | ~250 | 含在上面的2500中 | - |

使用子模型（如 GPT-4o-mini ~$0.15/1M input, $0.6/1M output）：
- 10个任务，平均每3分钟分析一次
- 每小时 ~200次调用 × 2500 tokens = 500K tokens
- 成本: ~$0.20/hour

---

## 13. 实现优先级

### Phase 1: 核心（必须）
1. HeartbeatScheduler + LLM分析
2. 子Agent启动即分离流程
3. 双模型 + 降级逻辑
4. DB字段新增 + 重启恢复

### Phase 2: 体验（重要）
5. WS实时推送 (task_analysis)
6. 前端 SubtaskProgress 改造
7. 动态频率策略
8. 模型状态灯

### Phase 3: 完善（可选）
9. 侧边栏 TaskBoard 增强
10. 分析历史查看
11. 配置开关
