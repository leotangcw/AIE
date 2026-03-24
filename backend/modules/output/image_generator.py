"""图像生成模块

支持通过 OpenAI 兼容接口调用本地部署的图像生成模型（如 Stable Diffusion API）。
"""

import asyncio
import base64
import json
from typing import Any, Optional
from pathlib import Path

import httpx
from loguru import logger


class ImageGenerator:
    """图像生成器 - 通过 OpenAI 兼容接口调用本地图像生成模型"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: str = "http://localhost:7860/v1",
        default_model: str = "stable-diffusion",
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        """初始化图像生成器

        Args:
            api_key: API 密钥（可选）
            api_base: API 基础 URL，默认指向本地 Stable Diffusion API
            default_model: 默认模型
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 7.5,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成图像

        Args:
            prompt: 生成提示词
            model: 模型名称（可选）
            negative_prompt: 负面提示词
            width: 图像宽度
            height: 图像高度
            steps: 生成步数
            cfg_scale: CFG 缩放因子
            seed: 随机种子（可选）
            **kwargs: 其他参数

        Returns:
            dict: 包含图像路径和元数据
        """
        model = model or self.default_model
        request_id = f"img_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(f"[{request_id}] Generating image: {prompt[:50]}...")

        # 构建请求参数（SD API 格式）
        request_params: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
        }

        if negative_prompt:
            request_params["negative_prompt"] = negative_prompt

        if seed is not None:
            request_params["seed"] = seed

        request_params.update(kwargs)

        # 尝试调用 Stable Diffusion API
        try:
            result = await self._call_sd_api(request_params, model, request_id)
            return result
        except Exception as e:
            logger.warning(f"[{request_id}] SD API failed: {e}")

        # 如果 SD API 失败，尝试 OpenAI 兼容格式（DALL-E 模拟）
        try:
            result = await self._call_openai_image_api(prompt, model, request_id)
            return result
        except Exception as e2:
            logger.error(f"[{request_id}] OpenAI image API also failed: {e2}")
            raise RuntimeError(f"图像生成失败: {str(e2)}")

    async def _call_sd_api(
        self,
        params: dict[str, Any],
        model: str,
        request_id: str,
    ) -> dict[str, Any]:
        """调用 Stable Diffusion API (AUTOMATIC1111 格式)"""
        url = f"{self.api_base}/sdapi/v1/txt2img"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # 提取图像
            if "images" in data and data["images"]:
                image_data = data["images"][0]
                seed = data.get("parameters", {}).get("seed", 0) or data.get("seed", 0)

                # 保存图像
                image_path = await self._save_image(image_data, request_id)

                logger.info(f"[{request_id}] Image generated: {image_path}")

                return {
                    "success": True,
                    "path": str(image_path),
                    "seed": seed,
                    "model": model,
                    "prompt": params.get("prompt"),
                }

            raise RuntimeError("SD API 返回格式未知")

    async def _call_openai_image_api(
        self,
        prompt: str,
        model: str,
        request_id: str,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容图像生成 API（如 DALL-E, Imagen）"""
        url = f"{self.api_base}/images/generations"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_data = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            data = response.json()

            if "data" in data and data["data"]:
                image_url = data["data"][0].get("url") or data["data"][0].get("b64_json")

                if image_url:
                    # 如果是 base64，保存为文件
                    if image_url.startswith("data:"):
                        # 提取 base64 数据
                        b64_data = image_url.split(",", 1)[1] if "," in image_url else image_url
                        image_path = await self._save_base64_image(b64_data, request_id)
                    else:
                        # 下载 URL
                        image_path = await self._download_image(image_url, request_id)

                    logger.info(f"[{request_id}] Image generated: {image_path}")

                    return {
                        "success": True,
                        "path": str(image_path),
                        "model": model,
                        "prompt": prompt,
                    }

            raise RuntimeError("OpenAI 图像 API 返回格式未知")

    async def _save_image(self, base64_data: str, request_id: str) -> Path:
        """保存 base64 图像数据到文件"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_path = output_dir / f"{request_id}.png"

        # 解码并保存
        image_bytes = base64.b64decode(base64_data)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        return image_path

    async def _save_base64_image(self, base64_data: str, request_id: str) -> Path:
        """保存纯 base64 图像数据到文件"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_path = output_dir / f"{request_id}.png"

        image_bytes = base64.b64decode(base64_data)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        return image_path

    async def _download_image(self, url: str, request_id: str) -> Path:
        """从 URL 下载图像"""
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_path = output_dir / f"{request_id}.png"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

            with open(image_path, "wb") as f:
                f.write(response.content)

        return image_path

    async def generate_variation(
        self,
        image_path: str,
        prompt: str,
        strength: float = 0.5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成图像变体（img2img）

        Args:
            image_path: 源图像路径
            prompt: 提示词
            strength: 变换强度 (0-1)
            **kwargs: 其他参数

        Returns:
            dict: 包含图像路径和元数据
        """
        request_id = f"img_var_{int(asyncio.get_event_loop().time() * 1000)}"

        logger.info(f"[{request_id}] Generating variation: {prompt[:50]}...")

        # 读取图像并转为 base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        # SD img2img API 格式
        url = f"{self.api_base}/sdapi/v1/img2img"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_data = {
            "init_images": [image_b64],
            "prompt": prompt,
            "denoising_strength": 1 - strength,  # SD 使用 denoising_strength
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()

            data = response.json()

            if "images" in data and data["images"]:
                image_data = data["images"][0]
                image_path = await self._save_image(image_data, request_id)

                logger.info(f"[{request_id}] Variation generated: {image_path}")

                return {
                    "success": True,
                    "path": str(image_path),
                    "prompt": prompt,
                }

        raise RuntimeError("图像变体生成失败")
