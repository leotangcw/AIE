# 子Agent长程任务心跳架构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现心跳驱动的子Agent长程任务管理系统，子Agent启动后台进程后由心跳定期唤醒做LLM智能分析进展，双模型策略，前端实时展示。

**Architecture:** 新增独立的 HeartbeatScheduler（asyncio循环）替代cron心跳，子Agent的LONG_RUNNING类型改为启动即分离（最多3轮LLM迭代），后续由心跳串行唤醒做LLM分析（携带最近5次分析历史的滑窗上下文）。双模型（子模型优先/主模型降级）+ ModelHealthTracker + 前端状态灯。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, asyncio, Vue 3, Pinia, WebSocket

**Spec:** `docs/superpowers/specs/2026-03-28-subagent-architecture-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/modules/agent/heartbeat_scheduler.py` | **CREATE** - HeartbeatScheduler 核心类：调度循环、LLM分析、PID检测、动态频率、DB同步 |
| `backend/modules/model_health.py` | **CREATE** - ModelHealthTracker：模型健康追踪、降级状态广播 |
| `backend/api/model_health.py` | **CREATE** - 模型状态查询 API 端点 |
| `backend/models/task_item.py` | **MODIFY** - 新增 DB 字段：last_analysis, analysis_history, next_check_at, check_interval, wake_count, prev_progress |
| `backend/modules/agent/subagent.py` | **MODIFY** - SubagentTask 新增字段；拆分 _run_long_running_task；新增 recover_tasks；SLEEPING/ANALYZING 状态支持 |
| `backend/modules/agent/task_board.py` | **MODIFY** - TaskBoardService 新增 update_analysis 方法；TaskHeartbeatService 保留但标注为 legacy |
| `backend/ws/task_notifications.py` | **MODIFY** - 新增 TaskAnalysisMessage、ModelStatusMessage |
| `backend/app.py` | **MODIFY** - 初始化 HeartbeatScheduler + ModelHealthTracker；启动恢复逻辑；注册路由；自动迁移新字段 |
| `backend/modules/config/schema.py` | **MODIFY** - SubAgentConfig 已有 model/provider/api_key/api_base，无需新增 |
| `frontend/src/components/common/ModelStatusLights.vue` | **CREATE** - 模型状态灯组件 |
| `frontend/src/store/tasks.ts` | **MODIFY** - 处理 task_analysis、model_status WS 消息 |
| `frontend/src/components/chat/SubtaskProgress.vue` | **MODIFY** - 支持 SLEEPING/ANALYZING 状态，显示 LLM 分析 summary |

---

## Task 1: DB 字段扩展 (task_item.py + 自动迁移)

**Files:**
- Modify: `backend/models/task_item.py`
- Modify: `backend/app.py` (自动迁移部分)

- [ ] **Step 1: 在 TaskItem 模型中新增字段**

在 `backend/models/task_item.py` 的 `monitoring_info` 字段之后、`# 元数据` 之前，添加：

```python
    # 心跳分析相关
    last_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    analysis_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    next_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=120)
    wake_count: Mapped[int] = mapped_column(Integer, default=0)
    prev_progress: Mapped[int] = mapped_column(Integer, default=0)
```

同时在 `to_dict()` 方法中新增这些字段的导出（analysis_history 需要从 JSON 字符串解析为 list 再导出）。

- [ ] **Step 2: 在 app.py 中添加自动迁移**

在现有 `monitoring_info` 迁移代码块之后添加新字段的 ALTER TABLE 迁移（用 try/except 包裹，忽略 "already exists"）：

```python
    # 自动迁移：心跳分析字段
    for col_name, col_type in [
        ("last_analysis", "TEXT"),
        ("analysis_history", "TEXT"),
        ("next_check_at", "DATETIME"),
        ("check_interval", "INTEGER DEFAULT 120"),
        ("wake_count", "INTEGER DEFAULT 0"),
        ("prev_progress", "INTEGER DEFAULT 0"),
    ]:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text(f"ALTER TABLE task_items ADD COLUMN {col_name} {col_type}"))
                await db.commit()
                logger.info(f"Migration: added {col_name} column to task_items")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                logger.warning(f"Migration check for {col_name}: {e}")
```

- [ ] **Step 3: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/models/task_item.py').read()); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/models/task_item.py backend/app.py
git commit -m "feat: add heartbeat analysis fields to TaskItem model"
```

---

## Task 2: SubagentTask 新增字段 + 状态支持

**Files:**
- Modify: `backend/modules/agent/subagent.py` (SubagentTask class only)

- [ ] **Step 1: 在 SubagentTask.__init__ 中新增字段**

在 `self.monitoring_info` 之后添加：

```python
        # 心跳分析
        self.last_analysis: str = ""
        self.analysis_history: list[dict] = []  # 最近5次分析记录（滑窗）
        self.next_check_at: Optional[datetime] = None
        self.check_interval: int = 120
        self.wake_count: int = 0
        self.prev_progress: int = 0
