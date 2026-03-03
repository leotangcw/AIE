"""经验学习 API"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from backend.modules.agent.experience import (
    ExperienceEngine,
    WorkFeedback,
    get_experience_engine,
)

router = APIRouter(prefix="/api/experience", tags=["experience"])


class LearnRequest(BaseModel):
    """学习请求"""
    task_description: str
    user_feedback: str
    original_output: str
    final_output: str
    context: dict = {}


class SkillResponse(BaseModel):
    """技能响应"""
    id: str
    name: str
    description: str
    trigger_conditions: list[str]
    action_steps: list[str]
    confidence: float
    source: str
    usage_count: int


@router.post("/learn")
async def learn_from_feedback(request: LearnRequest) -> SkillResponse:
    """从用户反馈中学习"""
    engine = get_experience_engine()

    feedback = WorkFeedback(
        task_description=request.task_description,
        user_feedback=request.user_feedback,
        original_output=request.original_output,
        final_output=request.final_output,
        context=request.context,
    )

    skill = engine.learn_from_feedback(feedback)

    if not skill:
        raise HTTPException(status_code=400, detail="Failed to learn from feedback")

    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        trigger_conditions=skill.trigger_conditions,
        action_steps=skill.action_steps,
        confidence=skill.confidence,
        source=skill.source,
        usage_count=skill.usage_count,
    )


@router.get("/skills")
async def get_skills(min_confidence: float = 0.0) -> list[SkillResponse]:
    """获取所有技能"""
    engine = get_experience_engine()
    skills = engine.get_skills_by_confidence(min_confidence)

    return [
        SkillResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            trigger_conditions=s.trigger_conditions,
            action_steps=s.action_steps,
            confidence=s.confidence,
            source=s.source,
            usage_count=s.usage_count,
        )
        for s in skills
    ]


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str) -> SkillResponse:
    """获取单个技能"""
    engine = get_experience_engine()
    skill = engine.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        trigger_conditions=skill.trigger_conditions,
        action_steps=skill.action_steps,
        confidence=skill.confidence,
        source=skill.source,
        usage_count=skill.usage_count,
    )


@router.post("/skills/{skill_id}/apply")
async def apply_skill(skill_id: str):
    """应用技能"""
    engine = get_experience_engine()
    success = engine.apply_skill(skill_id)

    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")

    return {"success": True, "message": "Skill applied"}


@router.post("/skills/{skill_id}/confidence")
async def update_confidence(skill_id: str, delta: float):
    """更新技能置信度"""
    engine = get_experience_engine()
    skill = engine.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    engine.update_confidence(skill_id, delta)
    return {"success": True, "confidence": skill.confidence}


@router.get("/export")
async def export_skills():
    """导出技能用于交换"""
    engine = get_experience_engine()
    return {"skills": engine.export_skills_for_exchange()}
