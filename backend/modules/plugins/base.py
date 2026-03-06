"""Plugin - 插件基类"""

import os
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from .manager import PluginManager


class PluginInfo(BaseModel):
    """插件信息"""

    name: str
    version: str
    description: str
    author: str = ""
    enabled: bool = False
    options: dict[str, Any] = {}


class Plugin(ABC):
    """
    插件基类

    所有插件必须继承此类并实现必要的方法。
    """

    # 插件元信息（子类必须覆盖）
    name: str = "plugin"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    enabled_by_default: bool = False  # 默认是否启用

    # 插件选项模式（子类可以覆盖）
    options_schema: dict[str, Any] = {}

    def __init__(self, manager: "PluginManager" = None):
        """
        初始化插件

        Args:
            manager: 插件管理器实例
        """
        self._manager = manager
        self._enabled = False
        self._options: dict[str, Any] = {}

    @property
    def info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            enabled=self._enabled,
            options=self._options,
        )

    @property
    def is_enabled(self) -> bool:
        """插件是否已启用"""
        return self._enabled

    @property
    def options(self) -> dict[str, Any]:
        """获取插件选项"""
        return self._options.copy()

    def set_options(self, options: dict[str, Any]) -> None:
        """
        设置插件选项

        Args:
            options: 选项字典
        """
        self._options = options

    # =========================================================================
    # 生命周期钩子（子类可以覆盖）
    # =========================================================================

    async def on_load(self) -> None:
        """
        加载时调用

        插件被注册到管理器时调用，此时尚未启用。
        """
        pass

    async def on_unload(self) -> None:
        """
        卸载时调用

        插件从管理器移除时调用。
        """
        pass

    async def on_enable(self) -> None:
        """
        启用时调用

        插件被启用时调用。
        """
        pass

    async def on_disable(self) -> None:
        """
        禁用时调用

        插件被禁用时调用。
        """
        pass

    async def on_config_changed(self, config: dict[str, Any]) -> None:
        """
        配置变更时调用

        Args:
            config: 新的配置
        """
        pass

    # =========================================================================
    # 扩展点（子类可以覆盖）
    # =========================================================================

    def get_routes(self) -> list[Any]:
        """
        获取插件提供的路由

        Returns:
            路由列表（FastAPI Router）
        """
        return []

    def get_tools(self) -> list[Any]:
        """
        获取插件提供的工具

        Returns:
            工具列表
        """
        return []

    def get_hooks(self) -> list[Any]:
        """
        获取插件提供的钩子

        Returns:
            钩子列表
        """
        return []

    def get_static_files(self) -> dict[str, Path]:
        """
        获取插件提供的静态文件

        Returns:
            路径映射字典 {mount_path: file_path}
        """
        return {}

    # =========================================================================
    # 辅助方法
    # =========================================================================

    @property
    def workspace(self) -> Path:
        """获取工作空间路径"""
        if self._manager:
            return self._manager.workspace
        return Path.cwd()

    @property
    def data_dir(self) -> Path:
        """获取插件数据目录"""
        plugin_data_dir = Path(f"data/plugins/{self.name}")
        plugin_data_dir.mkdir(parents=True, exist_ok=True)
        return plugin_data_dir

    def load_config(self, config_name: str = None) -> dict[str, Any]:
        """
        加载插件配置文件

        Args:
            config_name: 配置文件名（不含扩展名），默认使用插件名

        Returns:
            配置字典
        """
        config_name = config_name or self.name
        config_path = Path(f"config/plugins/{config_name}.yaml")

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

        return {}

    def save_config(self, config: dict[str, Any], config_name: str = None) -> None:
        """
        保存插件配置文件

        Args:
            config: 配置字典
            config_name: 配置文件名
        """
        config_name = config_name or self.name
        config_path = Path(f"config/plugins/{config_name}.yaml")
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)

    async def emit_event(self, event: str, context: dict[str, Any] = None) -> list[Any]:
        """
        发送事件

        Args:
            event: 事件名称
            context: 上下文数据

        Returns:
            事件处理结果
        """
        if self._manager:
            return await self._manager.emit_event(event, context)
        return []