```

- [ ] **Step 2: 更新 is_completed 属性**

当前 `is_completed` 只检查 `done/failed/cancelled`。SLEEPING 和 ANALYZING 不是完成状态，不需要修改。但需要确认 `status` 字段支持这些新值。

在 `to_dict()` 方法的 `monitoring_info` 之后添加：

```python
            "last_analysis": self.last_analysis,
            "analysis_history": self.analysis_history,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "check_interval": self.check_interval,
            "wake_count": self.wake_count,
            "prev_progress": self.prev_progress,
```

- [ ] **Step 3: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/modules/agent/subagent.py').read()); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/modules/agent/subagent.py
git commit -m "feat: add heartbeat analysis fields to SubagentTask"
```

---

## Task 3: ModelHealthTracker

**Files:**
- Create: `backend/modules/model_health.py`

- [ ] **Step 1: 创建 ModelHealthTracker**

```python
"""模型健康状态追踪器"""

from datetime import datetime
from typing import Any
from loguru import logger


class ModelHealthTracker:
    """追踪主模型和子模型的调用健康状态"""

    def __init__(self):
        self.status: dict[str, dict[str, Any]] = {
            "main": {
                "healthy": True,
                "model_name": "",
                "last_success": None,
                "last_failure": None,
                "failures": 0,
            },
            "sub": {
                "healthy": True,
                "model_name": "",
                "last_success": None,
                "last_failure": None,
                "failures": 0,
            },
        }

    def configure(self, main_model: str, sub_model: str):
        """配置模型名称"""
        self.status["main"]["model_name"] = main_model
        self.status["sub"]["model_name"] = sub_model

    def report_success(self, model_role: str):
        """报告模型调用成功"""
        if model_role not in self.status:
            return
        prev_healthy = self.status[model_role]["healthy"]
        self.status[model_role]["healthy"] = True
        self.status[model_role]["last_success"] = datetime.utcnow().isoformat() + "Z"
        self.status[model_role]["failures"] = 0
        # 状态从 unhealthy 恢复到 healthy 时广播
        if not prev_healthy:
            logger.info(f"Model {model_role} recovered to healthy")
            self._schedule_broadcast()

    def report_failure(self, model_role: str):
        """报告模型调用失败"""
        if model_role not in self.status:
            return
        self.status[model_role]["failures"] += 1
        self.status[model_role]["last_failure"] = datetime.utcnow().isoformat() + "Z"
        if self.status[model_role]["failures"] >= 3:
            self.status[model_role]["healthy"] = False
            logger.warning(f"Model {model_role} marked as unhealthy (3+ consecutive failures)")
            self._schedule_broadcast()

    async def _schedule_broadcast(self):
        """通过WS广播模型状态变化"""
        try:
            from backend.ws.connection import connection_manager
            from backend.ws.task_notifications import ModelStatusMessage
            await connection_manager.broadcast(ModelStatusMessage(
                type="model_status",
                models=self.get_status(),
            ))
        except Exception as e:
            logger.debug(f"Failed to broadcast model status: {e}")

    def get_status(self) -> dict[str, dict[str, Any]]:
        """获取当前模型状态（用于API）"""
        return {
            k: {
                "healthy": v["healthy"],
                "model_name": v["model_name"],
                "last_success": v["last_success"],
                "last_failure": v["last_failure"],
                "consecutive_failures": v["failures"],
            }
            for k, v in self.status.items()
        }
```

- [ ] **Step 2: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/modules/model_health.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/model_health.py
git commit -m "feat: add ModelHealthTracker for dual-model health monitoring"
```

---

## Task 4: WS 消息类型扩展

**Files:**
- Modify: `backend/ws/task_notifications.py`

- [ ] **Step 1: 新增 TaskAnalysisMessage 和 ModelStatusMessage**

在 `SubtaskUpdateMessage` 类之后添加：

```python
class TaskAnalysisMessage(ServerMessage):
    """心跳分析结果推送"""
    type: str = "task_analysis"
    task_id: str
    progress: int
    summary: str
    elapsed_minutes: int
    wake_count: int = 0


class ModelStatusMessage(ServerMessage):
    """模型健康状态变化"""
    type: str = "model_status"
    models: dict = {}
```

- [ ] **Step 2: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/ws/task_notifications.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/ws/task_notifications.py
git commit -m "feat: add TaskAnalysisMessage and ModelStatusMessage WS types"
```

---

## Task 5: TaskBoardService 新增 update_analysis 方法

**Files:**
- Modify: `backend/modules/agent/task_board.py` (TaskBoardService class only)

- [ ] **Step 1: 在 TaskBoardService 中新增 update_analysis 方法**

在现有 `update_monitoring_info` 方法之后添加：

```python
    async def update_analysis(
        self,
        task_id: str,
        progress: int,
        last_analysis: str,
        analysis_history: list[dict],
        next_check_at: datetime,
        prev_progress: int,
        wake_count: int,
    ):
        """更新心跳分析结果"""
        import json
        result = await self.db.execute(
            select(TaskItem).where(TaskItem.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return

        task.prev_progress = prev_progress
        task.progress = progress
        task.last_analysis = last_analysis
        task.analysis_history = json.dumps(analysis_history, ensure_ascii=False)
        task.next_check_at = next_check_at
        task.wake_count = wake_count
        task.updated_at = datetime.utcnow()
        await self.db.commit()
```

