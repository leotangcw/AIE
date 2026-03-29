"""工具注册统一配置模块"""

from pathlib import Path
from loguru import logger

from backend.modules.tools.registry import ToolRegistry


def register_all_tools(
    workspace: Path,
    command_timeout: int = 30,
    max_output_length: int = 10000,
    allow_dangerous: bool = False,
    restrict_to_workspace: bool = True,
    custom_deny_patterns: list[str] | None = None,
    custom_allow_patterns: list[str] | None = None,
    audit_log_enabled: bool = True,
    subagent_manager=None,
    skills_loader=None,
    session_id: str | None = None,
    channel_manager=None,
    session_manager=None,
    memory_store=None,
) -> ToolRegistry:
    """
    注册所有可用工具
    
    Args:
        workspace: 工作空间路径
        command_timeout: 命令超时时间（秒）
        max_output_length: 最大输出长度（字符）
        allow_dangerous: 是否允许危险命令
        restrict_to_workspace: 是否限制在工作空间内
        custom_deny_patterns: 自定义拒绝模式列表
        custom_allow_patterns: 自定义允许模式列表
        audit_log_enabled: 是否启用审计日志
        subagent_manager: SubagentManager 实例（可选）
        skills_loader: SkillsLoader 实例（可选，用于检查禁用的技能）
        session_id: 会话 ID（可选，用于审计日志）
        channel_manager: ChannelManager 实例（可选）
        session_manager: SessionManager 实例（可选）
        memory_store: MemoryStore 实例（可选，用于记忆工具）
        
    Returns:
        ToolRegistry: 已注册所有工具的注册表
    """
    tools = ToolRegistry()
    
    # 配置审计日志
    tools.set_audit_enabled(audit_log_enabled)
    if session_id:
        tools.set_session_id(session_id)
    
    # 1. 注册文件系统工具（AI 可用，但前端隐藏）
    from backend.modules.tools.filesystem import (
        ReadFileTool,
        WriteFileTool,
        EditFileTool,
        ListDirTool,
    )
    
    tools.register(ReadFileTool(workspace, skills_loader=skills_loader, restrict_to_workspace=restrict_to_workspace))
    tools.register(WriteFileTool(workspace, restrict_to_workspace=restrict_to_workspace))
    tools.register(EditFileTool(workspace, restrict_to_workspace=restrict_to_workspace))
    tools.register(ListDirTool(workspace, restrict_to_workspace=restrict_to_workspace))
    logger.debug("Registered filesystem tools")
    
    # 2. 注册 Shell 工具（AI 可用，但前端隐藏）
    from backend.modules.tools.shell import ExecTool
    
    # 合并自定义拒绝模式
    deny_patterns = None
    if custom_deny_patterns:
        from backend.modules.tools.shell import DANGEROUS_PATTERNS
        deny_patterns = list(DANGEROUS_PATTERNS) + custom_deny_patterns
    
    tools.register(
        ExecTool(
            workspace=workspace,
            timeout=command_timeout,
            max_output_length=max_output_length,
            allow_dangerous=allow_dangerous,
            deny_patterns=deny_patterns,
            allow_patterns=custom_allow_patterns,
            restrict_to_workspace=restrict_to_workspace,
        )
    )
    logger.debug(
        f"Registered shell tools (dangerous_blocked={not allow_dangerous}, "
        f"workspace_restricted={restrict_to_workspace})"
    )
    
    # 3. 注册 Web 工具
    try:
        from backend.modules.tools.web import WebFetchTool
        
        tools.register(WebFetchTool())
        logger.debug("Registered web fetch tool")
    except ImportError:
        logger.warning("Web tools not available")
    
    # 4. 注册 Spawn 工具（如果提供了 SubagentManager）
    if subagent_manager is not None:
        try:
            from backend.modules.tools.spawn import SpawnTool

            spawn_tool = SpawnTool(subagent_manager)
            # 设置当前会话 ID（用于任务追踪）
            if session_id:
                spawn_tool.set_context(session_id)
            tools.register(spawn_tool)
            logger.debug("Registered spawn tool")
        except Exception as e:
            logger.error(f"Failed to register spawn tool: {e}")

        # 4b. 注册 Workflow 工具（如果提供了 SubagentManager）
        try:
            from backend.modules.tools.workflow_tool import WorkflowTool

            workflow_tool = WorkflowTool(subagent_manager, skills=skills_loader)
            if session_id:
                workflow_tool.set_session_id(session_id)
            tools.register(workflow_tool)
            logger.debug("Registered workflow tool")
        except Exception as e:
            logger.error(f"Failed to register workflow tool: {e}")

        # 4.5 注册后台任务工具（run_background + check_task）
        try:
            from backend.modules.tools.background_tools import RunBackgroundTool, CheckTaskTool

            bg_tool = RunBackgroundTool(subagent_manager)
            if session_id:
                bg_tool.set_session_id(session_id)
            tools.register(bg_tool)

            check_tool = CheckTaskTool(subagent_manager)
            if session_id:
                check_tool.set_session_id(session_id)
            tools.register(check_tool)
            logger.debug("Registered background task tools (run_background, check_task)")
        except Exception as e:
            logger.error(f"Failed to register background task tools: {e}")
    
    # 5. 注册发送媒体工具（如果提供了 ChannelManager）
    if channel_manager is not None:
        try:
            from backend.modules.tools.send_media import SendMediaTool
            
            send_media_tool = SendMediaTool(
                channel_manager=channel_manager,
                session_manager=session_manager
            )
            # 设置当前会话 ID
            if session_id:
                send_media_tool.set_session_id(session_id)
            tools.register(send_media_tool)
            logger.debug("Registered send_media tool")
        except Exception as e:
            logger.error(f"Failed to register send_media tool: {e}")
    
    # 5.5 注册 display_media 工具（Web 界面展示媒体的基础工具）
    # 先创建 _pending_media 列表，供 display_media 和 loop.py 共用
    _pending_media: list[dict] = []
    try:
        from backend.modules.tools.display_media import DisplayMediaTool

        display_media_tool = DisplayMediaTool(workspace=workspace, pending_media=_pending_media)
        tools.register(display_media_tool)
        logger.debug("Registered display_media tool")
    except Exception as e:
        logger.error(f"Failed to register display_media tool: {e}")

    # 6. 注册截图工具
    try:
        from backend.modules.tools.screenshot import ScreenshotTool
        
        screenshot_tool = ScreenshotTool(workspace=workspace)
        tools.register(screenshot_tool)
        logger.debug("Registered screenshot tool")
    except Exception as e:
        logger.error(f"Failed to register screenshot tool: {e}")
    
    # 7. 注册文件搜索工具
    try:
        from backend.modules.tools.file_search import FileSearchTool
        
        file_search_tool = FileSearchTool(default_max_results=20)
        tools.register(file_search_tool)
        logger.debug("Registered file search tool")
    except Exception as e:
        logger.error(f"Failed to register file search tool: {e}")
    
    # 8. 注册记忆工具
    if memory_store is not None:
        try:
            from backend.modules.tools.memory_tool import (
                MemoryWriteTool,
                MemorySearchTool,
                MemoryReadTool,
            )

            tools.register(MemoryWriteTool(memory_store))
            tools.register(MemorySearchTool(memory_store))
            tools.register(MemoryReadTool(memory_store))
            logger.debug("Registered memory tools")
        except Exception as e:
            logger.error(f"Failed to register memory tools: {e}")

    # 9. 注册向量记忆工具 (Memory-MCP-Server)
    try:
        from backend.modules.tools.vector_memory_tool import (
            VectorMemoryStoreTool,
            VectorMemoryRecallTool,
            VectorMemoryGetTool,
            VectorMemoryStatsTool,
        )

        tools.register(VectorMemoryStoreTool())
        tools.register(VectorMemoryRecallTool())
        tools.register(VectorMemoryGetTool())
        tools.register(VectorMemoryStatsTool())
        logger.debug("Registered vector memory tools")
    except Exception as e:
        logger.warning(f"Failed to register vector memory tools: {e}")

    # 10. 注册多模态生成工具（图像生成、TTS、视频理解、音乐生成、视频生成）
    def _resolve_model_type(model_config, provider_id: str | None) -> str | None:
        """解析实际的 model_type，优先使用 provider registry 的映射"""
        db_type = model_config.model_type
        if provider_id:
            from backend.modules.providers.registry import PROVIDER_REGISTRY
            provider_meta = PROVIDER_REGISTRY.get(provider_id)
            if provider_meta and provider_meta.model_overrides:
                override = provider_meta.model_overrides.get(model_config.model)
                if override and 'model_type' in override:
                    return override['model_type']
        return db_type

    try:
        from backend.modules.tools.multimodal_tools import (
            GenerateImageTool,
            TextToSpeechTool,
            UnderstandVideoTool,
            GenerateMusicTool,
            GenerateVideoTool,
            MiniMaxTextToSpeechTool,
        )
        from backend.modules.config.loader import config_loader

        # Try to get image generation config from enhanced_models
        image_gen_config = None
        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if _resolve_model_type(model, model.provider) == 'image_gen' and model.enabled:
                    image_gen_config = model
                    logger.info(f"Found enabled image_gen model: {model.model} from {model.provider}")
                    break

        if image_gen_config:
            # Get provider API config
            provider_config = config_loader.config.providers.get(image_gen_config.provider, {})
            api_key = image_gen_config.api_key or provider_config.api_key
            api_base = image_gen_config.api_base or provider_config.api_base

            tools.register(GenerateImageTool(
                api_key=api_key,
                api_base=api_base,
                default_model=image_gen_config.model,
            ))
            logger.info(f"Registered image generation tool with {image_gen_config.provider}/{image_gen_config.model}")
        else:
            # Fall back to default (local SD)
            tools.register(GenerateImageTool())
            logger.warning("No enabled image_gen model found, using default local config")

        # Try to get TTS config from enhanced_models
        tts_config = None
        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if _resolve_model_type(model, model.provider) == 'audio_gen' and model.enabled:
                    tts_config = model
                    logger.info(f"Found enabled audio_gen model: {model.model} from {model.provider}")
                    break

        if tts_config:
            provider_config = config_loader.config.providers.get(tts_config.provider, {})
            api_key = tts_config.api_key or provider_config.api_key
            api_base = tts_config.api_base or provider_config.api_base

            # Detect MiniMax provider → use MiniMax-specific TTS tool
            is_minimax = (
                tts_config.provider == "minimax"
                or (api_base and any(d in api_base.lower() for d in ("minimaxi.com", "minimax.chat")))
            )

            if is_minimax:
                tools.register(MiniMaxTextToSpeechTool(
                    api_key=api_key,
                    api_base=api_base,
                    default_model=tts_config.model,
                ))
                logger.info(f"Registered MiniMax TTS tool with {tts_config.provider}/{tts_config.model}")
            else:
                tools.register(TextToSpeechTool(
                    api_key=api_key,
                    api_base=api_base,
                    default_model=tts_config.model,
                ))
                logger.info(f"Registered TTS tool with {tts_config.provider}/{tts_config.model}")
        else:
            tools.register(TextToSpeechTool())
            logger.debug("No enabled audio_gen model found, using default TTS config")

        # Try to get music generation config from enhanced_models
        music_gen_config = None
        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if _resolve_model_type(model, model.provider) == 'music_gen' and model.enabled:
                    music_gen_config = model
                    logger.info(f"Found enabled music_gen model: {model.model} from {model.provider}")
                    break

        if music_gen_config:
            provider_config = config_loader.config.providers.get(music_gen_config.provider, {})
            api_key = music_gen_config.api_key or provider_config.api_key
            api_base = music_gen_config.api_base or provider_config.api_base

            tools.register(GenerateMusicTool(
                api_key=api_key,
                api_base=api_base,
                default_model=music_gen_config.model,
            ))
            logger.info(f"Registered music generation tool with {music_gen_config.provider}/{music_gen_config.model}")

        # Try to get video generation config from enhanced_models
        video_gen_config = None
        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if _resolve_model_type(model, model.provider) == 'video_gen' and model.enabled:
                    video_gen_config = model
                    logger.info(f"Found enabled video_gen model: {model.model} from {model.provider}")
                    break

        if video_gen_config:
            provider_config = config_loader.config.providers.get(video_gen_config.provider, {})
            api_key = video_gen_config.api_key or provider_config.api_key
            api_base = video_gen_config.api_base or provider_config.api_base

            tools.register(GenerateVideoTool(
                api_key=api_key,
                api_base=api_base,
                default_model=video_gen_config.model,
            ))
            logger.info(f"Registered video generation tool with {video_gen_config.provider}/{video_gen_config.model}")

        tools.register(UnderstandVideoTool())
        logger.debug("Registered multimodal generation tools")
    except Exception as e:
        logger.error(f"Failed to register multimodal tools: {e}")

    # 11. 注册 GraphRAG 工具（知识图谱检索）
    try:
        from backend.modules.graph_rag.skill import register_graph_rag_tools

        register_graph_rag_tools(tools)
        logger.debug("Registered GraphRAG tools")
    except ImportError:
        logger.debug("GraphRAG tools not available (LightRAG not installed)")
    except Exception as e:
        logger.warning(f"Failed to register GraphRAG tools: {e}")

    logger.debug(f"Registered {len(tools.get_definitions())} tools")
    return tools
