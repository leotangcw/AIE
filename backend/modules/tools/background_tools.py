"""后台任务工具 - run_background + check_task

提供非阻塞的后台任务执行能力：
- run_background: 将耗时操作（视频生成、音乐生成等）放入后台执行，不阻塞主对话
- check_task: 查询后台任务状态和结果
"""

import json
from typing import Any, Optional

from loguru import logger

from backend.modules.tools.base import Tool


class RunBackgroundTool(Tool):
    """在后台执行耗时操作（视频生成、音乐生成等），不阻塞主对话。"""

    def __init__(self, subagent_manager):
        self._subagent_manager = subagent_manager

    @property
    def name(self) -> str:
        return "run_background"

    @property
    def description(self) -> str:
        return (
            "Run a time-consuming tool in the background without blocking the conversation. "
            "Use this for video generation (1-5 min), music generation, or other long operations. "
            "Returns immediately with a task_id. Use check_task to get the result later."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": ["generate_video", "generate_music", "minimax_text_to_speech"],
                    "description": "The tool to execute in the background",
                },
                "args": {
                    "type": "object",
                    "description": "Arguments for the tool (same as the original tool's parameters)",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable task label (optional, auto-generated if omitted)",
                },
            },
            "required": ["tool_name", "args"],
        }

    async def execute(self, **kwargs: Any) -> str:
        tool_name = kwargs.get("tool_name", "")
        args = kwargs.get("args", {})
        label = kwargs.get("label", "")

        if not tool_name:
            return json.dumps({"success": False, "error": "tool_name is required"})

        if not args:
            return json.dumps({"success": False, "error": "args is required"})

        # 获取当前会话 ID
        session_id = getattr(self, '_session_id', None)

        # 自动生成标签
        if not label:
            label_map = {
                "generate_video": "视频生成",
                "generate_music": "音乐生成",
                "minimax_text_to_speech": "语音合成",
            }
            label = label_map.get(tool_name, f"后台任务: {tool_name}")

        try:
            # 从已注册的工具中找到对应的 provider
            executor = await self._build_executor(tool_name, args)

            if executor is None:
                return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})

            # 创建并启动后台任务
            task_id = self._subagent_manager.create_tool_task(
                label=label,
                executor=executor,
                session_id=session_id,
                estimated_duration=self._estimate_duration(tool_name),
            )

            await self._subagent_manager.execute_task(task_id)

            return json.dumps({
                "success": True,
                "task_id": task_id,
                "status": "running",
                "message": f"后台任务已启动: {label}",
                "label": label,
            })

        except Exception as e:
            logger.error(f"Failed to start background task: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def _build_executor(self, tool_name: str, args: dict):
        """为指定工具构建 executor（一个 async callable）"""
        try:
            from backend.modules.tools.setup import register_all_tools
            from backend.modules.config.loader import config_loader
            from backend.utils.paths import WORKSPACE_DIR
        except ImportError as e:
            logger.error(f"Missing import for _build_executor: {e}")
            return None

        workspace = WORKSPACE_DIR

        if tool_name == "generate_video":
            return await self._build_video_executor(args)
        elif tool_name == "generate_music":
            return await self._build_music_executor(args)
        elif tool_name == "minimax_text_to_speech":
            return await self._build_tts_executor(args)
        else:
            return None

    async def _build_video_executor(self, args: dict):
        """构建视频生成 executor"""
        from backend.modules.output.minimax_video import MinimaxVideoProvider
        from backend.modules.config.loader import config_loader

        api_key = None
        api_base = "https://api.minimaxi.com/v1"
        default_model = "MiniMax-Hailuo-2.3"

        # 从配置中获取
        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if model.enabled:
                    from backend.modules.tools.setup import register_all_tools as _r
                    provider_config = config_loader.config.providers.get(model.provider, {})
                    if provider_config:
                        api_key = model.api_key or provider_config.api_key
                        api_base = model.api_base or provider_config.api_base or api_base
                    if model.model:
                        default_model = model.model
                    break

        provider = MinimaxVideoProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
        )

        # Capture args for closure
        prompt = args.get("prompt", "")
        model = args.get("model")
        first_frame_image = args.get("first_frame_image")
        duration = args.get("duration", 6)
        resolution = args.get("resolution", "1080P")

        async def executor(progress_callback, cancel_check):
            result = await provider.generate(
                prompt=prompt,
                model=model,
                first_frame_image=first_frame_image,
                duration=duration,
                resolution=resolution,
                progress_callback=progress_callback,
            )
            return result

        return executor

    async def _build_music_executor(self, args: dict):
        """构建音乐生成 executor"""
        from backend.modules.output.minimax_music import MinimaxMusicProvider
        from backend.modules.config.loader import config_loader

        api_key = None
        api_base = "https://api.minimaxi.com/v1"
        default_model = "music-2.5"

        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if model.enabled and 'music' in model.model.lower():
                    provider_config = config_loader.config.providers.get(model.provider, {})
                    if provider_config:
                        api_key = model.api_key or provider_config.api_key
                        api_base = model.api_base or provider_config.api_base or api_base
                    if model.model:
                        default_model = model.model
                    break

        provider = MinimaxMusicProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
        )

        prompt = args.get("prompt", "")
        lyrics = args.get("lyrics")
        instrumental = args.get("instrumental", False)

        async def executor(progress_callback, cancel_check):
            # 简单进度模拟（Music API 不支持进度查询）
            if progress_callback:
                await progress_callback(10, "音乐生成中...")
            result = await provider.generate(
                prompt=prompt,
                lyrics=lyrics,
                instrumental=instrumental,
            )
            if progress_callback:
                await progress_callback(100, "音乐生成完成")
            return result

        return executor

    async def _build_tts_executor(self, args: dict):
        """构建 TTS executor"""
        from backend.modules.output.minimax_tts import MinimaxTTSProvider
        from backend.modules.config.loader import config_loader

        api_key = None
        api_base = "https://api.minimaxi.com/v1"
        default_model = "speech-2.8"
        default_voice = "male-qn-qingse"

        if hasattr(config_loader, 'config') and hasattr(config_loader.config, 'enhanced_models'):
            for model in config_loader.config.enhanced_models:
                if model.enabled and 'speech' in model.model.lower():
                    provider_config = config_loader.config.providers.get(model.provider, {})
                    if provider_config:
                        api_key = model.api_key or provider_config.api_key
                        api_base = model.api_base or provider_config.api_base or api_base
                    if model.model:
                        default_model = model.model
                    break

        provider = MinimaxTTSProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            default_voice=default_voice,
        )

        text = args.get("text", "")
        voice = args.get("voice")
        speed = args.get("speed", 1.0)

        async def executor(progress_callback, cancel_check):
            result = await provider.speak(
                text=text,
                model=args.get("model"),
                voice=voice,
                speed=speed,
            )
            return result

        return executor

    def _estimate_duration(self, tool_name: str) -> int:
        """预估任务时长（秒）"""
        estimates = {
            "generate_video": 300,       # 5 分钟
            "generate_music": 180,       # 3 分钟
            "minimax_text_to_speech": 60, # 1 分钟
        }
        return estimates.get(tool_name, 120)

    def set_session_id(self, session_id: str):
        """设置当前会话 ID"""
        self._session_id = session_id


