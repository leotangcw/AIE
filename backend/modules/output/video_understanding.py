"""视频理解模块

支持视频帧采样和分析，通过多模态模型理解视频内容。
"""

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger


class VideoUnderstanding:
    """视频理解 - 采样视频帧并通过多模态模型分析"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        default_model: str = "gpt-4o",
        max_frames: int = 8,
        frame_interval: float = 1.0,
        timeout: float = 180.0,
        max_retries: int = 3,
    ):
        """初始化视频理解

        Args:
            api_key: API 密钥
            api_base: API 基础 URL（可选，用于多模态视频理解）
            default_model: 默认模型
            max_frames: 最大采样帧数
            frame_interval: 帧采样间隔（秒）
            timeout: 超时时间
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.api_base = api_base
        self.default_model = default_model
        self.max_frames = max_frames
        self.frame_interval = frame_interval
        self.timeout = timeout
        self.max_retries = max_retries

    async def describe_video(
        self,
        video_path: str,
        prompt: str = "描述这个视频的内容",
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """理解视频内容

        Args:
            video_path: 视频文件路径
            prompt: 分析提示词
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            dict: 包含分析结果和帧信息
        """
        model = model or self.default_model
        request_id = f"vid_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(f"[{request_id}] Understanding video: {video_path}")

        # 采样视频帧
        frames = await self._extract_frames(video_path, request_id)

        if not frames:
            raise RuntimeError("无法从视频中提取帧")

        logger.info(f"[{request_id}] Extracted {len(frames)} frames")

        # 如果有 OpenAI 兼容的视频理解 API
        if self.api_base:
            try:
                result = await self._call_multimodal_api(
                    video_path, frames, prompt, model, request_id
                )
                return result
            except Exception as e:
                logger.warning(f"[{request_id}] Multimodal API failed: {e}")

        # 使用图像序列分析
        result = await self._analyze_frames_as_images(
            frames, prompt, model, request_id
        )

        return result

    async def _extract_frames(
        self,
        video_path: str,
        request_id: str,
    ) -> list[dict[str, Any]]:
        """提取视频帧"""
        try:
            import cv2
            return await self._extract_frames_cv2(video_path, request_id)
        except ImportError:
            logger.warning("OpenCV not available, trying alternative method")
            return await self._extract_frames_basic(video_path, request_id)

    async def _extract_frames_cv2(
        self,
        video_path: str,
        request_id: str,
    ) -> list[dict[str, Any]]:
        """使用 OpenCV 提取视频帧"""
        import cv2

        frames = []
        video_path_obj = Path(video_path)

        if not video_path_obj.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        cap = cv2.VideoCapture(str(video_path_obj))

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            logger.info(
                f"[{request_id}] Video: {total_frames} frames, {fps:.1f} fps, {duration:.1f}s duration"
            )

            # 计算采样间隔
            if duration <= 0:
                return []

            interval_frames = max(1, int(self.frame_interval * fps))
            max_frames = min(self.max_frames, total_frames // interval_frames + 1)

            frame_times = []
            for i in range(max_frames):
                frame_idx = min(i * interval_frames, total_frames - 1)
                frame_times.append(frame_idx)

            # 提取指定帧
            for frame_idx in frame_times:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret:
                    # 编码为 JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                    _, buffer = cv2.imencode(".jpg", frame, encode_param)
                    b64_image = base64.b64encode(buffer).decode()

                    timestamp = frame_idx / fps if fps > 0 else 0

                    frames.append({
                        "frame_index": frame_idx,
                        "timestamp": timestamp,
                        "data": b64_image,
                        "mime_type": "image/jpeg",
                    })

            return frames

        finally:
            cap.release()

    async def _extract_frames_basic(
        self,
        video_path: str,
        request_id: str,
    ) -> list[dict[str, Any]]:
        """基础帧提取（不依赖 OpenCV）"""
        # 尝试使用 ffmpeg
        import subprocess

        frames = []
        video_path_obj = Path(video_path)

        if not video_path_obj.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 使用 ffmpeg 提取帧
        output_pattern = f"/tmp/{request_id}_frame_%03d.jpg"

        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path_obj),
                "-vf", f"fps=1/{self.frame_interval}",
                "-frames:v", str(self.max_frames),
                "-q:v", "3",
                output_pattern,
                "-y",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                # 读取生成的帧
                output_dir = Path("/tmp")
                for frame_file in sorted(output_dir.glob(f"{request_id}_frame_*.jpg")):
                    with open(frame_file, "rb") as f:
                        b64_image = base64.b64encode(f.read()).decode()

                    # 从文件名提取帧索引
                    frame_idx = int(frame_file.stem.split("_")[-1])

                    frames.append({
                        "frame_index": frame_idx,
                        "timestamp": frame_idx * self.frame_interval,
                        "data": b64_image,
                        "mime_type": "image/jpeg",
                    })

                    # 删除临时文件
                    frame_file.unlink()

        except Exception as e:
            logger.warning(f"[{request_id}] ffmpeg extraction failed: {e}")

        return frames

    async def _call_multimodal_api(
        self,
        video_path: str,
        frames: list[dict[str, Any]],
        prompt: str,
        model: str,
        request_id: str,
    ) -> dict[str, Any]:
        """调用多模态 API 进行视频理解"""
        url = f"{self.api_base}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 构建多模态消息
        content = []

        # 添加帧
        for frame in frames:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{frame['mime_type']};base64,{frame['data']}"
                }
            })

        # 添加提示
        content.append({
            "type": "text",
            "text": prompt
        })

        messages = [{
            "role": "user",
            "content": content
        }]

        request_data = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            data = response.json()

            if "choices" in data and data["choices"]:
                description = data["choices"][0]["message"]["content"]

                return {
                    "success": True,
                    "description": description,
                    "frames_analyzed": len(frames),
                    "model": model,
                    "prompt": prompt,
                }

        raise RuntimeError("多模态视频理解 API 返回格式未知")

    async def _analyze_frames_as_images(
        self,
        frames: list[dict[str, Any]],
        prompt: str,
        model: str,
        request_id: str,
    ) -> dict[str, Any]:
        """将帧作为图像序列分析（使用 OpenAI Vision API）"""
        from backend.modules.providers.factory import create_provider

        # 使用视觉模型分析
        provider = create_provider(
            provider_id="openai",
            api_key=self.api_key,
            default_model=model or "gpt-4o",
        )

        # 构建消息内容
        content = []

        # 添加帧
        for frame in frames[:4]:  # 限制分析帧数以节省 tokens
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{frame['mime_type']};base64,{frame['data']}"
                }
            })

        # 添加提示
        content.append({
            "type": "text",
            "text": f"这些是从视频中采样的关键帧。{prompt}\n\n请详细描述视频的内容、场景、动作和重要细节。"
        })

        messages = [{"role": "user", "content": content}]

        # 调用模型
        description = ""
        async for chunk in provider.chat_stream(messages=messages, model=model or "gpt-4o"):
            if chunk.is_content and chunk.content:
                description += chunk.content

        return {
            "success": True,
            "description": description,
            "frames_analyzed": len(frames),
            "model": model,
            "prompt": prompt,
        }

    async def get_video_info(self, video_path: str) -> dict[str, Any]:
        """获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            dict: 视频元数据
        """
        video_path_obj = Path(video_path)

        if not video_path_obj.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        mime_type, _ = mimetypes.guess_type(video_path)
        file_size = video_path_obj.stat().st_size

        info = {
            "path": str(video_path),
            "filename": video_path_obj.name,
            "mime_type": mime_type or "video/mp4",
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
        }

        # 尝试获取更多视频信息
        try:
            import cv2
            cap = cv2.VideoCapture(str(video_path_obj))
            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                info.update({
                    "fps": round(fps, 2) if fps > 0 else 0,
                    "total_frames": total_frames,
                    "duration_seconds": round(total_frames / fps, 2) if fps > 0 else 0,
                    "width": width,
                    "height": height,
                    "resolution": f"{width}x{height}",
                })
            finally:
                cap.release()
        except Exception as e:
            logger.warning(f"Could not extract video metadata: {e}")

        return info
