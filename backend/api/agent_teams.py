"""Agent Teams API — CRUD for user-defined multi-agent workflow templates."""

import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.agent_team import AgentTeam

router = APIRouter(prefix="/api/agent-teams", tags=["agent-teams"])


# ============================================================================
# Workflow Execution
# ============================================================================


class ExecuteWorkflowRequest(BaseModel):
    """执行工作流请求"""
    team_id: str = Field(..., description="Agent Team ID")
    question: str = Field(..., description="问题或目标")
    session_id: Optional[str] = Field(None, description="会话ID，用于WebSocket推送")


# ============================================================================
# Pydantic schemas
# ============================================================================


class AgentDefinition(BaseModel):
    """One agent slot inside a workflow."""
    id: str = Field(..., description="Unique identifier within the team")
    role: str = Field(default="", description="Role / persona label")
    system_prompt: Optional[str] = Field(
        None,
        description=(
            "Persistent system-level instructions for this agent. "
            "Injected as the system message so the LLM fully adopts this persona "
            "before seeing the workflow goal or task."
        ),
    )
    task: str = Field(default="", description="What this agent should do (pipeline/graph only)")
    perspective: Optional[str] = Field(None, description="Viewpoint label (council mode only)")
    depends_on: List[str] = Field(default_factory=list, description="IDs this agent waits for (graph mode)")


class AgentTeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    mode: str = Field("pipeline", pattern="^(pipeline|graph|council)$")
    agents: List[AgentDefinition] = Field(default_factory=list)
    is_active: bool = Field(True)
    cross_review: bool = Field(True, description="Council mode only: enable cross-review between members")
    enable_skills: bool = Field(False, description="Enable skills system for sub-agents")


class AgentTeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    mode: Optional[str] = Field(None, pattern="^(pipeline|graph|council)$")
    agents: Optional[List[AgentDefinition]] = None
    is_active: Optional[bool] = None
    cross_review: Optional[bool] = Field(None, description="Council mode only: enable cross-review between members")
    enable_skills: Optional[bool] = Field(None, description="Enable skills system for sub-agents")


class AgentTeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    mode: str
    agents: List[Any]
    is_active: bool
    cross_review: bool
    enable_skills: bool
    created_at: str
    updated_at: str


# ============================================================================
# Helpers
# ============================================================================


def _to_response(team: AgentTeam) -> AgentTeamResponse:
    return AgentTeamResponse(**team.to_dict())


async def _get_or_404(team_id: str, db: AsyncSession) -> AgentTeam:
    result = await db.execute(select(AgentTeam).where(AgentTeam.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Agent team '{team_id}' not found")
    return team


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/", response_model=List[AgentTeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)) -> List[AgentTeamResponse]:
    """Return all agent teams ordered by creation time (newest first)."""
    try:
        result = await db.execute(
            select(AgentTeam).order_by(AgentTeam.created_at.desc())
        )
        teams = result.scalars().all()
        return [_to_response(t) for t in teams]
    except Exception as exc:
        logger.exception(f"Failed to list agent teams: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{team_id}", response_model=AgentTeamResponse)
async def get_team(team_id: str, db: AsyncSession = Depends(get_db)) -> AgentTeamResponse:
    team = await _get_or_404(team_id, db)
    return _to_response(team)


@router.post("/", response_model=AgentTeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: AgentTeamCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentTeamResponse:
    """Create a new agent team template."""
    try:
        team = AgentTeam(
            id=str(uuid.uuid4()),
            name=payload.name,
            description=payload.description,
            mode=payload.mode,
            agents=[a.model_dump() for a in payload.agents],
            is_active=payload.is_active,
            cross_review=payload.cross_review,
            enable_skills=payload.enable_skills,
        )
        db.add(team)
        await db.commit()
        await db.refresh(team)
        return _to_response(team)
    except Exception as exc:
        await db.rollback()
        logger.exception(f"Failed to create agent team: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{team_id}", response_model=AgentTeamResponse)
async def update_team(
    team_id: str,
    payload: AgentTeamUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentTeamResponse:
    """Update an existing agent team."""
    team = await _get_or_404(team_id, db)
    try:
        if payload.name is not None:
            team.name = payload.name
        if payload.description is not None:
            team.description = payload.description
        if payload.mode is not None:
            team.mode = payload.mode
        if payload.agents is not None:
            team.agents = [a.model_dump() for a in payload.agents]
        if payload.is_active is not None:
            team.is_active = payload.is_active
        if payload.cross_review is not None:
            team.cross_review = payload.cross_review
        if payload.enable_skills is not None:
            team.enable_skills = payload.enable_skills
        await db.commit()
        await db.refresh(team)
        return _to_response(team)
    except Exception as exc:
        await db.rollback()
        logger.exception(f"Failed to update agent team {team_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """Delete an agent team."""
    team = await _get_or_404(team_id, db)
    try:
        await db.delete(team)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception(f"Failed to delete agent team {team_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/execute")
async def execute_workflow(payload: ExecuteWorkflowRequest) -> dict:
    """Execute a workflow using an agent team."""
    from sqlalchemy import select
    from backend.database import AsyncSessionLocal
    from backend.modules.agent.workflow import WorkflowEngine
    from backend.modules.agent.subagent import SubagentManager
    from backend.modules.agent.skills import SkillsLoader
    from backend.ws.connection import get_cancel_token
    from backend.utils.paths import WORKSPACE_DIR

    # 获取 team
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AgentTeam).where(AgentTeam.id == payload.team_id))
        team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail=f"Agent team '{payload.team_id}' not found")

    # 获取子代理管理器
    skills_dir = WORKSPACE_DIR / "skills"
    skills = SkillsLoader(skills_dir)
    subagent_manager = SubagentManager(skills=skills)

    # 获取取消令牌
    cancel_token = None
    if payload.session_id:
        cancel_token = get_cancel_token(payload.session_id)

    # 创建工作流引擎
    engine = WorkflowEngine(
        subagent_manager=subagent_manager,
        session_id=payload.session_id,
        cancel_token=cancel_token,
        skills=skills,
    )

    # 根据模式执行工作流
    try:
        if team.mode == "pipeline":
            result = await engine.run_pipeline(
                goal=payload.question,
                stages=team.agents,
                enable_skills=team.enable_skills,
            )
        elif team.mode == "graph":
            result = await engine.run_graph(
                goal=payload.question,
                slots=team.agents,
                enable_skills=team.enable_skills,
            )
        elif team.mode == "council":
            result = await engine.run_council(
                question=payload.question,
                members=team.agents,
                cross_review=team.cross_review,
                enable_skills=team.enable_skills,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown workflow mode: {team.mode}")

        return {"result": result}
    except Exception as exc:
        logger.exception(f"Workflow execution failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
