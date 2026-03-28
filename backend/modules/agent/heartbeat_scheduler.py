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

from backend.database import AsyncSessionLocal
from backend.models.task_item import TaskItem
from sqlalchemy import select


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
    """独立心跳调度器 - 不依赖 Cron"""

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
        """主调度循环 - 串行唤醒 SLEEPING 任务"""
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
                    wait_seconds = max(0, (task.next_check_at or now) - now)
                    if wait_seconds.total_seconds() > 0:
                        await asyncio.sleep(wait_seconds.total_seconds())
                    # 串行唤醒
                    await self._analyze_task(task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[HeartbeatScheduler] Loop error: {e}")

    def _get_sleeping_tasks(self) -> list:
        """获取 SLEEPING 状态且有 monitoring_info 的任务"""
        return [
            t for t in self.subagent_manager.tasks.values()
            if t.status in ("sleeping", "SLEEPING") and t.monitoring_info
        ]

    async def _analyze_task(self, task) -> None:
        """分析单个任务的进展"""
        task.status = "ANALYZING"
        task.wake_count += 1
        logger.info(f"[HeartbeatScheduler] Analyzing task {task.task_id} (wake #{task.wake_count})")
        try:
            # 1. 检查进程存活
            alive = self._check_pid_alive(task)

            if not alive:
                # 进程已退出，做最终分析
                logger.info(f"[HeartbeatScheduler] Task {task.task_id} process exited")
                analysis = await self._llm_analyze(task, final=True)
                if analysis.success:
                    task.status = "done"
                    task.progress = 100
                else:
                    task.status = "failed"
                    task.error = analysis.summary or "进程异常退出"
                task.completed_at = datetime.utcnow()
                await self._notify_completion(task, analysis)
                action = "complete" if analysis.success else "fail"
                await self._sync_to_board(task, action)
                return

            # 2. LLM 智能分析
            analysis = await self._llm_analyze(task, final=False)

            # 3. 更新状态
            task.prev_progress = task.progress
            task.progress = analysis.progress
            task.last_analysis = analysis.summary

            # 4. 推送 WS
            await self._notify_progress(task, analysis)

            # 5. 动态频率
            task.next_check_at = self._calc_next_check(task, analysis)

            logger.info(f"[HeartbeatScheduler] Task {task.task_id}: progress={analysis.progress}%, summary={analysis.summary[:80]}")

        except Exception as e:
            logger.error(f"[HeartbeatScheduler] Analysis failed for {task.task_id}: {e}")
            task.next_check_at = datetime.utcnow() + timedelta(seconds=30)
        finally:
            if task.status == "ANALYZING":
                task.status = "SLEEPING"
            await self._sync_analysis_to_db(task)

    def _check_pid_alive(self, task) -> bool:
        """检查进程是否存活"""
        pid = task.monitoring_info.get("pid") if task.monitoring_info else None
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
            if minutes < 60:
                elapsed = f"{minutes} 分钟"
            else:
                hours = minutes // 60
                mins = minutes % 60
                elapsed = f"{hours}小时{mins}分钟"

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

        # 追加到历史滑窗（最多5条）
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
            if self.model_health_tracker:
                self.model_health_tracker.report_success("sub")
            return result
        except Exception as e:
            logger.warning(f"[HeartbeatScheduler] Sub-model failed: {e}")
            if self.model_health_tracker:
                self.model_health_tracker.report_failure("sub")

        # 降级到主模型
        try:
            result = await self._call_llm(self.main_model, messages)
            if self.model_health_tracker:
                self.model_health_tracker.report_success("main")
            return result
        except Exception as e:
            if self.model_health_tracker:
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