需要导入: `from datetime import datetime`（已有）。

- [ ] **Step 2: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/modules/agent/task_board.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/agent/task_board.py
git commit -m "feat: add update_analysis method to TaskBoardService"
```

---

## Task 6: HeartbeatScheduler 核心实现

**Files:**
- Create: `backend/modules/agent/heartbeat_scheduler.py`

这是最核心的文件。包含调度循环、PID检测、LLM分析、动态频率、DB同步。

- [ ] **Step 1: 创建 heartbeat_scheduler.py**

完整实现包含以下组件：

1. **AnalysisResult** 数据类 - LLM分析结果
2. **HeartbeatScheduler** 类:
   - `__init__`: 接收 subagent_manager, provider, sub_model, main_model, model_health_tracker
   - `start()` / `stop()`: asyncio.Task 管理
   - `_loop()`: 主调度循环，串行唤醒 SLEEPING 任务
   - `_get_sleeping_tasks()`: 从 subagent_manager 获取 SLEEPING 任务
   - `_analyze_task(task)`: 单个任务分析流程
   - `_check_pid_alive(task)`: 用 os.kill(pid, 0) 检查进程存活
   - `_llm_analyze(task, final)`: 构建提示词（含滑窗历史），调LLM，解析结果
   - `_call_with_fallback(messages)`: 子模型优先，失败降级到主模型
   - `_read_log_tail(task, max_lines)`: 读取日志文件最后N行
   - `_get_log_size(task)`: 获取日志文件大小
   - `_format_analysis_history(history)`: 格式化历史记录为文本
   - `_parse_analysis(response)`: 解析LLM返回的JSON
   - `_calc_next_check(task, analysis)`: 动态频率计算
   - `_notify_progress(task, analysis)`: WS推送 task_analysis
   - `_notify_completion(task, analysis)`: WS推送 task_complete/task_failed
   - `_sync_to_db(task)`: 同步到 TaskBoardService

3. **ANALYSIS_SYSTEM_PROMPT** 常量

关键实现细节：
- `_llm_analyze` 中使用 `provider.chat_stream` 收集所有 chunks 组成完整响应
- `_parse_analysis` 用正则或 json.loads 从响应中提取JSON（LLM可能包裹在 markdown code block 中）
- `_read_log_tail` 使用 deque + 逐行读取，避免读整个文件
- `_call_with_fallback` 中 model 参数传给 `provider.chat_stream` 的 `model=` 参数

```python
"""心跳调度器 - 独立 asyncio 循环，定期唤醒 SLEEPING 子Agent 做 LLM 分析"""

import asyncio
import json
import os
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

from backend.modules.agent.task_board import TaskBoardService
from backend.database import AsyncSessionLocal
from sqlalchemy import select
from backend.models.task_item import TaskItem


ANALYSIS_SYSTEM_PROMPT = """你是任务进展监控器。每次你会收到：
1. 原始任务目标
2. 历史分析记录（最近几次的进度和结论，用于对比变化）
3. 最新日志尾部

你的职责：
- 对比历史记录，判断进展是否有实质变化
- 如果进度和日志都与上次相同，标记为可能停滞
- 给出准确的进度百分比和分析结论

必须返回JSON格式，不要返回其他内容：
{"progress": 45, "status": "running", "summary": "...", "near_completion": false, "stuck": false, "stuck_reason": null, "estimated_remaining_minutes": 15, "progress_delta": "+5%", "log_delta": "日志增加了15行，有新的下载活动"}"""


@dataclass
class AnalysisResult:
    """LLM分析结果"""
    progress: int = 0
    status: str = "running"
    summary: str = ""
    near_completion: bool = False
    stuck: bool = False
    stuck_reason: Optional[str] = None
    estimated_remaining_minutes: Optional[int] = None
    progress_delta: str = ""
    log_delta: str = ""
    success: bool = False  # 用于最终分析：进程是否成功完成


