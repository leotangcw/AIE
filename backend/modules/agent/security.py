"""AIE 数据安全与权限控制系统"""

import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from backend.utils.paths import MEMORY_DIR


class SecurityLevel(Enum):
    """安全级别"""
    PUBLIC = "public"       # 公开
    INTERNAL = "internal"   # 内部
    CONFIDENTIAL = "confidential"  # 机密
    SECRET = "secret"        # 绝密


class DataClassification:
    """数据分类"""

    def __init__(
        self,
        data_id: str,
        level: SecurityLevel,
        owner: str,
        description: str = "",
        tags: list[str] = None,
    ):
        self.id = data_id
        self.level = level
        self.owner = owner
        self.description = description
        self.tags = tags or []
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level.value,
            "owner": self.owner,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataClassification":
        return cls(
            data_id=data["id"],
            level=SecurityLevel(data["level"]),
            owner=data["owner"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )


class AieSecurityProfile:
    """AIE 安全配置文件"""

    def __init__(
        self,
        aie_id: str,
        level: SecurityLevel,
        permissions: list[str] = None,
        allowed_data_ids: list[str] = None,
        denied_data_ids: list[str] = None,
    ):
        self.aie_id = aie_id
        self.level = level
        self.permissions = permissions or []
        self.allowed_data_ids = allowed_data_ids or []
        self.denied_data_ids = denied_data_ids or []

    def can_access(self, classification: DataClassification) -> bool:
        """检查是否可以访问数据"""
        # 如果在拒绝列表，直接拒绝
        if classification.id in self.denied_data_ids:
            return False

        # 如果在允许列表，直接允许
        if classification.id in self.allowed_data_ids:
            return True

        # 检查安全级别
        level_order = [SecurityLevel.PUBLIC, SecurityLevel.INTERNAL,
                       SecurityLevel.CONFIDENTIAL, SecurityLevel.SECRET]

        # AIE 级别 >= 数据级别才能访问
        try:
            aie_index = level_order.index(self.level)
            data_index = level_order.index(classification.level)
            return aie_index >= data_index
        except ValueError:
            return False

    def to_dict(self) -> dict:
        return {
            "aie_id": self.aie_id,
            "level": self.level.value,
            "permissions": self.permissions,
            "allowed_data_ids": self.allowed_data_ids,
            "denied_data_ids": self.denied_data_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AieSecurityProfile":
        return cls(
            aie_id=data["aie_id"],
            level=SecurityLevel(data["level"]),
            permissions=data.get("permissions", []),
            allowed_data_ids=data.get("allowed_data_ids", []),
            denied_data_ids=data.get("denied_data_ids", []),
        )


class SecurityManager:
    """安全管理器"""

    def __init__(self, security_dir: Path = None):
        self.security_dir = security_dir or MEMORY_DIR / "security"
        self.security_dir.mkdir(parents=True, exist_ok=True)

        self._data_classifications: dict[str, DataClassification] = {}
        self._aie_profiles: dict[str, AieSecurityProfile] = {}
        self._enabled = False  # 默认关闭

        self._load_data()
        logger.info(f"Security manager initialized (enabled={self._enabled})")

    def _load_data(self):
        """加载数据"""
        # 加载数据分类
        classifications_file = self.security_dir / "classifications.json"
        if classifications_file.exists():
            try:
                data = json.loads(classifications_file.read_text(encoding="utf-8"))
                for item in data:
                    classification = DataClassification.from_dict(item)
                    self._data_classifications[classification.id] = classification
            except Exception as e:
                logger.warning(f"Failed to load classifications: {e}")

        # 加载 AIE 配置
        profiles_file = self.security_dir / "profiles.json"
        if profiles_file.exists():
            try:
                data = json.loads(profiles_file.read_text(encoding="utf-8"))
                for item in data:
                    profile = AieSecurityProfile.from_dict(item)
                    self._aie_profiles[profile.aie_id] = profile
            except Exception as e:
                logger.warning(f"Failed to load profiles: {e}")

        # 加载启用状态
        config_file = self.security_dir / "config.json"
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
                self._enabled = config.get("enabled", False)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

    def _save_data(self):
        """保存数据"""
        # 保存数据分类
        classifications_file = self.security_dir / "classifications.json"
        classifications_file.write_text(
            json.dumps(
                [c.to_dict() for c in self._data_classifications.values()],
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        # 保存 AIE 配置
        profiles_file = self.security_dir / "profiles.json"
        profiles_file.write_text(
            json.dumps(
                [p.to_dict() for p in self._aie_profiles.values()],
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        # 保存配置
        config_file = self.security_dir / "config.json"
        config_file.write_text(
            json.dumps({"enabled": self._enabled}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self):
        """启用安全系统"""
        self._enabled = True
        self._save_data()
        logger.info("Security system enabled")

    def disable(self):
        """禁用安全系统"""
        self._enabled = False
        self._save_data()
        logger.info("Security system disabled")

    def add_classification(self, classification: DataClassification):
        """添加数据分类"""
        self._data_classifications[classification.id] = classification
        self._save_data()
        logger.info(f"Added classification: {classification.id} ({classification.level.value})")

    def get_classification(self, data_id: str) -> Optional[DataClassification]:
        """获取数据分类"""
        return self._data_classifications.get(data_id)

    def get_all_classifications(self) -> list[DataClassification]:
        """获取所有数据分类"""
        return list(self._data_classifications.values())

    def delete_classification(self, data_id: str) -> bool:
        """删除数据分类"""
        if data_id in self._data_classifications:
            del self._data_classifications[data_id]
            self._save_data()
            return True
        return False

    def set_aie_profile(self, profile: AieSecurityProfile):
        """设置 AIE 配置"""
        self._aie_profiles[profile.aie_id] = profile
        self._save_data()
        logger.info(f"Set AIE profile: {profile.aie_id} ({profile.level.value})")

    def get_aie_profile(self, aie_id: str) -> Optional[AieSecurityProfile]:
        """获取 AIE 配置"""
        return self._aie_profiles.get(aie_id)

    def get_all_aie_profiles(self) -> list[AieSecurityProfile]:
        """获取所有 AIE 配置"""
        return list(self._aie_profiles.values())

    def delete_aie_profile(self, aie_id: str) -> bool:
        """删除 AIE 配置"""
        if aie_id in self._aie_profiles:
            del self._aie_profiles[aie_id]
            self._save_data()
            return True
        return False

    def check_access(self, aie_id: str, data_id: str) -> bool:
        """检查访问权限"""
        # 如果未启用安全系统，允许访问
        if not self._enabled:
            return True

        profile = self._aie_profiles.get(aie_id)
        if not profile:
            # 没有配置，默认为内部级别
            profile = AieSecurityProfile(
                aie_id=aie_id,
                level=SecurityLevel.INTERNAL
            )

        classification = self._data_classifications.get(data_id)
        if not classification:
            # 未分类的数据，默认允许内部级别访问
            return True

        return profile.can_access(classification)

    def filter_data_access(self, aie_id: str, data_ids: list[str]) -> list[str]:
        """过滤可访问的数据列表"""
        if not self._enabled:
            return data_ids

        return [did for did in data_ids if self.check_access(aie_id, did)]


# 全局实例
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