class CheckTaskTool(Tool):
    """检查后台任务状态和结果。"""

    def __init__(self, subagent_manager):
        self._subagent_manager = subagent_manager

    @property
    def name(self) -> str:
        return "check_task"

    @property
    def description(self) -> str:
        return (
            "Check the status and result of a background task started with run_background. "
            "If task_id is omitted, returns all tasks for the current session."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to check (optional; omit to list all session tasks)",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        task_id = kwargs.get("task_id")
        session_id = getattr(self, '_session_id', None)

        if task_id:
            # 查询单个任务
            task = self._subagent_manager.get_task(task_id)
            if not task:
                return json.dumps({"success": False, "error": f"Task {task_id} not found"})

            result = {
                "task_id": task.task_id,
                "label": task.label,
                "status": task.status,
                "progress": task.progress,
                "is_tool_task": task.is_tool_task,
            }

            if task.status == "done" and task.result:
                try:
                    result["result"] = json.loads(task.result)
                except (json.JSONDecodeError, TypeError):
                    result["result"] = task.result

            if task.status == "failed":
                result["error"] = task.error

            if task.started_at:
                result["started_at"] = task.started_at.isoformat()
            if task.completed_at:
                result["completed_at"] = task.completed_at.isoformat()
            if task.duration:
                result["duration_seconds"] = task.duration

            return json.dumps(result, ensure_ascii=False)

        else:
            # 列出所有会话任务
            if not session_id:
                return json.dumps({"success": False, "error": "No session_id available"})

            tasks = self._subagent_manager.get_session_tasks(session_id)
            task_list = []
            for t in tasks:
                item = {
                    "task_id": t.task_id,
                    "label": t.label,
                    "status": t.status,
                    "progress": t.progress,
                    "is_tool_task": t.is_tool_task,
                }
                if t.duration:
                    item["duration_seconds"] = t.duration
                task_list.append(item)

            return json.dumps({
                "total": len(task_list),
                "tasks": task_list,
            }, ensure_ascii=False)

    def set_session_id(self, session_id: str):
        """设置当前会话 ID"""
        self._session_id = session_id
