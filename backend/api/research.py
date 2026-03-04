"""研究系统 API"""

from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from backend.modules.agent.research import (
    ResearchManager,
    ResearchSession,
    get_research_manager,
)
from backend.modules.agent.consolidator import (
    Consolidator,
    get_consolidator,
)

router = APIRouter(prefix="/api/research", tags=["research"])


# ========== Request Models ==========

class StartSessionRequest(BaseModel):
    """开始会话请求"""
    query: str
    session_type: Literal["research", "chat"] = "chat"


class LogExplorationRequest(BaseModel):
    """记录探索请求"""
    exploration_type: Literal["thinking", "action", "result", "retrieved", "decision"]
    content: str
    metadata: dict = {}


class CompleteSessionRequest(BaseModel):
    """完成会话请求"""
    solution: str
    success: bool


class KnowledgeRefRequest(BaseModel):
    """知识引用请求"""
    source_name: str
    content: str
    file_path: str = None
    score: float = 0.0


# ========== Research Endpoints ==========

@router.post("/start")
async def start_session(request: StartSessionRequest):
    """开始研究会话"""
    manager = get_research_manager()
    session = manager.create_session(request.query, request.session_type)

    return {
        "session_id": session.id,
        "query": session.query,
        "start_time": session.start_time.isoformat(),
    }


@router.post("/{session_id}/exploration")
async def log_exploration(session_id: str, request: LogExplorationRequest):
    """记录探索过程"""
    manager = get_research_manager()
    success = manager.add_exploration(
        session_id=session_id,
        exploration_type=request.exploration_type,
        content=request.content,
        metadata=request.metadata,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


@router.post("/{session_id}/knowledge")
async def add_knowledge_ref(session_id: str, request: KnowledgeRefRequest):
    """添加知识引用"""
    manager = get_research_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    manager.add_knowledge_ref(session_id, request.dict())

    return {"success": True}


@router.post("/{session_id}/complete")
async def complete_session(session_id: str, request: CompleteSessionRequest):
    """完成会话"""
    manager = get_research_manager()
    manager.complete_session(session_id, request.solution, request.success)

    return {"success": True}


@router.get("/history")
async def get_history(limit: int = 20):
    """获取研究历史"""
    manager = get_research_manager()
    sessions = manager.get_recent_sessions(limit)

    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    manager = get_research_manager()
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


# ========== Consolidation Endpoints ==========

@router.get("/consolidation/status")
async def get_consolidation_status():
    """获取沉淀状态"""
    manager = get_research_manager()
    consolidator = get_consolidator()

    # 获取需要沉淀的会话
    pending = manager.get_sessions_for_consolidation(limit=100)
    pending_count = len(pending)

    # 获取已沉淀的解决方案
    solutions = consolidator.get_solutions(limit=10)
    solutions_count = len(consolidator.get_solutions(limit=1000))

    return {
        "pending_sessions": pending_count,
        "consolidated_solutions": solutions_count,
        "recent_solutions": solutions,
    }


@router.post("/consolidate")
async def consolidate_session(session_id: str = None):
    """手动触发沉淀"""
    manager = get_research_manager()
    consolidator = get_consolidator()

    if session_id:
        # 沉淀指定会话
        session = manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = consolidator.consolidate_session(session)
        return {
            "success": True,
            "result": result.to_dict(),
        }
    else:
        # 沉淀所有待处理的会话
        sessions = manager.get_sessions_for_consolidation(limit=10)
        results = []

        for session in sessions:
            try:
                result = consolidator.consolidate_session(session)
                results.append(result.to_dict())
            except Exception as e:
                logger.error(f"Failed to consolidate session {session.id}: {e}")

        return {
            "success": True,
            "consolidated": len(results),
            "results": results,
        }


@router.get("/solutions")
async def get_solutions(limit: int = 20):
    """获取已沉淀的解决方案"""
    consolidator = get_consolidator()
    solutions = consolidator.get_solutions(limit)

    return {"solutions": solutions, "count": len(solutions)}
