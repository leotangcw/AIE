"""MiniMax 视频生成模块

通过 MiniMax Hailuo API 生成视频：
- 文生视频（text-to-video）
- 图生视频（image-to-video）
- 首尾帧生成视频
- 主体参考生成视频（subject reference，角色一致性）

视频生成为异步 API，内部自动轮询任务状态。
"""

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger


class MinimaxVideoProvider:
    """MiniMax 视频生成提供者"""

    MODEL_NAME_MAP = {
        "hailuo-2.3-fast-768p-6s": "MiniMax-Hailuo-2.3",
        "hailuo-2.3-768p-6s": "MiniMax-Hailuo-2.3",
        "hailuo-2.3": "MiniMax-Hailuo-2.3",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "https://api.minimaxi.com/v1",
        default_model: str = "MiniMax-Hailuo-2.3",
        timeout: float = 300.0,
        poll_interval: float = 10.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.poll_interval = poll_interval
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
        first_frame_image: Optional[str] = None,
        last_frame_image: Optional[str] = None,
        subject_reference: Optional[list[dict[str, Any]]] = None,
        duration: int = 6,
        resolution: str = "1080P",
        progress_callback: Optional[Any] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成视频

        Args:
            prompt: 视频内容描述
            model: 模型名称（如 MiniMax-Hailuo-2.3, S2V-01）
            first_frame_image: 首帧图像 URL（图生视频模式）
            last_frame_image: 尾帧图像 URL（首尾帧模式）
            subject_reference: 主体参考 [{"type": "character", "image": ["url"]}]
            duration: 视频时长（秒），默认 6
            resolution: 分辨率（360P, 540P, 720P, 1080P）
            progress_callback: 可选的进度回调 async def (progress: int, message: str)

        Returns:
            dict: {"success": True, "path": str, "model": str, "prompt": str, "duration": int}
        """
        model = model or self.default_model
        # 将常见别名映射为 API 接受的格式
        model = self.MODEL_NAME_MAP.get(model, model)
        request_id = f"vid_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(
            f"[{request_id}] MiniMax video generation: "
            f"prompt={prompt[:80]}..., model={model}, duration={duration}s"
        )

        try:
            # 步骤 1: 提交任务
            task_id = await self._submit_video_task(
                prompt, model, first_frame_image, last_frame_image,
                subject_reference, duration, resolution, request_id,
            )
            logger.info(f"[{request_id}] Task submitted: task_id={task_id}")

            # 步骤 2: 轮询状态
            file_id = await self._poll_video_status(task_id, request_id, progress_callback)
            logger.info(f"[{request_id}] Task completed: file_id={file_id}")

            # 步骤 3: 获取视频下载链接
            download_url = await self._retrieve_video(file_id, request_id)
            logger.info(f"[{request_id}] Got download URL: {download_url[:80]}...")

            # 步骤 4: 下载视频
            video_path = await self._download_video(download_url, request_id)
            logger.info(f"[{request_id}] Video saved: {video_path}")

            return {
                "success": True,
                "path": str(video_path),
                "model": model,
                "prompt": prompt,
                "duration": duration,
            }

        except TimeoutError as e:
            logger.error(f"[{request_id}] Video generation timed out: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": f"视频生成超时（{self.timeout}秒）: {e}",
            }
        except RuntimeError as e:
            logger.error(f"[{request_id}] Video generation failed: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"[{request_id}] Video generation error: {e}")
            return {
                "success": False,
                "path": None,
                "url": None,
                "error": f"视频生成异常: {e}",
            }

    async def _submit_video_task(
        self,
        prompt: str,
        model: str,
        first_frame_image: Optional[str],
        last_frame_image: Optional[str],
        subject_reference: Optional[list[dict[str, Any]]],
        duration: int,
        resolution: str,
        request_id: str,
    ) -> str:
        """提交视频生成任务，返回 task_id"""
        url = f"{self.api_base}/video_generation"

        request_data: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }

        if first_frame_image:
            request_data["first_frame_image"] = first_frame_image

        if last_frame_image:
            request_data["last_frame_image"] = last_frame_image

        if subject_reference:
            request_data["subject_reference"] = subject_reference

        logger.debug(f"[{request_id}] POST {url}")
        logger.debug(f"[{request_id}] Request data keys: {list(request_data.keys())}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()
            data = response.json()

        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError(f"响应中无 task_id。Response: {str(data)[:300]}")

        return task_id

    async def _poll_video_status(self, task_id: str, request_id: str, progress_callback=None) -> str:
        """轮询视频生成状态，返回 file_id"""
        url = f"{self.api_base}/query/video_generation"
        params = {"task_id": task_id}

        elapsed = 0.0
        poll_count = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            while elapsed < self.timeout:
                poll_count += 1
                logger.debug(
                    f"[{request_id}] Poll #{poll_count}: "
                    f"task_id={task_id}, elapsed={elapsed:.0f}s"
                )

                try:
                    response = await client.get(
                        url, params=params, headers=self._build_headers()
                    )
                    response.raise_for_status()
                    data = response.json()

                    status = data.get("status", "")

                    if status == "Success":
                        file_id = data.get("file_id")
                        if not file_id:
                            raise RuntimeError(f"任务成功但无 file_id。Response: {str(data)[:300]}")
                        return file_id

                    if status in ("Fail", "Failed"):
                        error_msg = data.get("error_message", data.get("base_resp", {}).get("status_msg", "未知错误"))
                        raise RuntimeError(f"视频生成失败: {error_msg}")

                    # 继续等待
                    logger.debug(f"[{request_id}] Status: {status}, waiting...")

                    # 上报进度
                    if progress_callback:
                        elapsed = poll_count * self.poll_interval
                        progress = min(90, int((elapsed / self.timeout) * 100))
                        try:
                            await progress_callback(progress, f"视频生成中... ({elapsed:.0f}s)")
                        except Exception:
                            pass
                except httpx.HTTPError as e:
                    logger.warning(f"[{request_id}] Poll request error: {e}")

                await asyncio.sleep(self.poll_interval)
                elapsed += self.poll_interval

        raise TimeoutError(f"视频生成超时（{self.timeout:.0f}秒），最后状态轮询 #{poll_count} 次")

    async def _retrieve_video(self, file_id: str, request_id: str) -> str:
        """获取视频下载 URL"""
        url = f"{self.api_base}/files/retrieve"
        params = {"file_id": file_id}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, params=params, headers=self._build_headers())
            response.raise_for_status()
            data = response.json()

        # 响应格式: {"file": {"download_url": "..."}}
        file_data = data.get("file", data)
        if isinstance(file_data, dict):
            download_url = file_data.get("download_url") or file_data.get("url")
        else:
            download_url = data.get("download_url") or data.get("url")

        if not download_url:
            raise RuntimeError(f"无法获取下载 URL。Response: {str(data)[:300]}")

        return download_url

    async def _download_video(self, url: str, request_id: str) -> str:
        """下载视频文件到本地"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_video"
        output_dir.mkdir(parents=True, exist_ok=True)

        video_path = output_dir / f"{request_id}.mp4"

        logger.info(f"[{request_id}] Downloading video from {url[:80]}...")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(video_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 64):
                        f.write(chunk)

        file_size = video_path.stat().st_size
        logger.info(f"[{request_id}] Video saved: {video_path} ({file_size / 1024 / 1024:.1f} MB)")

        return str(video_path)
