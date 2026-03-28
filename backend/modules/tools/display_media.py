"""display_media 工具 - 在 Web 界面展示媒体文件"""

import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.modules.tools.base import Tool
from backend.modules.tools.multimodal_tools import _build_file_url
from backend.utils.paths import WORKSPACE_DIR

# 自动检测 media_type 的扩展名映射
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv'}


class DisplayMediaTool(Tool):
    """在 Web 聊天窗口展示媒体文件（图片、音频、视频、文件）"""

    def __init__(self, workspace: Optional[Path] = None, pending_media: Optional[list] = None):
        super().__init__()
        self.workspace = workspace or WORKSPACE_DIR
        self._pending_media = pending_media  # 由 loop.py 传入，用于持久化
        self._current_session_id = None

    def set_session_id(self, session_id: str):
        """设置当前会话 ID"""
        self._current_session_id = session_id

    @property
    def name(self) -> str:
        return "display_media"

    @property
    def description(self) -> str:
        return (
            "Display a media file (image, audio, video, document) to the user in the chat window. "
            "Use this after generating or downloading any file you want the user to see."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path or workspace-relative path to the file",
                },
                "media_type": {
                    "type": "string",
                    "enum": ["image", "audio", "video", "file"],
                    "description": "Media type (auto-detected from extension if omitted)",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption or description",
                },
            },
            "required": ["file_path"],
        }

    def _detect_media_type(self, file_path: Path) -> str:
        """从文件扩展名推断媒体类型"""
        ext = file_path.suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        return "file"

    async def execute(self, file_path: str, media_type: Optional[str] = None, caption: Optional[str] = None) -> str:
        """展示媒体文件"""
        try:
            # 解析为绝对路径
            path = Path(file_path)
            if not path.is_absolute():
                path = self.workspace / path
            path = path.resolve()

            # 验证文件存在
            if not path.exists():
                return json.dumps({
                    "success": False,
                    "error": f"文件不存在: {path}",
                })

            # 自动检测 media_type
            if not media_type:
                media_type = self._detect_media_type(path)

            # 构建 URL
            src = _build_file_url(str(path))
            if not src:
                return json.dumps({
                    "success": False,
                    "error": f"文件不在 workspace 范围内，无法构建访问 URL: {path}",
                })

            # 通过 WebSocket 推送到前端
            if self._current_session_id:
                try:
                    from backend.ws.connection import send_media_generated
                    await send_media_generated(
                        session_id=self._current_session_id,
                        media_type=media_type,
                        src=src,
                        name=path.name,
                        alt=caption or f"display_media: {path.name}",
                        tool_name="display_media",
                    )
                    logger.info(f"display_media: pushed {media_type} to session {self._current_session_id}: {path.name}")
                except Exception as ws_err:
                    logger.warning(f"display_media: WebSocket 推送失败: {ws_err}")

            # 记录到 pending_media（由 loop.py 持久化到 DB）
            if self._pending_media is not None:
                self._pending_media.append({
                    "media_type": media_type,
                    "src": src,
                    "name": path.name,
                    "alt": caption,
                    "tool_name": "display_media",
                })

            return json.dumps({
                "success": True,
                "path": str(path),
                "url": src,
                "media_type": media_type,
            })

        except Exception as e:
            logger.error(f"display_media 执行失败: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
            })
