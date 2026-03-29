"""Plugin Manager - 插件管理器"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .base import Plugin, PluginInfo
from .hooks import EventBus, get_event_bus


class PluginManager:
    """
    插件管理器

    负责插件的加载、启用、禁用和生命周期管理。
    """

    def __init__(self, workspace: Path = None, config_dir: Path = None):
        """
        初始化插件管理器

        Args:
            workspace: 工作空间路径
            config_dir: 配置文件目录
        """
        self.workspace = workspace or Path.cwd()
        self.config_dir = config_dir or self.workspace / "config"
        self.plugins: dict[str, Plugin] = {}
        self._event_bus: EventBus = get_event_bus()

        # 加载插件配置
        self._config = self._load_config()

        logger.info("PluginManager initialized")

    def _load_config(self) -> dict[str, Any]:
        """加载插件配置"""
        config_path = self.config_dir / "plugins.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_config(self) -> None:
        """保存插件配置"""
        config_path = self.config_dir / "plugins.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._config, f, allow_unicode=True, default_flow_style=False)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """
        获取插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            插件配置
        """
        return self._config.get("plugins", {}).get(plugin_name, {})

    def register(self, plugin: Plugin) -> None:
        """
        注册插件

        Args:
            plugin: 插件实例

        Raises:
            ValueError: 插件已存在
        """
        if plugin.name in self.plugins:
            raise ValueError(f"Plugin '{plugin.name}' already registered")

        self.plugins[plugin.name] = plugin

        # 加载插件配置
        plugin_config = self.get_plugin_config(plugin.name)
        if plugin_config:
            plugin.set_options(plugin_config.get("options", {}))

        # 注意：插件注册后不会自动启用，需要调用 async_register() 或在异步上下文中手动调用 enable_plugin()
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    async def async_register(self, plugin: Plugin) -> None:
        """
        异步注册插件（含自动启用）

        在异步上下文中使用，注册插件并根据配置自动启用。

        Args:
            plugin: 插件实例

        Raises:
            ValueError: 插件已存在
        """
        self.register(plugin)

        # 尝试启用插件（如果配置中启用）
        plugin_config = self.get_plugin_config(plugin.name)
        if plugin_config.get("enabled", plugin.enabled_by_default):
            try:
                await self.enable_plugin(plugin.name)
            except Exception as e:
                logger.warning(f"Failed to auto-enable plugin '{plugin.name}': {e}")

    async def load_plugin(self, plugin_name: str) -> bool:
        """
        加载插件（动态加载）

        Args:
            plugin_name: 插件名称

        Returns:
            是否成功
        """
        if plugin_name in self.plugins:
            logger.warning(f"Plugin '{plugin_name}' already loaded")
            return True

        # 尝试导入插件模块
        plugin_module_name = f"backend.modules.plugins.{plugin_name}.plugin"
        try:
            from importlib import import_module

            module = import_module(plugin_module_name)
            plugin_class = getattr(module, "Plugin", None)

            if plugin_class is None:
                logger.error(f"Plugin class not found in {plugin_module_name}")
                return False

            plugin = plugin_class(manager=self)
            await self.async_register(plugin)

            await plugin.on_load()
            return True

        except ImportError as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            return False

    async def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否成功启用

        Raises:
            ValueError: 插件不存在
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        if plugin.is_enabled:
            logger.debug(f"Plugin '{plugin_name}' already enabled")
            return True

        # 调用启用钩子
        await plugin.on_enable()

        # 注册插件的钩子
        for hook in plugin.get_hooks():
            self._event_bus.register(hook)

        plugin._enabled = True

        # 更新配置
        if "plugins" not in self._config:
            self._config["plugins"] = {}
        if plugin_name not in self._config["plugins"]:
            self._config["plugins"][plugin_name] = {}
        self._config["plugins"][plugin_name]["enabled"] = True
        self._save_config()

        logger.info(f"Enabled plugin: {plugin_name}")
        return True

    async def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否成功禁用

        Raises:
            ValueError: 插件不存在
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        if not plugin.is_enabled:
            logger.debug(f"Plugin '{plugin_name}' already disabled")
            return True

        plugin._enabled = False

        # 注销插件的钩子（简化处理，实际应该保存钩子引用）
        # 暂不实现，因为需要保存钩子引用

        # 调用禁用钩子
        await plugin.on_disable()

        # 更新配置
        if "plugins" in self._config and plugin_name in self._config["plugins"]:
            self._config["plugins"][plugin_name]["enabled"] = False
            self._save_config()

        logger.info(f"Disabled plugin: {plugin_name}")
        return True

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        获取插件实例

        Args:
            plugin_name: 插件名称

        Returns:
            插件实例，如果不存在返回None
        """
        return self.plugins.get(plugin_name)

    def list_plugins(self, enabled_only: bool = False) -> list[PluginInfo]:
        """
        列出所有插件

        Args:
            enabled_only: 只返回已启用的插件

        Returns:
            插件信息列表
        """
        plugins = []
        for plugin in self.plugins.values():
            if enabled_only and not plugin.is_enabled:
                continue
            plugins.append(plugin.info)

        return plugins

    def is_enabled(self, plugin_name: str) -> bool:
        """
        检查插件是否已启用

        Args:
            plugin_name: 插件名称

        Returns:
            是否启用
        """
        plugin = self.plugins.get(plugin_name)
        return plugin.is_enabled if plugin else False

    async def emit_event(
        self,
        event: str,
        context: dict[str, Any] = None,
    ) -> list[Any]:
        """
        发送事件到所有已启用的插件

        Args:
            event: 事件名称
            context: 上下文数据

        Returns:
            事件处理结果
        """
        return await self._event_bus.emit(event, context or {})

    def get_event_hooks(self) -> dict[str, list[str]]:
        """
        获取所有已注册的钩子

        Returns:
            事件到钩子的映射
        """
        return self._event_bus.list_hooks()

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否成功
        """
        # 禁用插件
        if plugin_name in self.plugins:
            await self.disable_plugin(plugin_name)

        # 重新加载插件
        return await self.load_plugin(plugin_name)


# 全局插件管理器实例
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """设置全局插件管理器实例"""
    global _plugin_manager
    _plugin_manager = manager