class HeartbeatScheduler:
    """独立心跳调度器"""

    def __init__(
        self,
        subagent_manager,
        provider,
        main_model: str,
        sub_model: str,
        model_health_tracker,
    ):
        self.subagent_manager = subagent_manager
        self.provider = provider
        self.main_model = main_model
        self.sub_model = sub_model or main_model
        self.model_health_tracker = model_health_tracker
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动心跳循环"""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("[HeartbeatScheduler] Started")

    async def stop(self):
        """停止心跳循环"""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("[HeartbeatScheduler] Stopped")

    async def _loop(self):
        """主调度循环"""
        try:
            while True:
                tasks = self._get_sleeping_tasks()
                if not tasks:
                    await asyncio.sleep(30)
                    continue

                # 按 next_check_at 排序
                tasks.sort(key=lambda t: t.next_check_at or datetime.min)

                for task in tasks:
                    if task.status not in ("sleeping", "SLEEPING"):
                        continue
                    # 等到下次检查时间
                    now = datetime.utcnow()
                    wait = max(0, (task.next_check_at or now) - now)
                    await asyncio.sleep(wait.total_seconds())
                    # 串行唤醒
                    await self._analyze_task(task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[HeartbeatScheduler] Loop error: {e}")

    def _get_sleeping_tasks(self) -> list:
        """获取 SLEEPING 状态的任务"""
        return [
            t for t in self.subagent_manager.tasks.values()
            if t.status in ("sleeping", "SLEEPING") and t.monitoring_info
        ]

    async def _analyze_task(self, task) -> None:
        """分析单个任务"""
        task.status = "ANALYZING"
        task.wake_count += 1
        try:
            # 1. 检查进程存活
            alive = self._check_pid_alive(task)

            if not alive:
                # 最终分析
                analysis = await self._llm_analyze(task, final=True)
                if analysis.success:
                    task.status = "done"
                    task.progress = 100
                else:
                    task.status = "failed"
                    task.error = analysis.summary or "进程异常退出"
                task.completed_at = datetime.utcnow()
                await self._notify_completion(task, analysis)
                # 同步到 DB
                await self._sync_to_board(task, "complete" if analysis.success else "fail")
                return

            # 2. LLM 分析
            analysis = await self._llm_analyze(task, final=False)

            # 3. 更新状态
            task.prev_progress = task.progress
            task.progress = analysis.progress
            task.last_analysis = analysis.summary

            # 4. 推送 WS
            await self._notify_progress(task, analysis)

            # 5. 动态频率
            task.next_check_at = self._calc_next_check(task, analysis)

        except Exception as e:
            logger.error(f"[HeartbeatScheduler] Analysis failed for {task.task_id}: {e}")
            task.next_check_at = datetime.utcnow() + timedelta(seconds=30)
        finally:
            if task.status == "ANALYZING":
                task.status = "SLEEPING"
            await self._sync_analysis_to_db(task)

    def _check_pid_alive(self, task) -> bool:
        """检查进程是否存活"""
        pid = task.monitoring_info.get("pid")
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False

    async def _llm_analyze(self, task, final=False) -> AnalysisResult:
        """用 LLM 分析任务进展（含滑窗历史）"""
        log_tail = self._read_log_tail(task, max_lines=100)
        current_log_bytes = self._get_log_size(task)
        history_text = self._format_analysis_history(task.analysis_history)

        elapsed = ""
        if task.started_at:
            minutes = int((datetime.utcnow() - task.started_at).total_seconds() / 60)
            elapsed = f"{minutes} 分钟"

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": f"""## 原始任务目标
{task.message}

## 已运行时间
{elapsed}

## 历史分析记录（最近{len(task.analysis_history)}次）
{history_text or '（首次分析，无历史记录）'}

## 最新日志（最后100行，总大小: {self._format_bytes(current_log_bytes)}）
```
{log_tail}
```

## {'最终分析（进程已退出，请判断成功还是失败）' if final else '当前进展分析'}

