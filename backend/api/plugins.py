"""Plugins API - 插件管理接口"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from loguru import logger

from backend.modules.plugins import PluginManager, get_plugin_manager
from backend.modules.plugins.base import PluginInfo

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PluginEnableRequest(BaseModel):
    """启用/禁用插件请求"""

    enabled: bool


class PluginOptionsRequest(BaseModel):
    """更新插件选项请求"""

    options: dict


class PluginListResponse(BaseModel):
    """插件列表响应"""

    plugins: list[PluginInfo]
    total: int


class PluginDetailResponse(BaseModel):
    """插件详情响应"""

    info: PluginInfo
    config: dict


# ============================================================================
# Plugins Endpoints
# ============================================================================


@router.get("/", response_model=PluginListResponse)
async def list_plugins(enabled_only: bool = False) -> PluginListResponse:
    """
    列出所有插件

    Args:
        enabled_only: 只返回已启用的插件

    Returns:
        PluginListResponse: 插件列表
    """
    try:
        manager = get_plugin_manager()
        plugins = manager.list_plugins(enabled_only=enabled_only)

        return PluginListResponse(
            plugins=plugins,
            total=len(plugins),
        )

    except Exception as e:
        logger.exception(f"Failed to list plugins: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list plugins: {str(e)}",
        )


@router.get("/{plugin_name}", response_model=PluginDetailResponse)
async def get_plugin(plugin_name: str) -> PluginDetailResponse:
    """
    获取插件详情

    Args:
        plugin_name: 插件名称

    Returns:
        PluginDetailResponse: 插件详情

    Raises:
        HTTPException: 插件不存在
    """
    try:
        manager = get_plugin_manager()
        plugin = manager.get_plugin(plugin_name)

        if plugin is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin '{plugin_name}' not found",
            )

        # 获取插件配置
        config = manager.get_plugin_config(plugin_name)

        return PluginDetailResponse(
            info=plugin.info,
            config=config,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get plugin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plugin: {str(e)}",
        )


@router.post("/{plugin_name}/enable")
async def enable_plugin(
    plugin_name: str,
    request: PluginEnableRequest,
) -> dict:
    """
    启用或禁用插件

    Args:
        plugin_name: 插件名称
        request: 请求体

    Returns:
        dict: 操作结果
    """
    try:
        manager = get_plugin_manager()

        if request.enabled:
            await manager.enable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' enabled"
        else:
            await manager.disable_plugin(plugin_name)
            message = f"Plugin '{plugin_name}' disabled"

        return {"success": True, "message": message}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Failed to toggle plugin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle plugin: {str(e)}",
        )


@router.post("/{plugin_name}/reload")
async def reload_plugin(plugin_name: str) -> dict:
    """
    重新加载插件

    Args:
        plugin_name: 插件名称

    Returns:
        dict: 操作结果
    """
    try:
        manager = get_plugin_manager()
        success = await manager.reload_plugin(plugin_name)

        if success:
            return {"success": True, "message": f"Plugin '{plugin_name}' reloaded"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reload plugin '{plugin_name}'",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to reload plugin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload plugin: {str(e)}",
        )


@router.get("/hooks")
async def list_hooks() -> dict:
    """
    列出所有已注册的钩子

    Returns:
        dict: 钩子列表
    """
    try:
        manager = get_plugin_manager()
        hooks = manager.get_event_hooks()

        return {"hooks": hooks}

    except Exception as e:
        logger.exception(f"Failed to list hooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list hooks: {str(e)}",
        )
