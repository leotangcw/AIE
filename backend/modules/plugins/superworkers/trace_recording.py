"""Trace Recording Skill - 操作轨迹记录

通过 Hook 机制自动记录 Agent 的完整工作过程。
不需要人工触发，插件启用后自动运行。
"""

import json
import uuid
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from backend.modules.plugins.hooks import Hook


class TraceRecordingSkill:
    """
    轨迹记录技能

    通过 Hook 监听以下事件自动记录：
    - before_process: 轨迹开始
    - tool_called: 工具调用
    - tool_result: 工具结果
    - after_process: 轨迹完成

    轨迹存储为 JSONL 文件 + SQLite 索引。
    """

    def __init__(self):
        self._storage_dir: Optional[Path] = None
        self._current_traces: dict[str, dict] = {}  # session_id -> trace data
        self._db = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "trace-recording"

    def _init_storage(self):
        """初始化存储"""
        if self._initialized:
            return

        from backend.utils.paths import DATA_DIR
        self._storage_dir = DATA_DIR / "traces"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 SQLite 索引
        self._init_db()
        self._initialized = True
        logger.debug("TraceRecording storage initialized")

    def _init_db(self):
        """初始化 SQLite 索引数据库"""
        import sqlite3
        db_path = self._storage_dir / "index.db"
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                session_id TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                task_type TEXT,
                outcome TEXT,
                has_knowledge BOOLEAN DEFAULT 0,
                knowledge_helpful BOOLEAN DEFAULT 0,
                tool_calls_count INTEGER DEFAULT 0,
                total_duration_ms INTEGER DEFAULT 0,
                user_feedback TEXT,
                trace_file TEXT
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_date ON traces(started_at)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_type ON traces(task_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_outcome ON traces(outcome)
        """)
        self._db.commit()

    def _get_trace_file_path(self, trace_id: str) -> Path:
        """获取轨迹文件路径"""
        now = datetime.now()
        month_dir = self._storage_dir / now.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir / f"{trace_id}.jsonl"

    async def _on_before_process(self, event: str, context: dict) -> None:
        """处理开始前 - 初始化轨迹"""
        self._init_storage()

        session_id = context.get("session_id", "unknown")
        user_message = context.get("message", "")
        channel = context.get("channel", "unknown")

        trace_id = str(uuid.uuid4())

        self._current_traces[session_id] = {
            "trace_id": trace_id,
            "session_id": session_id,
            "started_at": datetime.now().isoformat(),
            "input": {
                "user_message": user_message[:2000],  # 截断过长消息
                "channel": channel,
            },
            "execution": {
                "iterations": [],
                "tool_calls": [],
            },
            "knowledge_stage": {
                "local_skills_checked": [],
                "local_skills_used": [],
                "enterprise_knowledge_queried": False,
                "knowledge_results": [],
            },
            "metadata": {
                "model": context.get("model", "unknown"),
                "plugin_active": "superworkers",
            },
        }

        logger.debug(f"Trace started: {trace_id} for session {session_id}")

    async def _on_tool_called(self, event: str, context: dict) -> None:
        """工具调用时记录"""
        session_id = context.get("session_id", "")
        trace = self._current_traces.get(session_id)
        if not trace:
            return

        tool_name = context.get("tool_name", "unknown")
        arguments = context.get("arguments", {})

        # 记录知识相关操作
        if tool_name == "knowledge_retrieve":
            trace["knowledge_stage"]["enterprise_knowledge_queried"] = True
        elif tool_name == "list_skills":
            trace["knowledge_stage"]["local_skills_checked"] = True
        elif tool_name == "read_file":
            args_str = json.dumps(arguments, ensure_ascii=False)
            if "skills" in args_str or "SKILL" in args_str:
                trace["knowledge_stage"]["local_skills_used"].append(arguments.get("path", ""))

        # 记录工具调用
        trace["execution"]["tool_calls"].append({
            "tool": tool_name,
            "arguments": {k: v for k, v in arguments.items() if k != "auto_record"},
            "called_at": datetime.now().isoformat(),
            "duration_ms": None,
            "success": None,
            "result_summary": None,
        })

    async def _on_tool_result(self, event: str, context: dict) -> None:
        """工具结果时记录"""
        session_id = context.get("session_id", "")
        trace = self._current_traces.get(session_id)
        if not trace:
            return

        tool_name = context.get("tool_name", "")
        result = context.get("result", "")
        success = context.get("success", True)

        # 找到最近的同名工具调用，更新结果
        tool_calls = trace["execution"]["tool_calls"]
        for i in range(len(tool_calls) - 1, -1, -1):
            if tool_calls[i]["tool"] == tool_name and tool_calls[i]["duration_ms"] is None:
                tool_calls[i]["success"] = success
                # 摘要结果（截断长文本）
                result_str = str(result)
                tool_calls[i]["result_summary"] = result_str[:500] if len(result_str) > 500 else result_str

                # 记录知识检索结果
                if tool_name == "knowledge_retrieve" and success:
                    trace["knowledge_stage"]["knowledge_results"].append({
                        "query": tool_calls[i]["arguments"].get("query", ""),
                        "result_preview": result_str[:200],
                        "mode": tool_calls[i]["arguments"].get("mode", "auto"),
                    })
                break

    async def _on_after_process(self, event: str, context: dict) -> None:
        """处理完成后 - 保存轨迹"""
        session_id = context.get("session_id", "")
        trace = self._current_traces.pop(session_id, None)
        if not trace:
            return

        trace["ended_at"] = datetime.now().isoformat()

        # 计算统计信息
        tool_calls = trace["execution"]["tool_calls"]
        trace["output"] = {
            "outcome": context.get("outcome", "success"),
            "tool_calls_count": len(tool_calls),
        }
        trace["metadata"]["total_duration_ms"] = self._calc_duration(
            trace["started_at"], trace["ended_at"]
        )

        # 推断任务类型
        trace["metadata"]["task_type"] = self._infer_task_type(
            trace["input"]["user_message"],
            [tc["tool"] for tc in tool_calls]
        )

        # 保存轨迹
        self._save_trace(trace)
        logger.debug(f"Trace saved: {trace['trace_id']}")

    def _calc_duration(self, start: str, end: str) -> int:
        """计算持续时间（毫秒）"""
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            start_dt = datetime.strptime(start[:19], fmt)
            end_dt = datetime.strptime(end[:19], fmt)
            return int((end_dt - start_dt).total_seconds() * 1000)
        except (ValueError, TypeError):
            return 0

    def _infer_task_type(self, message: str, tools: list[str]) -> str:
        """推断任务类型"""
        if any(t in tools for t in ["knowledge_retrieve", "knowledge_query_db"]):
            return "knowledge_query"
        if "knowledge" in message or "知识" in message:
            return "knowledge_query"
        if any(t in tools for t in ["write_file", "edit_file"]):
            return "content_creation"
        if "web_search" in tools or "搜索" in message:
            return "web_search"
        if "code" in message.lower() or "代码" in message:
            return "coding"
        return "general"

    def _save_trace(self, trace: dict):
        """保存轨迹到 JSONL 文件和 SQLite"""
        if not self._storage_dir:
            return

        trace_id = trace["trace_id"]

        # 保存 JSONL
        trace_file = self._get_trace_file_path(trace_id)
        try:
            trace_file.write_text(
                json.dumps(trace, ensure_ascii=False),
                encoding="utf-8"
            )

            # 保存到 SQLite 索引
            if self._db:
                self._db.execute("""
                    INSERT OR REPLACE INTO traces (
                        trace_id, session_id, started_at, ended_at,
                        task_type, outcome, has_knowledge, knowledge_helpful,
                        tool_calls_count, total_duration_ms, trace_file
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trace_id,
                    trace.get("session_id"),
                    trace.get("started_at"),
                    trace.get("ended_at"),
                    trace.get("metadata", {}).get("task_type"),
                    trace.get("output", {}).get("outcome"),
                    1 if trace.get("knowledge_stage", {}).get("enterprise_knowledge_queried") else 0,
                    None,  # knowledge_helpful 需要后续用户反馈
                    trace.get("output", {}).get("tool_calls_count", 0),
                    trace.get("metadata", {}).get("total_duration_ms", 0),
                    str(trace_file.relative_to(self._storage_dir)),
                ))
                self._db.commit()
        except Exception as e:
            logger.error(f"Failed to save trace {trace_id}: {e}")

    def get_recent_traces(self, limit: int = 20, task_type: str = None) -> list[dict]:
        """获取最近的轨迹摘要"""
        if not self._db:
            return []

        query = "SELECT * FROM traces"
        params = []
        if task_type:
            query += " WHERE task_type = ?"
            params.append(task_type)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        rows = self._db.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_trace_detail(self, trace_id: str) -> Optional[dict]:
        """获取完整轨迹详情"""
        if not self._storage_dir:
            return None

        # 先从索引找到文件路径
        if self._db:
            row = self._db.execute(
                "SELECT trace_file FROM traces WHERE trace_id = ?",
                (trace_id,)
            ).fetchone()

            if not row:
                return None

            trace_file = self._storage_dir / row["trace_file"]
        else:
            return None

        if not trace_file.exists():
            return None

        try:
            return json.loads(trace_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read trace {trace_id}: {e}")
            return None

    def get_trace_stats(self, days: int = 30) -> dict:
        """获取轨迹统计"""
        if not self._db:
            return {}

        from datetime import timedelta
        since = (datetime.now() - timedelta(days=days)).isoformat()

        row = self._db.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN outcome = 'success' THEN 1 END) as success_count,
                COUNT(CASE WHEN has_knowledge = 1 THEN 1 END) as with_knowledge,
                AVG(total_duration_ms) as avg_duration,
                AVG(tool_calls_count) as avg_tool_calls
            FROM traces WHERE started_at >= ?
        """, (since,)).fetchone()

        return dict(row) if row else {}

    async def cleanup_old_traces(self, retain_days: int = 30) -> int:
        """清理过期轨迹"""
        if not self._storage_dir or not self._db:
            return 0

        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=retain_days)).isoformat()

        # 查找过期轨迹
        rows = self._db.execute(
            "SELECT trace_id, trace_file FROM traces WHERE started_at < ?",
            (cutoff,)
        ).fetchall()

        if not rows:
            return 0

        cleaned = 0
        for row in rows:
            trace_file = self._storage_dir / row["trace_file"]
            if trace_file.exists():
                try:
                    trace_file.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {trace_file}: {e}")

            self._db.execute(
                "DELETE FROM traces WHERE trace_id = ?",
                (row["trace_id"],)
            )

        self._db.commit()

        # 清理空目录
        self._cleanup_empty_dirs()

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old traces (older than {retain_days} days)")

        return cleaned

    def _cleanup_empty_dirs(self):
        """清理空的月度目录"""
        if not self._storage_dir:
            return
        for month_dir in self._storage_dir.iterdir():
            if month_dir.is_dir():
                try:
                    if not any(month_dir.iterdir()):
                        month_dir.rmdir()
                except OSError:
                    pass

    def get_hooks(self) -> list[Hook]:
        """注册自动记录 Hook"""
        return [
            Hook(
                event="before_process",
                callback=self._on_before_process,
                description="轨迹记录启动",
                priority=10,
            ),
            Hook(
                event="tool_called",
                callback=self._on_tool_called,
                description="工具调用记录",
                priority=0,
            ),
            Hook(
                event="tool_result",
                callback=self._on_tool_result,
                description="工具结果记录",
                priority=0,
            ),
            Hook(
                event="after_process",
                callback=self._on_after_process,
                description="轨迹完成与保存",
                priority=10,
            ),
        ]