请对比历史记录分析进展，返回JSON。"""},
        ]

        response = await self._call_with_fallback(messages)
        result = self._parse_analysis(response, final=final)

        # 追加到历史滑窗
        task.analysis_history.append({
            "time": datetime.utcnow().isoformat() + "Z",
            "progress": result.progress,
            "summary": result.summary,
            "log_bytes": current_log_bytes,
        })
        if len(task.analysis_history) > 5:
            task.analysis_history = task.analysis_history[-5:]

        return result

    async def _call_with_fallback(self, messages) -> str:
        """子模型优先，失败降级到主模型"""
        # 尝试子模型
        try:
            result = await self._call_llm(self.sub_model, messages)
            self.model_health_tracker.report_success("sub")
            return result
        except Exception as e:
            logger.warning(f"[HeartbeatScheduler] Sub-model failed: {e}")
            self.model_health_tracker.report_failure("sub")

        # 降级到主模型
        try:
            result = await self._call_llm(self.main_model, messages)
            self.model_health_tracker.report_success("main")
            return result
        except Exception as e:
            self.model_health_tracker.report_failure("main")
            raise

    async def _call_llm(self, model: str, messages: list) -> str:
        """调用 LLM 并收集完整响应"""
        chunks = []
        async for chunk in self.provider.chat_stream(
            messages=messages,
            tools=None,
            model=model,
            temperature=0.3,
            max_tokens=500,
        ):
            if chunk.is_content and chunk.content:
                chunks.append(chunk.content)
        return "".join(chunks)

    def _parse_analysis(self, response: str, final=False) -> AnalysisResult:
        """解析 LLM 返回的 JSON"""
        # 尝试提取 JSON（可能在 markdown code block 中）
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # 尝试直接解析
            brace_match = re.search(r'\{.*\}', response, re.DOTALL)
            text = brace_match.group(0) if brace_match else response

        try:
            data = json.loads(text)
            return AnalysisResult(
                progress=max(0, min(100, int(data.get("progress", 0)))),
                status=data.get("status", "running"),
                summary=data.get("summary", ""),
                near_completion=data.get("near_completion", False),
                stuck=data.get("stuck", False),
                stuck_reason=data.get("stuck_reason"),
                estimated_remaining_minutes=data.get("estimated_remaining_minutes"),
                progress_delta=data.get("progress_delta", ""),
                log_delta=data.get("log_delta", ""),
                success=(final and data.get("status") in ("completed", "done", "success")),
            )
        except json.JSONDecodeError:
            logger.warning(f"[HeartbeatScheduler] Failed to parse analysis JSON: {text[:200]}")
            return AnalysisResult(summary=response[:200])

    def _read_log_tail(self, task, max_lines=100) -> str:
        """读取日志文件最后 N 行"""
        log_file = task.monitoring_info.get("log_file") if task.monitoring_info else None
        if not log_file or not os.path.exists(log_file):
            return "(日志文件不存在)"
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = deque(f, maxlen=max_lines)
                return "".join(lines)
        except Exception as e:
            return f"(读取日志失败: {e})"

    def _get_log_size(self, task) -> int:
        """获取日志文件大小"""
        log_file = task.monitoring_info.get("log_file") if task.monitoring_info else None
        if not log_file or not os.path.exists(log_file):
            return 0
        try:
            return os.path.getsize(log_file)
        except OSError:
            return 0

    @staticmethod
    def _format_analysis_history(history: list) -> str:
        """格式化历史分析记录"""
        if not history:
            return ""
        parts = []
        for i, h in enumerate(history):
            log_bytes = h.get("log_bytes", 0)
            size_str = f"{log_bytes / 1024:.1f}KB" if log_bytes > 1024 else f"{log_bytes}B"
            parts.append(
                f"### 第{i+1}次 ({h.get('time', 'N/A')})\n"
                f"- 进度: {h.get('progress', 0)}%\n"
                f"- 日志大小: {size_str}\n"
                f"- 结论: {h.get('summary', 'N/A')}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _format_bytes(size: int) -> str:
        if size > 1024 * 1024:
            return f"{size / (1024*1024):.1f}MB"
        if size > 1024:
            return f"{size / 1024:.1f}KB"
        return f"{size}B"

    def _calc_next_check(self, task, analysis) -> datetime:
        """动态频率：根据任务状态计算下次检查时间"""
        now = datetime.utcnow()
        if not task.started_at:
            return now + timedelta(minutes=2)

        elapsed = (now - task.started_at).total_seconds()

        # 刚启动（5分钟内）
        if elapsed < 300:
            return now + timedelta(minutes=2)

        # 进度高或即将完成
        if task.progress > 80 or analysis.near_completion:
            return now + timedelta(minutes=1)

        # 进度无变化超过15分钟
        if task.progress == task.prev_progress and elapsed > 900:
            return now + timedelta(minutes=1)

        # LLM 报告停滞
        if analysis.stuck:
            return now + timedelta(minutes=1)

        # 稳定运行
        return now + timedelta(minutes=5)

    async def _notify_progress(self, task, analysis) -> None:
        """推送 task_analysis WS 消息"""
        try:
            from backend.ws.connection import connection_manager
            from backend.ws.task_notifications import TaskAnalysisMessage

            elapsed = 0
            if task.started_at:
                elapsed = int((datetime.utcnow() - task.started_at).total_seconds() / 60)

            await connection_manager.broadcast(TaskAnalysisMessage(
                task_id=task.task_id,
                progress=analysis.progress,
                summary=analysis.summary,
                elapsed_minutes=elapsed,
                wake_count=task.wake_count,
            ))
        except Exception as e:
            logger.debug(f"[HeartbeatScheduler] Failed to notify progress: {e}")

    async def _notify_completion(self, task, analysis) -> None:
        """推送 task_complete/task_failed WS 消息"""
        try:
            from backend.ws.task_notifications import task_notification_manager
            handler = task_notification_manager.get_handler(task.task_id)
            if handler:
                if task.status == "done":
                    await handler.notify_complete(analysis.summary)
                else:
                    await handler.notify_failed(task.error or "任务失败")
                task_notification_manager.remove_handler(task.task_id)
        except Exception as e:
            logger.debug(f"[HeartbeatScheduler] Failed to notify completion: {e}")

    async def _sync_to_board(self, task, action: str) -> None:
        """同步任务状态到 TaskBoard"""
        if not task.task_board_item_id:
            return
        try:
            service = await self.subagent_manager._get_task_board_service()
            if service is None:
                return
            if action == "complete":
                await service.complete_task(task.task_board_item_id)
            elif action == "fail":
                await service.fail_task(task.task_board_item_id, error_message=task.error or "Task failed")
        except Exception as e:
            logger.debug(f"[HeartbeatScheduler] Failed to sync to board: {e}")

    async def _sync_analysis_to_db(self, task) -> None:
        """同步分析数据到 DB"""
        if not task.task_board_item_id:
            return
        try:
            service = await self.subagent_manager._get_task_board_service()
            if service:
                await service.update_analysis(
                    task_id=task.task_board_item_id,
                    progress=task.progress,
                    last_analysis=task.last_analysis,
                    analysis_history=task.analysis_history,
                    next_check_at=task.next_check_at,
                    prev_progress=task.prev_progress,
                    wake_count=task.wake_count,
                )
        except Exception as e:
            logger.debug(f"[HeartbeatScheduler] Failed to sync analysis to DB: {e}")
```

- [ ] **Step 2: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/modules/agent/heartbeat_scheduler.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/agent/heartbeat_scheduler.py
git commit -m "feat: implement HeartbeatScheduler with LLM analysis and sliding window"
```

---

## Task 7: 子Agent启动即分离 (subagent.py 改造)

**Files:**
- Modify: `backend/modules/agent/subagent.py`

- [ ] **Step 1: 拆分 _run_agent_task**

将现有 `_run_agent_task` 重命名为 `_run_standard_agent_task`，新增一个 `_run_agent_task` 做分发：

```python
    async def _run_agent_task(self, task: SubagentTask, handler=None) -> None:
        """根据类型分发任务执行"""
        if task.subagent_type == SubagentType.LONG_RUNNING:
            await self._run_long_running_task(task, handler)
        else:
            await self._run_standard_agent_task(task, handler)
```

- [ ] **Step 2: 实现 _run_long_running_task**

在 `_run_agent_task` 之前添加新方法。这个方法是 LONG_RUNNING 类型的专用执行路径，最多 3 轮 LLM 迭代：

```python
    async def _run_long_running_task(self, task: SubagentTask, handler=None) -> None:
        """长时任务：启动后台进程后转入 SLEEPING，由心跳接管"""
        try:
            from backend.modules.tools.registry import ToolRegistry
            from backend.modules.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
            from backend.modules.tools.shell import ExecTool

            system_prompt = self._build_subagent_prompt(task.message, SubagentType.LONG_RUNNING)
            tools = ToolRegistry()
            tools.register(ReadFileTool(self.workspace))
            tools.register(WriteFileTool(self.workspace))
            tools.register(EditFileTool(self.workspace))
            tools.register(ListDirTool(self.workspace))

            # ExecTool 权限
            if self.security_config:
                tools.register(ExecTool(
                    workspace=self.workspace,
                    timeout=self.security_config.command_timeout,
                    allow_dangerous=not self.security_config.dangerous_commands_blocked,
                    restrict_to_workspace=self.security_config.restrict_to_workspace,
                    max_output_length=self.security_config.max_output_length,
                    deny_patterns=self.security_config.custom_deny_patterns,
                    allow_patterns=(
                        self.security_config.custom_allow_patterns
                        if self.security_config.command_whitelist_enabled
                        else None
                    ),
                ))
            else:
                tools.register(ExecTool(workspace=self.workspace))

            # 注册 start_background 工具
            bg_tool = StartBackgroundTool(self.workspace)
            bg_tool._current_task = task
            bg_tool._sync_fn = self._sync_monitoring_to_board
            tools.register(bg_tool)

            try:
                from backend.modules.tools.web import WebSearchTool, WebFetchTool
                tools.register(WebSearchTool())
                tools.register(WebFetchTool())
            except ImportError:
                pass

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.message},
            ]

            # 最多 3 轮迭代（规划 → 启动 → 确认）
            for iteration in range(3):
                content_buffer = ""
                tool_calls_buffer = []

                async for chunk in self.provider.chat_stream(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if chunk.is_content and chunk.content:
                        content_buffer += chunk.content
                    if chunk.is_tool_call and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)

                if tool_calls_buffer:
                    tool_call_dicts = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                        for tc in tool_calls_buffer
                    ]
                    messages.append({"role": "assistant", "content": content_buffer or "", "tool_calls": tool_call_dicts})

                    for tc in tool_calls_buffer:
                        result = await tools.execute(tool_name=tc.name, arguments=tc.arguments)
                        messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})
                        task.add_tool_call(tc.name, tc.arguments, result)
                else:
                    break

                # 检查是否已启动后台进程
                if task.monitoring_info:
                    break

            # 检查是否成功启动
            if not task.monitoring_info:
                task.status = "failed"
                task.error = "子Agent未能启动后台进程"
                await self._sync_task_to_board(task, "fail")
                if handler:
                    await handler.notify_failed(task.error)
                return

            # 转入 SLEEPING 状态
            task.status = "SLEEPING"
            task.last_analysis = "任务已启动，等待首次心跳分析"
            task.next_check_at = datetime.utcnow() + timedelta(minutes=1)

            # 同步到 TaskBoard
            await self._sync_task_to_board(task, "start")  # 确保 DB 记录存在
            # 更新 DB 中的 monitoring_info 和新字段
            await self._sync_monitoring_to_board(task)

            if handler:
                await handler.notify_progress(5, message="后台进程已启动，心跳监控中")

            logger.info(f"[LongRunning] Task {task.task_id} entered SLEEPING, monitoring_info: {task.monitoring_info.get('pid')}")

        except asyncio.CancelledError:
            task.status = "cancelled"
            if handler:
                await handler.notify_failed("任务被取消")
            raise
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            await self._sync_task_to_board(task, "fail")
            if handler:
                await handler.notify_failed(str(e))
            logger.error(f"[LongRunning] Task {task.task_id} failed: {e}")
        finally:
            if handler:
                try:
                    from backend.ws.task_notifications import task_notification_manager
                    # 注意：SLEEPING 状态不移除 handler，保留给心跳使用
                    pass
                except Exception:
                    pass
```

- [ ] **Step 3: 更新 LONG_RUNNING 系统提示词**

在 `subagent_types.py` 的 LONG_RUNNING 提示词中强调"启动即退出"：

```python
        SubagentType.LONG_RUNNING: """你是长时任务启动器。
