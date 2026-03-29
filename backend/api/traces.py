"""SuperWorkers 轨迹与技能进化 API

通过 SuperWorkers 插件暴露轨迹记录、技能提炼和技能管理能力。
"""

import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

router = APIRouter(prefix="/api/traces", tags=["traces"])


def _get_trace_skill(request: Request):
    """从 SuperWorkers 插件获取 TraceRecordingSkill"""
    plugin_manager = request.app.state.shared.get("plugin_manager")
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not available")

    plugin = plugin_manager.get_plugin("superworkers")
    if not plugin:
        raise HTTPException(status_code=503, detail="SuperWorkers plugin not enabled")

    trace_skill = plugin._skills.get("trace-recording")
    if not trace_skill:
        raise HTTPException(status_code=503, detail="Trace recording skill not loaded")

    return trace_skill


def _get_skill_distiller(request: Request):
    """从 SuperWorkers 插件获取 SkillDistillerSkill"""
    plugin_manager = request.app.state.shared.get("plugin_manager")
    if not plugin_manager:
        raise HTTPException(status_code=503, detail="Plugin manager not available")

    plugin = plugin_manager.get_plugin("superworkers")
    if not plugin:
        raise HTTPException(status_code=503, detail="SuperWorkers plugin not enabled")

    distiller = plugin._skills.get("skill-distiller")
    if not distiller:
        raise HTTPException(status_code=503, detail="Skill distiller skill not loaded")

    return distiller


# ── 轨迹统计 ──


@router.get("/stats")
async def get_trace_stats(request: Request, days: int = 30):
    """获取轨迹统计数据"""
    trace_skill = _get_trace_skill(request)
    stats = trace_skill.get_trace_stats(days=days)

    if not stats:
        return {
            "total": 0,
            "success_count": 0,
            "with_knowledge": 0,
            "avg_duration": 0,
            "avg_tool_calls": 0,
        }

    total = stats.get("total", 0)
    success_count = stats.get("success_count", 0)
    with_knowledge = stats.get("with_knowledge", 0)

    return {
        "total": total,
        "success_count": success_count,
        "success_rate": round(success_count / total, 3) if total > 0 else 0,
        "with_knowledge": with_knowledge,
        "knowledge_rate": round(with_knowledge / total, 3) if total > 0 else 0,
        "avg_duration": round(stats.get("avg_duration", 0), 1),
        "avg_tool_calls": round(stats.get("avg_tool_calls", 0), 1),
    }


# ── 轨迹列表 ──


@router.get("")
async def get_traces(
    request: Request,
    limit: int = 20,
    task_type: Optional[str] = None,
    outcome: Optional[str] = None,
):
    """获取最近轨迹列表"""
    trace_skill = _get_trace_skill(request)
    traces = trace_skill.get_recent_traces(limit=limit, task_type=task_type)

    if outcome:
        traces = [t for t in traces if t.get("outcome") == outcome]

    return traces


# ── 轨迹详情 ──


@router.get("/{trace_id}")
async def get_trace_detail(request: Request, trace_id: str):
    """获取轨迹完整详情"""
    trace_skill = _get_trace_skill(request)
    detail = trace_skill.get_trace_detail(trace_id)

    if not detail:
        raise HTTPException(status_code=404, detail="Trace not found")

    return detail


# ── 技能提炼 ──


@router.post("/distill")
async def distill_skills(request: Request):
    """从轨迹中提炼候选技能"""
    distiller = _get_skill_distiller(request)

    try:
        result = await distiller.process("", {})
        return {"message": result}
    except Exception as e:
        logger.error(f"Failed to distill skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 候选技能列表 ──


@router.get("/skills/candidates")
async def get_candidate_skills():
    """获取所有候选技能"""
    from backend.utils.paths import SKILLS_DIR

    candidates_dir = SKILLS_DIR / "_candidates"
    if not candidates_dir.exists():
        return []

    candidates = []
    for skill_dir in sorted(candidates_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            meta = _parse_skill_md(skill_file)
            candidates.append({
                "name": skill_dir.name,
                **meta,
            })

    return candidates


# ── 候选技能详情 ──


@router.get("/skills/candidates/{name}")
async def get_candidate_skill_detail(name: str):
    """获取候选技能 SKILL.md 内容"""
    from backend.utils.paths import SKILLS_DIR

    skill_file = SKILLS_DIR / "_candidates" / name / "SKILL.md"
    if not skill_file.exists():
        raise HTTPException(status_code=404, detail="Candidate skill not found")

    return {"name": name, "content": skill_file.read_text(encoding="utf-8")}


# ── 发布候选技能 ──


@router.post("/skills/candidates/{name}/promote")
async def promote_candidate_skill(name: str):
    """将候选技能发布到正式目录"""
    from backend.utils.paths import SKILLS_DIR

    candidates_dir = SKILLS_DIR / "_candidates" / name
    target_dir = SKILLS_DIR / name

    if not candidates_dir.exists():
        raise HTTPException(status_code=404, detail="Candidate skill not found")

    if target_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Skill '{name}' already exists in the official directory",
        )

    try:
        shutil.copytree(str(candidates_dir), str(target_dir))
        shutil.rmtree(str(candidates_dir))
        return {"success": True, "message": f"Skill '{name}' published successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 拒绝候选技能 ──


@router.post("/skills/candidates/{name}/reject")
async def reject_candidate_skill(name: str):
    """删除候选技能"""
    from backend.utils.paths import SKILLS_DIR

    candidates_dir = SKILLS_DIR / "_candidates" / name
    if not candidates_dir.exists():
        raise HTTPException(status_code=404, detail="Candidate skill not found")

    try:
        shutil.rmtree(str(candidates_dir))
        return {"success": True, "message": f"Skill '{name}' rejected and deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 正式技能列表 ──


@router.get("/skills")
async def get_skills():
    """获取所有正式技能"""
    from backend.utils.paths import SKILLS_DIR

    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            meta = _parse_skill_md(skill_file)
            skills.append({
                "name": skill_dir.name,
                **meta,
            })

    return skills


def _parse_skill_md(path) -> dict:
    """解析 SKILL.md front matter"""
    content = path.read_text(encoding="utf-8")

    title = path.parent.name
    description = ""
    confidence = 0
    created = ""
    status = ""

    for line in content.split("\n"):
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("confidence:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("created:"):
            created = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("status:"):
            status = line.split(":", 1)[1].strip().strip('"')

    return {
        "title": title,
        "description": description,
        "confidence": confidence,
        "created": created,
        "status": status,
    }
