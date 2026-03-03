"""企业规则 API"""

from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from loguru import logger

from backend.modules.agent.rules import (
    RulesEngine,
    Rule,
    AieTemplate,
    get_rules_engine,
    get_template_manager,
)

router = APIRouter(prefix="/api/rules", tags=["rules"])


class RuleCreate(BaseModel):
    """创建规则"""
    name: str
    description: str
    content: str
    enabled: bool = True
    priority: int = 0
    rule_type: str = "general"


class RuleUpdate(BaseModel):
    """更新规则"""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    rule_type: Optional[str] = None


class RuleResponse(BaseModel):
    """规则响应"""
    id: str
    name: str
    description: str
    content: str
    enabled: bool
    priority: int
    rule_type: str


class TemplateCreate(BaseModel):
    """创建模板"""
    name: str
    description: str
    rules: list[str] = []
    skills: list[str] = []
    default_config: dict = {}


@router.get("/")
async def get_rules(enabled_only: bool = False):
    """获取所有规则"""
    engine = get_rules_engine()

    if enabled_only:
        rules = engine.get_enabled_rules()
    else:
        rules = engine.get_all_rules()

    return [
        RuleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            content=r.content,
            enabled=r.enabled,
            priority=r.priority,
            rule_type=r.rule_type,
        )
        for r in rules
    ]


@router.post("/")
async def create_rule(rule: RuleCreate):
    """创建规则"""
    engine = get_rules_engine()

    new_rule = Rule(
        name=rule.name,
        description=rule.description,
        content=rule.content,
        enabled=rule.enabled,
        priority=rule.priority,
        rule_type=rule.rule_type,
    )

    engine.add_rule(new_rule)

    return RuleResponse(
        id=new_rule.id,
        name=new_rule.name,
        description=new_rule.description,
        content=new_rule.content,
        enabled=new_rule.enabled,
        priority=new_rule.priority,
        rule_type=new_rule.rule_type,
    )


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    """获取单个规则"""
    engine = get_rules_engine()
    rule = engine.get_rule(rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        content=rule.content,
        enabled=rule.enabled,
        priority=rule.priority,
        rule_type=rule.rule_type,
    )


@router.patch("/{rule_id}")
async def update_rule(rule_id: str, rule_update: RuleUpdate):
    """更新规则"""
    engine = get_rules_engine()

    update_data = rule_update.model_dump(exclude_unset=True)
    success = engine.update_rule(rule_id, **update_data)

    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"success": True}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    engine = get_rules_engine()
    success = engine.delete_rule(rule_id)

    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"success": True}


@router.post("/import")
async def import_rule(file: UploadFile = File(...)):
    """从文件导入规则"""
    from pathlib import Path
    import tempfile

    engine = get_rules_engine()

    # 保存上传文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        rule = engine.import_from_document(tmp_path)
        return RuleResponse(
            id=rule.id,
            name=rule.name,
            description=rule.description,
            content=rule.content,
            enabled=rule.enabled,
            priority=rule.priority,
            rule_type=rule.rule_type,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/evaluate")
async def evaluate_rules(context: dict):
    """评估规则"""
    engine = get_rules_engine()
    results = engine.evaluate(context)
    return {"results": [r.to_dict() for r in results]}


# Templates
@router.get("/templates")
async def get_templates():
    """获取所有模板"""
    manager = get_template_manager()
    templates = manager.get_all_templates()
    return [{"id": t.id, "name": t.name, "description": t.description} for t in templates]


@router.post("/templates")
async def create_template(template: TemplateCreate):
    """创建模板"""
    manager = get_template_manager()

    new_template = AieTemplate(
        name=template.name,
        description=template.description,
        rules=template.rules,
        skills=template.skills,
        default_config=template.default_config,
    )

    manager.add_template(new_template)

    return {"id": new_template.id, "name": new_template.name}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """删除模板"""
    manager = get_template_manager()
    success = manager.delete_template(template_id)

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"success": True}
