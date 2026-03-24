"""TTS 语音合成模块

支持通过 OpenAI TTS 兼容接口调用本地部署的 TTS 模型。
"""

import asyncio
import base64
from typing import Any, Optional

import httpx
from loguru import logger


class TTSProvider:
    """TTS 提供者 - 通过 OpenAI TTS 兼容接口调用本地 TTS 模型"""

    # 支持的模型列表
    SUPPORTED_MODELS = [
        "tts-1",          # OpenAI TTS-1
        "tts-1-hd",       # OpenAI TTS-1 HD
        "kokoro",         # Kokoro TTS
        " XTTS",          # Coqui XTTS
        "fish-speech",   # Fish Speech
    ]

    # 支持的声音
    VOICES = [
        "alloy",      # OpenAI
        "echo",
        "fable",
        "onyx",
        "nova",
        "shimmer",
        # Kokoro 风格
        "af_bella",
        "af_nicole",
        "af_sarah",
        "af_sky",
        "bf_emma",
        "bf_gwyn",
        "hm_aries",
        "hm_omega",
        "hm_ryan",
        "lm_tempest",
        "pm_jennifer",
        "pm_nicole",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "http://localhost:8080/v1",
        default_model: str = "tts-1",
        default_voice: str = "alloy",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """初始化 TTS 提供者

        Args:
            api_key: API 密钥（可选）
            api_base: API 基础 URL，默认指向本地 TTS 服务
            default_model: 默认模型
            default_voice: 默认声音
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.default_voice = default_voice
        self.timeout = timeout
        self.max_retries = max_retries

    async def speak(
        self,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        response_format: str = "mp3",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """将文本转换为语音

        Args:
            text: 要转换的文本
            model: 模型名称（可选）
            voice: 声音名称（可选）
            response_format: 输出格式 (mp3, opus, aac, flac)
            speed: 语速 (0.25 - 4.0)
            **kwargs: 其他参数

        Returns:
            dict: 包含音频路径和元数据
        """
        model = model or self.default_model
        voice = voice or self.default_voice
        request_id = f"tts_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(f"[{request_id}] TTS: {text[:50]}... (model={model}, voice={voice})")

        # 首先尝试 OpenAI 兼容格式
        try:
            result = await self._call_openai_tts(
                text, model, voice, response_format, speed, request_id
            )
            return result
        except Exception as e:
            logger.warning(f"[{request_id}] OpenAI TTS API failed: {e}")

        # 尝试 Kokoro / XTTS 等其他格式
        try:
            result = await self._call_extended_tts(
                text, model, voice, request_id
            )
            return result
        except Exception as e2:
            logger.error(f"[{request_id}] Extended TTS API also failed: {e2}")
            raise RuntimeError(f"TTS 语音合成失败: {str(e2)}")

    async def _call_openai_tts(
        self,
        text: str,
        model: str,
        voice: str,
        response_format: str,
        speed: float,
        request_id: str,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容 TTS API"""
        url = f"{self.api_base}/audio/speech"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
            "speed": speed,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            # 音频内容
            audio_content = response.content

            # 保存音频文件
            audio_path = await self._save_audio(audio_content, response_format, request_id)

            logger.info(f"[{request_id}] TTS completed: {audio_path}")

            return {
                "success": True,
                "path": str(audio_path),
                "model": model,
                "voice": voice,
                "text": text,
                "format": response_format,
            }

    async def _call_extended_tts(
        self,
        text: str,
        model: str,
        voice: str,
        request_id: str,
    ) -> dict[str, Any]:
        """调用扩展 TTS API（如 Kokoro 的完整格式）"""
        url = f"{self.api_base}/v1/audio/speech"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_data = {
            "model": model,
            "input": text,
            "voice": voice,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            audio_content = response.content
            audio_path = await self._save_audio(audio_content, "mp3", request_id)

            logger.info(f"[{request_id}] Extended TTS completed: {audio_path}")

            return {
                "success": True,
                "path": str(audio_path),
                "model": model,
                "voice": voice,
                "text": text,
            }

    async def _save_audio(
        self,
        audio_content: bytes,
        format: str,
        request_id: str,
    ) -> str:
        """保存音频数据到文件"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_audio"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 确定文件扩展名
        ext_map = {
            "mp3": "mp3",
            "opus": "opus",
            "aac": "aac",
            "flac": "flac",
            "wav": "wav",
        }
        ext = ext_map.get(format, "mp3")

        audio_path = output_dir / f"{request_id}.{ext}"

        with open(audio_path, "wb") as f:
            f.write(audio_content)

        return audio_path

    async def stream_speak(
        self,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        **kwargs: Any,
    ) -> bytes:
        """流式 TTS（返回音频字节）

        Args:
            text: 要转换的文本
            model: 模型名称
            voice: 声音名称
            **kwargs: 其他参数

        Returns:
            bytes: 音频内容
        """
        model = model or self.default_model
        voice = voice or self.default_voice

        url = f"{self.api_base}/audio/speech"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            return response.content

    def list_voices(self) -> list[str]:
        """列出可用的声音"""
        return self.VOICES.copy()

    def list_models(self) -> list[str]:
        """列出支持的模型"""
        return self.SUPPORTED_MODELS.copy()