- 分析任务，决定最佳执行方案
- 使用 start_background 启动耗时命令（下载、编译等）
- 启动成功后立即标记 [TASK_SUCCESS] 并退出（不需要等待完成）
- 如果启动失败，标记 [TASK_FAILED: 原因]
- 务必指定 target_dir 参数，让心跳系统能根据目标目录变化估算进度
- 不要用 exec 阻塞等待长时间运行的命令""",
```

- [ ] **Step 4: 更新 _execute_task_inner 中的重试逻辑**

在 `_execute_task_inner` 中，当 LONG_RUNNING 任务进入 SLEEPING 状态时，不应再重试。在 `if task.status == "done":` 分支之后添加：

```python
                if task.status == "SLEEPING":
                    # 长时任务已启动后台进程，进入心跳监控，退出重试循环
                    break
```

同时，SLEEPING 状态的 finally 块中不应从 running_tasks 中移除（因为心跳还需要它）。

- [ ] **Step 5: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/modules/agent/subagent.py').read()); print('OK')"`

- [ ] **Step 6: Commit**

```bash
git add backend/modules/agent/subagent.py backend/modules/agent/subagent_types.py
git commit -m "feat: implement launch-and-sleep pattern for LONG_RUNNING subagents"
```

---

## Task 8: 任务恢复 (recover_tasks)

**Files:**
- Modify: `backend/modules/agent/subagent.py` (SubagentManager class)

- [ ] **Step 1: 在 SubagentManager 中新增 recover_tasks 方法**

```python
    async def recover_tasks(self):
        """从 DB 恢复未完成的 LONG_RUNNING 任务"""
        from backend.database import AsyncSessionLocal
        from backend.models.task_item import TaskItem
        from sqlalchemy import select
        from backend.ws.task_notifications import task_notification_manager

        db = AsyncSessionLocal()
        try:
            result = await db.execute(
                select(TaskItem).where(
                    TaskItem.status.in_(["running", "sleeping", "SLEEPING", "RUNNING"])
                )
            )
            items = result.scalars().all()

            for item in items:
                task = SubagentTask(
                    task_id=item.id,
                    label=item.title,
                    message=item.description or "",
                    session_id=item.session_id,
                    subagent_type=SubagentType.LONG_RUNNING,
                )
                task.status = item.status.lower()  # normalize
                task.progress = item.progress
                task.started_at = item.started_at
                task.monitoring_info = json.loads(item.monitoring_info or "{}")
                task.last_analysis = item.last_analysis or ""
                task.analysis_history = json.loads(item.analysis_history or "[]")
                task.next_check_at = item.next_check_at
                task.wake_count = item.wake_count or 0
                task.prev_progress = item.prev_progress or 0
                task.task_board_item_id = item.id

                # 重建通知处理器
                handler = task_notification_manager.create_handler(task.task_id, task.label)
                task._notification_handler = handler

                self.tasks[task.task_id] = task
                logger.info(f"[Recovery] Recovered task {task.task_id} (status={task.status}, progress={task.progress}%)")
        except Exception as e:
            logger.error(f"[Recovery] Failed to recover tasks: {e}")
        finally:
            await db.close()
```

- [ ] **Step 2: 语法检查**

- [ ] **Step 3: Commit**

```bash
git add backend/modules/agent/subagent.py
git commit -m "feat: add recover_tasks for restarting monitoring after reboot"
```

---

## Task 9: app.py 集成

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 在 lifespan 中初始化 HeartbeatScheduler + ModelHealthTracker**

在创建 `shared` 组件之后、创建 CronScheduler 之前，添加：

```python
    # 初始化模型健康追踪器
    from backend.modules.model_health import ModelHealthTracker
    model_health_tracker = ModelHealthTracker()
    main_model = config.model.model
    sub_agent_cfg = config.sub_agent
    sub_model = sub_agent_cfg.model if sub_agent_cfg.enabled and sub_agent_cfg.model else main_model
    model_health_tracker.configure(main_model=main_model, sub_model=sub_model)
    shared["model_health_tracker"] = model_health_tracker
    logger.info(f"ModelHealthTracker initialized: main={main_model}, sub={sub_model}")

    # 初始化心跳调度器
    from backend.modules.agent.heartbeat_scheduler import HeartbeatScheduler
    heartbeat_scheduler = HeartbeatScheduler(
        subagent_manager=shared["subagent_manager"],
        provider=shared["provider"],
        main_model=main_model,
        sub_model=sub_model,
        model_health_tracker=model_health_tracker,
    )
    shared["heartbeat_scheduler"] = heartbeat_scheduler

    # 恢复未完成的任务
    await shared["subagent_manager"].recover_tasks()

    # 启动心跳调度器
    await heartbeat_scheduler.start()
    logger.info("HeartbeatScheduler started")
```

- [ ] **Step 2: 在 shutdown 时停止 HeartbeatScheduler**

在 lifespan 的 `yield` 之后（shutdown 阶段）添加：

```python
    # 停止心跳调度器
    if "heartbeat_scheduler" in shared:
        await shared["heartbeat_scheduler"].stop()
```

- [ ] **Step 3: 注册模型状态 API 路由**

```python
from backend.api.model_health import router as model_health_router
app.include_router(model_health_router)
```

- [ ] **Step 4: 语法检查**

Run: `python3 -c "import ast; ast.parse(open('/mnt/d/code/AIE_0302/AIE/backend/app.py').read()); print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/app.py
git commit -m "feat: integrate HeartbeatScheduler and ModelHealthTracker into app lifecycle"
```

---

## Task 10: 模型状态 API

**Files:**
- Create: `backend/api/model_health.py`

- [ ] **Step 1: 创建 API 端点**

```python
"""模型健康状态 API"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["model-health"])


