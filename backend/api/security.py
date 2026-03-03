"""数据安全 API"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from backend.modules.agent.security import (
    SecurityManager,
    SecurityLevel,
    DataClassification,
    AieSecurityProfile,
    get_security_manager,
)

router = APIRouter(prefix="/api/security", tags=["security"])


class SecurityConfig(BaseModel):
    """安全配置"""
    enabled: bool


class DataClassificationCreate(BaseModel):
    """创建数据分类"""
    data_id: str
    level: str  # public, internal, confidential, secret
    owner: str
    description: str = ""
    tags: list[str] = []


class AieProfileCreate(BaseModel):
    """创建 AIE 配置"""
    aie_id: str
    level: str
    permissions: list[str] = []
    allowed_data_ids: list[str] = []
    denied_data_ids: list[str] = []


@router.get("/config")
async def get_config():
    """获取安全配置"""
    manager = get_security_manager()
    return {"enabled": manager.is_enabled}


@router.post("/config")
async def set_config(config: SecurityConfig):
    """设置安全配置"""
    manager = get_security_manager()

    if config.enabled:
        manager.enable()
    else:
        manager.disable()

    return {"enabled": manager.is_enabled}


# Data Classifications
@router.get("/classifications")
async def get_classifications():
    """获取所有数据分类"""
    manager = get_security_manager()
    classifications = manager.get_all_classifications()

    return [
        {
            "id": c.id,
            "level": c.level.value,
            "owner": c.owner,
            "description": c.description,
            "tags": c.tags,
            "created_at": c.created_at,
        }
        for c in classifications
    ]


@router.post("/classifications")
async def create_classification(create: DataClassificationCreate):
    """创建数据分类"""
    manager = get_security_manager()

    classification = DataClassification(
        data_id=create.data_id,
        level=SecurityLevel(create.level),
        owner=create.owner,
        description=create.description,
        tags=create.tags,
    )

    manager.add_classification(classification)

    return {
        "id": classification.id,
        "level": classification.level.value,
        "owner": classification.owner,
    }


@router.delete("/classifications/{data_id}")
async def delete_classification(data_id: str):
    """删除数据分类"""
    manager = get_security_manager()
    success = manager.delete_classification(data_id)

    if not success:
        raise HTTPException(status_code=404, detail="Classification not found")

    return {"success": True}


# AIE Profiles
@router.get("/profiles")
async def get_profiles():
    """获取所有 AIE 配置"""
    manager = get_security_manager()
    profiles = manager.get_all_aie_profiles()

    return [
        {
            "aie_id": p.aie_id,
            "level": p.level.value,
            "permissions": p.permissions,
            "allowed_data_ids": p.allowed_data_ids,
            "denied_data_ids": p.denied_data_ids,
        }
        for p in profiles
    ]


@router.post("/profiles")
async def create_profile(create: AieProfileCreate):
    """创建 AIE 配置"""
    manager = get_security_manager()

    profile = AieSecurityProfile(
        aie_id=create.aie_id,
        level=SecurityLevel(create.level),
        permissions=create.permissions,
        allowed_data_ids=create.allowed_data_ids,
        denied_data_ids=create.denied_data_ids,
    )

    manager.set_aie_profile(profile)

    return {"aie_id": profile.aie_id, "level": profile.level.value}


@router.delete("/profiles/{aie_id}")
async def delete_profile(aie_id: str):
    """删除 AIE 配置"""
    manager = get_security_manager()
    success = manager.delete_aie_profile(aie_id)

    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {"success": True}


@router.post("/check-access")
async def check_access(aie_id: str, data_id: str):
    """检查访问权限"""
    manager = get_security_manager()
    allowed = manager.check_access(aie_id, data_id)

    return {"allowed": allowed, "aie_id": aie_id, "data_id": data_id}


@router.post("/filter-access")
async def filter_access(aie_id: str, data_ids: list[str]):
    """过滤可访问的数据"""
    manager = get_security_manager()
    allowed_ids = manager.filter_data_access(aie_id, data_ids)

    return {"allowed_ids": allowed_ids, "total": len(data_ids), "allowed": len(allowed_ids)}
