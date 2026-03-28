"""MiniMax 音乐生成模块

通过 MiniMax music-2.5 API 生成音乐：
- 文生音乐（prompt 描述风格/情绪/乐器）
- 可选歌词输入
- 纯音乐模式（instrumental）
- 歌词生成（lyrics_generation）
"""

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger


class MinimaxMusicProvider:
    """MiniMax 音乐生成提供者"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "https://api.minimaxi.com/v1",
        default_model: str = "music-2.5",
        timeout: float = 180.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        lyrics: Optional[str] = None,
        instrumental: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成音乐

        Args:
            prompt: 音乐风格描述（如 "Mandopop, Festive, Upbeat"）
            model: 模型名称（如 music-2.5）
            lyrics: 歌词内容（可选，没有歌词可纯音乐）
            instrumental: 是否纯音乐（无演唱）

        Returns:
            dict: {"success": True, "path": str, "url": str, "model": str, "prompt": str}
        """
        model = model or self.default_model
        request_id = f"music_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(f"[{request_id}] MiniMax music generation: prompt={prompt[:80]}...")

        url = f"{self.api_base}/music_generation"

        request_data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
            },
            "output_format": "url",
        }

        if lyrics and not instrumental:
            request_data["lyrics"] = lyrics

        if instrumental:
            request_data["instrumental"] = True

        logger.debug(f"[{request_id}] POST {url}")
        logger.debug(f"[{request_id}] Request: model={model}, prompt={prompt[:100]}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()
            data = response.json()

        logger.debug(f"[{request_id}] Response keys: {list(data.keys())}")

        # 解析响应 - 获取音频 URL
        audio_url = self._parse_audio_url(data, request_id)

        if not audio_url:
            logger.error(f"[{request_id}] No audio URL in response: {str(data)[:500]}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": f"音乐生成失败：响应中无音频 URL。Response keys: {list(data.keys())}",
            }

        # 下载音频文件
        try:
            audio_path = await self._download_audio(audio_url, request_id)
        except Exception as e:
            logger.error(f"[{request_id}] Failed to download audio: {e}")
            return {
                "success": False,
                "path": None,
                "url": audio_url,
                "error": f"音频下载失败: {e}",
            }

        logger.info(f"[{request_id}] Music generated: {audio_path}")

        return {
            "success": True,
            "path": str(audio_path),
            "model": model,
            "prompt": prompt,
        }

    async def generate_lyrics(
        self,
        prompt: str,
        mode: str = "write_full_song",
    ) -> dict[str, Any]:
        """生成歌词

        Args:
            prompt: 歌曲主题描述
            mode: 生成模式（write_full_song, write_verse, write_chorus 等）

        Returns:
            dict: {"success": True, "lyrics": str}
        """
        request_id = f"lyrics_{int(asyncio.get_event_loop().time() * 1000)}"
        url = f"{self.api_base}/lyrics_generation"

        request_data = {
            "mode": mode,
            "prompt": prompt,
        }

        logger.info(f"[{request_id}] MiniMax lyrics generation: {prompt[:50]}...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()
            data = response.json()

        # 解析歌词
        lyrics = ""
        if isinstance(data, dict):
            # 可能直接返回歌词文本
            lyrics = data.get("lyrics", data.get("text", data.get("content", "")))
            if not lyrics and "data" in data:
                lyrics_data = data["data"]
                if isinstance(lyrics_data, dict):
                    lyrics = lyrics_data.get("lyrics", lyrics_data.get("text", ""))
                elif isinstance(lyrics_data, str):
                    lyrics = lyrics_data
            # 如果仍然没有，尝试取第一个值
            if not lyrics:
                for v in data.values():
                    if isinstance(v, str) and len(v) > 50:
                        lyrics = v
                        break

        return {
            "success": True,
            "lyrics": lyrics,
        }

    def _parse_audio_url(self, data: dict[str, Any], request_id: str) -> Optional[str]:
        """解析音频 URL"""
        # 格式 1: {"data": {"audio_url": "..."}}
        if "data" in data and isinstance(data["data"], dict):
            url = data["data"].get("audio_url")
            if url:
                logger.info(f"[{request_id}] Parsed audio_url from data dict")
                return url

        # 格式 2: {"audio_url": "..."} (顶层)
        if "audio_url" in data:
            logger.info(f"[{request_id}] Parsed audio_url from top level")
            return data["audio_url"]

        # 格式 3: {"data": {"audio": "...", "download_url": "..."}}
        if "data" in data and isinstance(data["data"], dict):
            url = data["data"].get("download_url") or data["data"].get("audio")
            if url:
                logger.info(f"[{request_id}] Parsed download_url from data dict")
                return url

        return None

    async def _download_audio(self, url: str, request_id: str) -> str:
        """下载音频文件到本地"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_audio"
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_path = output_dir / f"{request_id}.mp3"

        logger.info(f"[{request_id}] Downloading audio from {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

            with open(audio_path, "wb") as f:
                f.write(response.content)

        file_size = audio_path.stat().st_size
        logger.info(f"[{request_id}] Audio saved: {audio_path} ({file_size} bytes)")

        return str(audio_path)