@router.get("/model-status")
async def get_model_status(request: Request):
    """获取当前模型健康状态"""
    tracker = request.app.state.shared.get("model_health_tracker")
    if not tracker:
        return {"error": "ModelHealthTracker not initialized"}
    return tracker.get_status()
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/model_health.py
git commit -m "feat: add model health status API endpoint"
```

---

## Task 11: 前端 - 模型状态灯组件

**Files:**
- Create: `frontend/src/components/common/ModelStatusLights.vue`

- [ ] **Step 1: 创建 ModelStatusLights.vue**

组件显示两个灯，接收 `models` prop（从 Pinia store 获取），每个灯显示模型名称和状态颜色：
- 绿色圆点: healthy=true
- 红色圆点: healthy=false
- 黄色圆点: consecutive_failures > 0 且 < 3

组件使用 `defineProps` 和 `computed`，不需要复杂状态管理。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/common/ModelStatusLights.vue
git commit -m "feat: add ModelStatusLights component"
```

---

## Task 12: 前端 - Store 处理新 WS 消息

**Files:**
- Modify: `frontend/src/store/tasks.ts`

- [ ] **Step 1: 新增 analysisHistory 字段到 task 数据结构**

在 `addTask` 中为新建的任务对象添加：

```typescript
      lastAnalysis: '',
      analysisHistory: [],
      nextCheckAt: null,
      wakeCount: 0,
```

