"""MiniMax 异步语音合成模块

通过 MiniMax speech-2.8 异步 API 进行文本转语音：
- 异步 3 步：提交任务 → 轮询状态 → 下载音频
- 支持 100+ 系统音色（中文、英文、日文、韩文等 40 种语言）
- 支持语速、音量、音调调节
- 支持最长 10 万字符文本
"""

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger


class MinimaxTTSProvider:
    """MiniMax 异步语音合成提供者"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "https://api.minimaxi.com/v1",
        default_model: str = "speech-2.8",
        default_voice: str = "male-qn-qingse",
        timeout: float = 120.0,
        poll_interval: float = 3.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.default_voice = default_voice
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def speak(
        self,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
        output_format: str = "mp3",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """文本转语音

        Args:
            text: 要转换的文本（最长 10 万字符）
            model: 模型名称（如 speech-2.8, speech-2.8-hd）
            voice: 音色 ID（如 male-qn-qingse, female-shaonv）
            speed: 语速（0.5 - 2.0，默认 1.0）
            vol: 音量（0.1 - 10，默认 1.0）
            pitch: 音调（-12 到 12，默认 0）
            output_format: 输出格式（mp3, wav, pcm）

        Returns:
            dict: {"success": True, "path": str, "model": str, "voice": str, "text": str}
        """
        model = model or self.default_model
        voice = voice or self.default_voice
        request_id = f"tts_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(
            f"[{request_id}] MiniMax TTS: text={text[:50]}..., "
            f"model={model}, voice={voice}"
        )

        try:
            # 步骤 1: 提交 TTS 任务
            task_id = await self._submit_tts_task(
                text, model, voice, speed, vol, pitch, output_format, request_id
            )
            logger.info(f"[{request_id}] TTS task submitted: task_id={task_id}")

            # 步骤 2: 轮询状态
            file_id = await self._poll_tts_status(task_id, request_id)
            logger.info(f"[{request_id}] TTS task completed: file_id={file_id}")

            # 步骤 3: 下载音频
            audio_path = await self._retrieve_audio(file_id, request_id, output_format)
            logger.info(f"[{request_id}] TTS audio saved: {audio_path}")

            return {
                "success": True,
                "path": str(audio_path),
                "model": model,
                "voice": voice,
                "text": text[:200],
                "format": output_format,
            }

        except TimeoutError as e:
            logger.error(f"[{request_id}] TTS timed out: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": f"语音合成超时（{self.timeout}秒）: {e}",
            }
        except RuntimeError as e:
            logger.error(f"[{request_id}] TTS failed: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"[{request_id}] TTS error: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": f"语音合成异常: {e}",
            }

    async def _submit_tts_task(
        self,
        text: str,
        model: str,
        voice: str,
        speed: float,
        vol: float,
        pitch: int,
        output_format: str,
        request_id: str,
    ) -> str:
        """提交 TTS 任务，返回 task_id"""
        url = f"{self.api_base}/t2a_async_v2"

        request_data: dict[str, Any] = {
            "model": model,
            "text": text,
            "language_boost": "auto",
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": vol,
                "pitch": pitch,
            },
            "audio_setting": {
                "audio_sample_rate": 32000,
                "bitrate": 128000,
                "format": output_format,
                "channel": 1,
            },
        }

        logger.debug(f"[{request_id}] POST {url}")
        logger.debug(f"[{request_id}] voice_id={voice}, text_length={len(text)}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()
            data = response.json()

        # 响应中可能有 task_id 或 data.task_id
        task_id = data.get("task_id") or data.get("data", {}).get("task_id")
        if not task_id:
            # 检查是否有错误
            if data.get("base_resp", {}).get("status_code") != 0:
                msg = data.get("base_resp", {}).get("status_msg", "未知错误")
                raise RuntimeError(f"MiniMax TTS API 错误: {msg}")
            raise RuntimeError(f"响应中无 task_id。Response: {str(data)[:300]}")

        return task_id

    async def _poll_tts_status(self, task_id: str, request_id: str) -> str:
        """轮询 TTS 任务状态，返回 file_id"""
        url = f"{self.api_base}/query/t2a_async_query_v2"
        params = {"task_id": task_id}

        elapsed = 0.0
        poll_count = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while elapsed < self.timeout:
                poll_count += 1
                logger.debug(
                    f"[{request_id}] TTS Poll #{poll_count}: "
                    f"task_id={task_id}, elapsed={elapsed:.0f}s"
                )

                try:
                    response = await client.get(
                        url, params=params, headers=self._build_headers()
                    )
                    response.raise_for_status()
                    data = response.json()

                    # 状态字段可能在顶层或 data 内
                    status_data = data.get("data", data)
                    status = status_data.get("status", "")

                    if status == "Success" or status == "completed":
                        file_id = status_data.get("file_id") or data.get("file_id")
                        if not file_id:
                            # 也检查 response_id
                            file_id = status_data.get("response_id") or data.get("response_id")
                        if not file_id:
                            raise RuntimeError(
                                f"任务成功但无 file_id。Response: {str(data)[:300]}"
                            )
                        return file_id

                    if status in ("Fail", "Failed", "fail"):
                        error_msg = (
                            status_data.get("error_message")
                            or data.get("base_resp", {}).get("status_msg", "未知错误")
                        )
                        raise RuntimeError(f"语音合成失败: {error_msg}")

                    logger.debug(f"[{request_id}] TTS Status: {status}, waiting...")
                except httpx.HTTPError as e:
                    logger.warning(f"[{request_id}] TTS Poll error: {e}")

                await asyncio.sleep(self.poll_interval)
                elapsed += self.poll_interval

        raise TimeoutError(f"语音合成超时（{self.timeout:.0f}秒）")

    async def _retrieve_audio(
        self, file_id: str, request_id: str, output_format: str
    ) -> str:
        """获取并保存音频文件"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_audio"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 扩展名映射
        ext_map = {"mp3": "mp3", "wav": "wav", "pcm": "pcm", "flac": "flac"}
        ext = ext_map.get(output_format, "mp3")
        audio_path = output_dir / f"{request_id}.{ext}"

        # 方法 1: 通过 retrieve_content 直接下载内容
        url = f"{self.api_base}/files/retrieve_content"
        params = {"file_id": file_id}

        logger.info(f"[{request_id}] Downloading audio: file_id={file_id}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params, headers=self._build_headers())
            response.raise_for_status()

            # 检查响应是否为 JSON（可能返回的是文件信息而非文件内容）
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data = response.json()
                # JSON 响应中可能有 download_url
                download_url = None
                if "file" in data:
                    download_url = data["file"].get("download_url")
                elif "download_url" in data:
                    download_url = data["download_url"]

                if download_url:
                    logger.info(f"[{request_id}] Got download URL, downloading...")
                    async with httpx.AsyncClient(timeout=60.0) as dl_client:
                        dl_response = await dl_client.get(download_url)
                        dl_response.raise_for_status()
                        with open(audio_path, "wb") as f:
                            f.write(dl_response.content)
                else:
                    raise RuntimeError(
                        f"无法获取音频内容。Response: {str(data)[:300]}"
                    )
            else:
                # 直接是音频内容
                with open(audio_path, "wb") as f:
                    f.write(response.content)

        file_size = audio_path.stat().st_size
        logger.info(f"[{request_id}] Audio saved: {audio_path} ({file_size} bytes)")

        return str(audio_path)
