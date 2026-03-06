"""AIE Research Session Logger - Real-time JSONL logging"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Any
from loguru import logger
from collections import deque
from threading import Lock
from contextlib import contextmanager

from backend.utils.paths import MEMORY_DIR


# Log entry types
LogType = Literal["thinking", "action", "result", "retrieved", "decision", "system", "error"]


class LogEntry:
    """Single log entry"""

    def __init__(
        self,
        log_type: LogType,
        content: str,
        session_id: str = None,
        metadata: dict = None,
    ):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.log_type = log_type
        self.content = content
        self.session_id = session_id
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.log_type,
            "content": self.content,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ResearchLogger:
    """
    Research session logger with real-time JSONL writing

    Features:
    - Real-time streaming write to JSONL files
    - In-memory buffer for batch writing
    - Session-based organization
    - Index file for quick lookup
    """

    def __init__(
        self,
        storage_dir: Path = None,
        buffer_size: int = 10,
        flush_interval: float = 1.0,
    ):
        self.storage_dir = storage_dir or MEMORY_DIR / "research_logs"
        self.sessions_dir = self.storage_dir / "sessions"
        self.index_file = self.storage_dir / "index.json"

        # Create directories
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Buffer settings
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # In-memory buffers per session
        self._buffers: dict[str, deque] = {}
        self._locks: dict[str, Lock] = {}

        # Track active sessions
        self._active_sessions: set = set()

        logger.info(f"Research logger initialized at {self.storage_dir}")

    def _get_lock(self, session_id: str) -> Lock:
        """Get or create lock for session"""
        if session_id not in self._locks:
            self._locks[session_id] = Lock()
        return self._locks[session_id]

    def _get_buffer(self, session_id: str) -> deque:
        """Get or create buffer for session"""
        if session_id not in self._buffers:
            self._buffers[session_id] = deque(maxlen=self.buffer_size * 2)
        return self._buffers[session_id]

    def start_session(self, session_id: str, query: str = None, metadata: dict = None):
        """Start a new logging session"""
        # Mark session as active
        self._active_sessions.add(session_id)

        # Create session file
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            # Write session start entry
            entry = LogEntry(
                log_type="system",
                content=f"Session started: {query or 'No query'}",
                session_id=session_id,
                metadata={
                    "event": "session_start",
                    "query": query,
                    **(metadata or {})
                }
            )
            self._write_entry(session_id, entry)

        # Update index
        self._update_session_index(session_id, query)

        logger.debug(f"Started logging session: {session_id}")

    def end_session(self, session_id: str, summary: str = None):
        """End a logging session"""
        # Flush any remaining buffer
        self.flush(session_id)

        # Write session end entry
        entry = LogEntry(
            log_type="system",
            content=summary or "Session ended",
            session_id=session_id,
            metadata={"event": "session_end"}
        )
        self._write_entry(session_id, entry)

        # Remove from active sessions
        self._active_sessions.discard(session_id)

        # Clean up buffer
        if session_id in self._buffers:
            del self._buffers[session_id]
        if session_id in self._locks:
            del self._locks[session_id]

        logger.debug(f"Ended logging session: {session_id}")

    def log(
        self,
        log_type: LogType,
        content: str,
        session_id: str = None,
        metadata: dict = None,
        flush: bool = False,
    ) -> str:
        """
        Log an entry

        Args:
            log_type: Type of log (thinking/action/result/retrieved/decision/system/error)
            content: Log content
            session_id: Session ID (optional)
            metadata: Additional metadata
            flush: Whether to flush immediately

        Returns:
            Log entry ID
        """
        if not session_id:
            logger.warning("No session_id provided, log entry will not be persisted")
            return None

        entry = LogEntry(
            log_type=log_type,
            content=content,
            session_id=session_id,
            metadata=metadata,
        )

        # Add to buffer
        buffer = self._get_buffer(session_id)
        buffer.append(entry)

        # Flush if requested or buffer is full
        if flush or len(buffer) >= self.buffer_size:
            self.flush(session_id)

        return entry.id

    # Convenience methods for common log types

    def log_thinking(self, session_id: str, thought: str, metadata: dict = None):
        """Log thinking process"""
        return self.log("thinking", thought, session_id, metadata)

    def log_action(self, session_id: str, action: str, tool: str = None, metadata: dict = None):
        """Log action performed"""
        return self.log(
            "action",
            action,
            session_id,
            {**(metadata or {}), "tool": tool}
        )

    def log_result(self, session_id: str, result: str, success: bool = True, error: str = None, metadata: dict = None):
        """Log result of an action"""
        return self.log(
            "result",
            result,
            session_id,
            {
                **(metadata or {}),
                "success": success,
                "error": error
            }
        )

    def log_retrieved(self, session_id: str, content: str, source: str = None, score: float = None, metadata: dict = None):
        """Log retrieved knowledge"""
        return self.log(
            "retrieved",
            content,
            session_id,
            {
                **(metadata or {}),
                "source": source,
                "score": score
            }
        )

    def log_decision(self, session_id: str, decision: str, reason: str = None, metadata: dict = None):
        """Log decision made"""
        return self.log(
            "decision",
            decision,
            session_id,
            {**(metadata or {}), "reason": reason}
        )

    def log_error(self, session_id: str, error: str, context: dict = None):
        """Log error"""
        return self.log(
            "error",
            error,
            session_id,
            {"context": context}
        )

    def _write_entry(self, session_id: str, entry: LogEntry):
        """Write entry to file"""
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        lock = self._get_lock(session_id)

        with lock:
            with open(session_file, "a", encoding="utf-8") as f:
                f.write(entry.to_jsonl() + "\n")

    def flush(self, session_id: str = None):
        """Flush buffer to disk"""
        if session_id:
            self._flush_session(session_id)
        else:
            # Flush all sessions
            for sid in list(self._buffers.keys()):
                self._flush_session(sid)

    def _flush_session(self, session_id: str):
        """Flush a specific session"""
        buffer = self._get_buffer(session_id)
        if not buffer:
            return

        lock = self._get_lock(session_id)
        session_file = self.sessions_dir / f"{session_id}.jsonl"

        with lock:
            with open(session_file, "a", encoding="utf-8") as f:
                while buffer:
                    entry = buffer.popleft()
                    f.write(entry.to_jsonl() + "\n")

    def _update_session_index(self, session_id: str, query: str = None):
        """Update session index"""
        index_data = {"sessions": []}

        if self.index_file.exists():
            try:
                index_data = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        sessions = index_data.get("sessions", [])

        # Check if session already exists
        existing = None
        for i, s in enumerate(sessions):
            if s.get("id") == session_id:
                existing = i
                break

        session_entry = {
            "id": session_id,
            "query": query,
            "started_at": datetime.now().isoformat(),
            "file": f"{session_id}.jsonl",
        }

        if existing is not None:
            sessions[existing] = session_entry
        else:
            sessions.insert(0, session_entry)

        # Keep only last 1000 sessions
        index_data["sessions"] = sessions[:1000]

        self.index_file.write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_session_log(self, session_id: str, limit: int = None) -> list[dict]:
        """Get all log entries for a session"""
        session_file = self.sessions_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            return []

        entries = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

        if limit:
            entries = entries[-limit:]

        return entries

    def get_session_logs_by_type(
        self,
        session_id: str,
        log_type: LogType
    ) -> list[dict]:
        """Get log entries of a specific type for a session"""
        all_entries = self.get_session_log(session_id)
        return [e for e in all_entries if e.get("type") == log_type]

    def get_recent_sessions(self, limit: int = 20) -> list[dict]:
        """Get recent session summaries"""
        if not self.index_file.exists():
            return []

        try:
            index_data = json.loads(self.index_file.read_text(encoding="utf-8"))
            sessions = index_data.get("sessions", [])[:limit]
            return sessions
        except Exception:
            return []

    def search_logs(
        self,
        query: str = None,
        session_id: str = None,
        log_type: LogType = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search logs"""
        results = []

        # Determine which sessions to search
        sessions_to_search = []
        if session_id:
            sessions_to_search = [session_id]
        else:
            sessions_to_search = [s["id"] for s in self.get_recent_sessions(limit=100)]

        # Search each session
        for sid in sessions_to_search:
            entries = self.get_session_log(sid)

            for entry in entries:
                # Filter by type
                if log_type and entry.get("type") != log_type:
                    continue

                # Filter by query (simple substring match)
                if query:
                    content = entry.get("content", "").lower()
                    if query.lower() not in content:
                        continue

                results.append(entry)

                if len(results) >= limit:
                    return results

        return results

    def get_session_stats(self, session_id: str) -> dict:
        """Get statistics for a session"""
        entries = self.get_session_log(session_id)

        stats = {
            "total_entries": len(entries),
            "by_type": {},
            "duration_seconds": None,
        }

        # Count by type
        for entry in entries:
            log_type = entry.get("type", "unknown")
            stats["by_type"][log_type] = stats["by_type"].get(log_type, 0) + 1

        # Calculate duration
        if entries:
            try:
                first_time = datetime.fromisoformat(entries[0]["timestamp"])
                last_time = datetime.fromisoformat(entries[-1]["timestamp"])
                stats["duration_seconds"] = (last_time - first_time).total_seconds()
            except Exception:
                pass

        return stats

    @contextmanager
    def session(self, session_id: str, query: str = None, metadata: dict = None):
        """Context manager for session logging"""
        self.start_session(session_id, query, metadata)
        try:
            yield self
        finally:
            self.end_session(session_id)

    def cleanup_old_sessions(self, days: int = 30):
        """Clean up session files older than specified days"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0

        for session_file in self.sessions_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                if mtime < cutoff:
                    session_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to clean up {session_file}: {e}")

        # Update index
        if self.index_file.exists():
            try:
                index_data = json.loads(self.index_file.read_text(encoding="utf-8"))
                sessions = [
                    s for s in index_data.get("sessions", [])
                    if (self.sessions_dir / s["file"]).exists()
                ]
                index_data["sessions"] = sessions
                self.index_file.write_text(
                    json.dumps(index_data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                logger.warning(f"Failed to update index: {e}")

        logger.info(f"Cleaned up {cleaned} old session files")
        return cleaned


# Global instance
_research_logger: Optional[ResearchLogger] = None


def get_research_logger() -> ResearchLogger:
    """Get global research logger instance"""
    global _research_logger
    if _research_logger is None:
        _research_logger = ResearchLogger()
    return _research_logger


def reinit_research_logger() -> ResearchLogger:
    """Reinitialize research logger"""
    global _research_logger
    _research_logger = ResearchLogger()
    return _research_logger
