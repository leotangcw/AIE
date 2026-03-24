"""Multimodal generation tools - 图像生成、TTS 和视频理解工具

提供 AI 图像生成、文本转语音和视频内容理解功能。
"""

import json
from typing import Any, Optional

from loguru import logger

from backend.modules.output.image_generator import ImageGenerator
from backend.modules.output.tts_provider import TTSProvider
from backend.modules.output.video_understanding import VideoUnderstanding
from backend.modules.tools.base import Tool


class GenerateImageTool(Tool):
    """图像生成工具 - 通过 AI 模型生成图像"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "http://localhost:7860/v1",
        default_model: str = "stable-diffusion",
    ):
        """
        初始化图像生成工具

        Args:
            api_key: API 密钥（可选）
            api_base: API 基础 URL
            default_model: 默认模型
        """
        self.generator = ImageGenerator(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
        )
        logger.debug(f"GenerateImageTool initialized with model={default_model}")

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return "Generate images from text prompts using AI models (Stable Diffusion, DALL-E, etc.)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text prompt describing the image to generate",
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Negative prompt (things to avoid in the image)",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for generation (optional)",
                },
                "width": {
                    "type": "integer",
                    "description": "Image width in pixels",
                    "minimum": 256,
                    "maximum": 2048,
                },
                "height": {
                    "type": "integer",
                    "description": "Image height in pixels",
                    "minimum": 256,
                    "maximum": 2048,
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of generation steps",
                    "minimum": 1,
                    "maximum": 150,
                },
                "seed": {
                    "type": "integer",
                    "description": "Random seed for reproducibility",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行图像生成

        Args:
            prompt (str): 生成提示词
            negative_prompt (str, optional): 负面提示词
            model (str, optional): 模型名称
            width (int, optional): 图像宽度
            height (int, optional): 图像高度
            steps (int, optional): 生成步数
            seed (int, optional): 随机种子

        Returns:
            str: JSON 格式结果，包含 success, path, url, error
        """
        prompt = kwargs.get("prompt", "")
        if not prompt:
            return json.dumps({
                "success": False,
                "path": None,
                "url": None,
                "error": "Prompt is required",
            })

        try:
            result = await self.generator.generate(
                prompt=prompt,
                negative_prompt=kwargs.get("negative_prompt"),
                model=kwargs.get("model"),
                width=kwargs.get("width", 1024),
                height=kwargs.get("height", 1024),
                steps=kwargs.get("steps", 20),
                seed=kwargs.get("seed"),
            )

            return json.dumps({
                "success": result.get("success", False),
                "path": result.get("path"),
                "url": None,
                "error": None,
            })

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return json.dumps({
                "success": False,
                "path": None,
                "url": None,
                "error": str(e),
            })


class TextToSpeechTool(Tool):
    """文本转语音工具 - 将文本转换为语音"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "http://localhost:8080/v1",
        default_model: str = "tts-1",
        default_voice: str = "alloy",
    ):
        """
        初始化 TTS 工具

        Args:
            api_key: API 密钥（可选）
            api_base: API 基础 URL
            default_model: 默认模型
            default_voice: 默认声音
        """
        self.tts = TTSProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
            default_voice=default_voice,
        )
        logger.debug(f"TextToSpeechTool initialized with model={default_model}, voice={default_voice}")

    @property
    def name(self) -> str:
        return "text_to_speech"

    @property
    def description(self) -> str:
        return "Convert text to speech using AI TTS models"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech",
                },
                "model": {
                    "type": "string",
                    "description": "TTS model to use (e.g., tts-1, tts-1-hd, kokoro)",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice to use (e.g., alloy, echo, nova, af_bella)",
                },
                "speed": {
                    "type": "number",
                    "description": "Speech speed (0.25 - 4.0)",
                    "minimum": 0.25,
                    "maximum": 4.0,
                },
            },
            "required": ["text"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行文本转语音

        Args:
            text (str): 要转换的文本
            model (str, optional): 模型名称
            voice (str, optional): 声音名称
            speed (float, optional): 语速 (0.25 - 4.0)

        Returns:
            str: JSON 格式结果，包含 success, path, url, error
        """
        text = kwargs.get("text", "")
        if not text:
            return json.dumps({
                "success": False,
                "path": None,
                "url": None,
                "error": "Text is required",
            })

        try:
            result = await self.tts.speak(
                text=text,
                model=kwargs.get("model"),
                voice=kwargs.get("voice"),
                speed=kwargs.get("speed", 1.0),
            )

            return json.dumps({
                "success": result.get("success", False),
                "path": result.get("path"),
                "url": None,
                "error": None,
            })

        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return json.dumps({
                "success": False,
                "path": None,
                "url": None,
                "error": str(e),
            })


class UnderstandVideoTool(Tool):
    """视频理解工具 - 分析和理解视频内容"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        default_model: str = "gpt-4o",
    ):
        """
        初始化视频理解工具

        Args:
            api_key: API 密钥（可选）
            api_base: API 基础 URL（可选）
            default_model: 默认模型
        """
        self.video = VideoUnderstanding(
            api_key=api_key,
            api_base=api_base,
            default_model=default_model,
        )
        logger.debug(f"UnderstandVideoTool initialized with model={default_model}")

    @property
    def name(self) -> str:
        return "understand_video"

    @property
    def description(self) -> str:
        return "Analyze and understand video content by extracting and describing frames"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "video_path": {
                    "type": "string",
                    "description": "Path to the video file",
                },
                "prompt": {
                    "type": "string",
                    "description": "Prompt for video analysis (e.g., '描述这个视频的内容')",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for analysis",
                },
            },
            "required": ["video_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行视频理解

        Args:
            video_path (str): 视频文件路径
            prompt (str, optional): 分析提示词
            model (str, optional): 模型名称

        Returns:
            str: JSON 格式结果，包含 success, description, frames_analyzed, error
        """
        video_path = kwargs.get("video_path", "")
        if not video_path:
            return json.dumps({
                "success": False,
                "description": None,
                "frames_analyzed": 0,
                "error": "video_path is required",
            })

        try:
            result = await self.video.describe_video(
                video_path=video_path,
                prompt=kwargs.get("prompt", "描述这个视频的内容"),
                model=kwargs.get("model"),
            )

            return json.dumps({
                "success": result.get("success", False),
                "description": result.get("description"),
                "frames_analyzed": result.get("frames_analyzed", 0),
                "error": None,
            })

        except Exception as e:
            logger.error(f"Video understanding failed: {e}")
            return json.dumps({
                "success": False,
                "description": None,
                "frames_analyzed": 0,
                "error": str(e),
            })
