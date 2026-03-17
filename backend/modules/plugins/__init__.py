"""Plugins - 插件系统基础"""

from .base import Plugin, PluginInfo
from .manager import PluginManager, get_plugin_manager
from .hooks import Hook, EventBus, EVENTS

__all__ = [
    "Plugin",
    "PluginInfo",
    "PluginManager",
    "get_plugin_manager",
    "Hook",
    "EventBus",
    "EVENTS",
]