- [ ] **Step 2: 新增 updateTaskAnalysis 方法**

```typescript
  function updateTaskAnalysis(taskId: string, data: {
    progress: number,
    summary: string,
    elapsed_minutes: number,
    wake_count: number,
  }) {
    const task = runningTasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = data.progress
      task.lastAnalysis = data.summary
      task.wakeCount = data.wake_count
    }
  }

  function updateModelStatus(models: Record<string, any>) {
    modelStatus.value = models
  }
```

新增 `modelStatus` ref 并在 return 中导出。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/tasks.ts
git commit -m "feat: handle task_analysis and model_status WS messages in store"
```

---

## Task 13: 前端 - SubtaskProgress 改造

**Files:**
- Modify: `frontend/src/components/chat/SubtaskProgress.vue`

- [ ] **Step 1: 扩展 Props 和状态映射**

在 Props 接口中新增 `lastAnalysis` 字段，在模板中：
- 当 `lastAnalysis` 存在时，在进度条下方显示分析文本
- 支持新的 status 值：`sleeping`（灰色脉动）、`analyzing`（蓝色旋转）

- [ ] **Step 2: 更新样式**

添加 sleeping 状态的灰色脉动动画和 analyzing 状态的样式。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/SubtaskProgress.vue
git commit -m "feat: support sleeping/analyzing states and LLM analysis summary in SubtaskProgress"
```

---

## Task 14: 前端 - ChatWindow 集成新 WS 消息

**Files:**
- Modify: `frontend/src/modules/chat/ChatWindow.vue` (WS 事件处理部分)

- [ ] **Step 1: 在 WS 事件处理中添加 task_analysis 和 model_status 的分发**

找到现有的 `task_progress`、`task_complete` 等消息处理逻辑，在附近添加：

```typescript
  // task_analysis: 心跳分析结果
  if (msg.type === 'task_analysis') {
    taskStore.updateTaskAnalysis(msg.task_id, {
      progress: msg.progress,
      summary: msg.summary,
      elapsed_minutes: msg.elapsed_minutes,
      wake_count: msg.wake_count,
    })
  }

  // model_status: 模型健康状态变化
  if (msg.type === 'model_status') {
    taskStore.updateModelStatus(msg.models)
  }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/chat/ChatWindow.vue
git commit -m "feat: dispatch task_analysis and model_status WS events in ChatWindow"
```

---

## 实施顺序总结

按依赖关系排序：

```
Task 1 (DB字段) → Task 2 (SubagentTask字段) → Task 3 (ModelHealthTracker)
                                                         ↓
Task 4 (WS消息) → Task 5 (TaskBoardService) → Task 6 (HeartbeatScheduler)
                                                         ↓
                                    Task 7 (子Agent改造) → Task 8 (recover_tasks)
                                                                     ↓
                                                         Task 9 (app.py集成) → Task 10 (API)
                                                                     ↓
                                            Task 11 (状态灯) + Task 12 (Store) + Task 13 (SubtaskProgress) + Task 14 (ChatWindow)
```

后端核心链路: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
前端: 11 → 12 → 13 → 14（可并行）
