"""图像生成模块

支持多种图像生成 API：
- Stable Diffusion WebUI API (AUTOMATIC1111 格式)
- OpenAI 兼容接口 (DALL-E, Imagen 等)
- MiniMax 文生图 API (text-01 模型)
- 通用 OpenAI 兼容接口
"""

import asyncio
import base64
import json
from enum import Enum
from typing import Any, Optional
from pathlib import Path

import httpx
from loguru import logger


class ImageApiType(str, Enum):
    """图像生成 API 类型"""
    STABLE_DIFFUSION = "stable_diffusion"   # AUTOMATIC1111 WebUI API
    OPENAI = "openai"                       # OpenAI 兼容格式 (DALL-E, Imagen 等)
    MINIMAX = "minimax"                     # MiniMax 文生图 API


def detect_api_type(api_base: str) -> ImageApiType:
    """根据 api_base 自动检测 API 类型

    Args:
        api_base: API 基础 URL

    Returns:
        ImageApiType: 检测到的 API 类型
    """
    api_base_lower = api_base.lower()

    # MiniMax API 域名检测
    if any(domain in api_base_lower for domain in ("minimaxi.com", "minimax.chat", "minimax.io")):
        return ImageApiType.MINIMAX

    # Stable Diffusion WebUI API 检测 (默认端口 7860)
    if any(marker in api_base_lower for marker in ("7860", "/sdapi/", "stable-diffusion")):
        return ImageApiType.STABLE_DIFFUSION

    # 默认使用 OpenAI 兼容格式
    return ImageApiType.OPENAI


class ImageGenerator:
    """图像生成器 - 支持多种图像生成 API"""

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
        self.api_type = detect_api_type(api_base)

        logger.info(
            f"ImageGenerator initialized: type={self.api_type.value}, "
            f"base={self.api_base}, model={self.default_model}"
        )

    def _build_headers(self) -> dict[str, str]:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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

        logger.info(
            f"[{request_id}] Generating image: prompt='{prompt[:50]}...', "
            f"model={model}, api_type={self.api_type.value}"
        )

        # 根据 API 类型选择调用方式
        if self.api_type == ImageApiType.MINIMAX:
            return await self._call_with_retry(
                self._call_minimax_api,
                prompt=prompt, model=model, request_id=request_id,
                negative_prompt=negative_prompt, seed=seed, **kwargs,
            )
        elif self.api_type == ImageApiType.STABLE_DIFFUSION:
            return await self._call_with_retry(
                self._call_sd_api,
                prompt=prompt, model=model, request_id=request_id,
                negative_prompt=negative_prompt, width=width, height=height,
                steps=steps, cfg_scale=cfg_scale, seed=seed, **kwargs,
            )
        else:
            # OpenAI 兼容格式 - 也尝试 SD 格式作为 fallback
            try:
                return await self._call_with_retry(
                    self._call_openai_image_api,
                    prompt=prompt, model=model, request_id=request_id,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(
                    f"[{request_id}] OpenAI format failed ({e}), "
                    f"trying SD format as fallback..."
                )
                return await self._call_with_retry(
                    self._call_sd_api,
                    prompt=prompt, model=model, request_id=request_id,
                    negative_prompt=negative_prompt, width=width, height=height,
                    steps=steps, cfg_scale=cfg_scale, seed=seed, **kwargs,
                )

    async def _call_with_retry(self, func, **kwargs) -> dict[str, Any]:
        """带重试的 API 调用

        Args:
            func: 异步调用函数
            **kwargs: 传递给函数的参数

        Returns:
            dict: API 返回结果
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(**kwargs)
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"HTTP {e.response.status_code} error (attempt {attempt}/{self.max_retries}): "
                    f"{e.response.text[:200]}"
                )
                if e.response.status_code < 500:
                    break  # 客户端错误不重试
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"Network error (attempt {attempt}/{self.max_retries}): {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"Error (attempt {attempt}/{self.max_retries}): {e}")
                break  # 非网络错误不重试

        raise RuntimeError(f"图像生成失败（已重试 {self.max_retries} 次）: {last_error}")

    # =========================================================================
    # Stable Diffusion WebUI API (AUTOMATIC1111 格式)
    # =========================================================================

    async def _call_sd_api(
        self,
        prompt: str,
        model: str,
        request_id: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 7.5,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """调用 Stable Diffusion API (AUTOMATIC1111 格式)"""
        url = f"{self.api_base}/sdapi/v1/txt2img"
        params: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
        }
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if seed is not None:
            params["seed"] = seed
        params.update(kwargs)

        logger.debug(f"[{request_id}] SD API request: url={url}, params_keys={list(params.keys())}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=params, headers=self._build_headers())
            response.raise_for_status()

            data = response.json()
            logger.debug(f"[{request_id}] SD API response keys: {list(data.keys())}")

            if "images" in data and data["images"]:
                image_data = data["images"][0]
                seed_val = data.get("parameters", {}).get("seed", 0) or data.get("seed", 0)
                image_path = await self._save_base64_image(image_data, request_id)

                logger.info(f"[{request_id}] SD image generated: {image_path}")
                return {
                    "success": True,
                    "path": str(image_path),
                    "seed": seed_val,
                    "model": model,
                    "prompt": prompt,
                }

            raise RuntimeError(f"SD API 返回格式未知: {json.dumps(data, ensure_ascii=False)[:300]}")

    # =========================================================================
    # MiniMax 文生图 API
    # =========================================================================

    async def _call_minimax_api(
        self,
        prompt: str,
        model: str,
        request_id: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """调用 MiniMax 文生图 API

        官方文档: https://platform.minimaxi.com/docs/guides/image-generation
        POST {api_base}/image_generation

        请求参数:
            model: 模型名称（如 image-01, text-01）
            prompt: 文本描述
            aspect_ratio: 宽高比（"1:1", "16:9", "9:16"）
            response_format: 返回格式（"base64"）
        """
        try:
            result = await self._call_minimax_openai_format(
                prompt, model, request_id, negative_prompt, seed, **kwargs
            )
            if result:
                return result
        except Exception as e:
            logger.debug(f"[{request_id}] MiniMax API failed: {e}")

        raise RuntimeError(
            f"MiniMax API 调用失败，"
            f"请检查 api_base={self.api_base} 和 model={model} 是否正确。"
            f"参考文档: https://platform.minimaxi.com/docs/guides/image-generation"
        )

    async def _call_minimax_openai_format(
        self,
        prompt: str,
        model: str,
        request_id: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        """调用 MiniMax 图像生成 API

        官方文档: https://platform.minimaxi.com/docs/guides/image-generation
        POST {api_base}/image_generation

        请求参数:
            model: 模型名称（如 image-01）
            prompt: 文本描述
            aspect_ratio: 宽高比（如 "1:1", "16:9", "9:16"）
            response_format: 返回格式（如 "base64"）
            subject_reference: 可选，角色参考图（图生图）
        """
        # 正确的 MiniMax 图像生成端点
        url = f"{self.api_base}/image_generation"

        # 根据 width/height 计算 aspect_ratio
        width = kwargs.get("width", 1024)
        height = kwargs.get("height", 1024)
        if width == height:
            aspect_ratio = "1:1"
        elif width > height:
            aspect_ratio = "16:9"
        else:
            aspect_ratio = "9:16"

        request_data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": "base64",
        }
        if seed is not None:
            request_data["seed"] = seed
        if negative_prompt:
            request_data["negative_prompt"] = negative_prompt
        # subject_reference 支持图生图（角色一致性）
        if "subject_reference" in kwargs:
            request_data["subject_reference"] = kwargs["subject_reference"]

        logger.info(f"[{request_id}] MiniMax image_generation: POST {url}")
        logger.debug(f"[{request_id}] Request data: {json.dumps(request_data, ensure_ascii=False)[:300]}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())

            response.raise_for_status()
            data = response.json()

        logger.debug(f"[{request_id}] MiniMax response keys: {list(data.keys())}")
        logger.debug(f"[{request_id}] MiniMax response (truncated): {json.dumps(data, ensure_ascii=False)[:500]}")

        return await self._parse_minimax_response(data, model, prompt, request_id)

    async def _parse_minimax_response(
        self,
        data: dict[str, Any],
        model: str,
        prompt: str,
        request_id: str,
    ) -> dict[str, Any]:
        """解析 MiniMax API 响应

        官方文档格式:
        {"data": {"image_base64": ["base64_data", ...]}}

        备用格式（兼容性）:
        {"data": [{"url": "...", "b64_json": "..."}]}
        {"images": ["base64_data", ...]}
        """
        image_content = None

        # 官方文档格式：{"data": {"image_base64": [...]}}
        if "data" in data and isinstance(data["data"], dict):
            image_base64_list = data["data"].get("image_base64", [])
            if image_base64_list and len(image_base64_list) > 0:
                image_content = image_base64_list[0]
                logger.info(f"[{request_id}] Parsed MiniMax official format: image_base64[{len(image_base64_list)}]")

        # 格式 A/B: {"data": [...]}
        if not image_content and "data" in data and data["data"]:
            image_item = data["data"][0]
            # 按优先级查找图像数据
            image_content = (
                image_item.get("url")
                or image_item.get("b64_json")
                or image_item.get("image")
                or image_item.get("base64_image")
            )

        # 格式 C: 顶层字段
        if not image_content:
            image_content = data.get("image_url") or data.get("base64_image")

        # 格式 D: {"images": [...]}
        if not image_content and "images" in data and data["images"]:
            image_content = data["images"][0]

        if not image_content:
            logger.error(
                f"[{request_id}] Cannot parse MiniMax response. "
                f"Response keys: {list(data.keys())}. "
                f"Full response: {json.dumps(data, ensure_ascii=False)[:500]}"
            )
            raise RuntimeError(
                f"MiniMax API 返回格式无法解析。"
                f"Response keys: {list(data.keys())}。"
                f"请检查 model={model} 是否为有效的图像生成模型。"
            )

        # 保存图像
        if isinstance(image_content, str) and image_content.startswith("http"):
            # URL
            image_path = await self._download_image(image_content, request_id)
        else:
            # Base64 数据（可能带 data: 前缀）
            if isinstance(image_content, str) and "," in image_content and image_content.startswith("data:"):
                image_content = image_content.split(",", 1)[1]
            image_path = await self._save_base64_image(str(image_content), request_id, ext="jpg")

        logger.info(f"[{request_id}] MiniMax image generated: {image_path}")

        return {
            "success": True,
            "path": str(image_path),
            "model": model,
            "prompt": prompt,
        }

    # =========================================================================
    # OpenAI 兼容图像生成 API (DALL-E, Imagen 等)
    # =========================================================================

    async def _call_openai_image_api(
        self,
        prompt: str,
        model: str,
        request_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """调用 OpenAI 兼容图像生成 API（如 DALL-E, Imagen）"""
        url = f"{self.api_base}/images/generations"

        request_data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }
        request_data.update(kwargs)

        logger.info(f"[{request_id}] OpenAI image API: POST {url}")
        logger.debug(f"[{request_id}] Request data: {json.dumps(request_data, ensure_ascii=False)[:300]}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()

            data = response.json()
            logger.debug(f"[{request_id}] Response keys: {list(data.keys())}")

            if "data" in data and data["data"]:
                image_data = data["data"][0]
                image_url = (
                    image_data.get("url")
                    or image_data.get("b64_json")
                    or image_data.get("image")
                )

                if image_url:
                    # 如果是 base64，保存为文件
                    if image_url.startswith("data:") or len(image_url) > 200:
                        b64_data = image_url.split(",", 1)[1] if "," in image_url else image_url
                        image_path = await self._save_base64_image(b64_data, request_id)
                    else:
                        # 下载 URL
                        image_path = await self._download_image(image_url, request_id)

                    logger.info(f"[{request_id}] OpenAI image generated: {image_path}")

                    return {
                        "success": True,
                        "path": str(image_path),
                        "model": model,
                        "prompt": prompt,
                    }

            raise RuntimeError(
                f"OpenAI 图像 API 返回格式未知: {json.dumps(data, ensure_ascii=False)[:300]}"
            )

    # =========================================================================
    # 图像保存工具方法
    # =========================================================================

    async def _save_base64_image(self, base64_data: str, request_id: str, ext: str = "png") -> Path:
        """保存 base64 图像数据到文件

        Args:
            base64_data: base64 编码的图像数据（可能包含 data:image/xxx;base64, 前缀）
            request_id: 请求 ID

        Returns:
            Path: 保存的图像路径
        """
        from backend.utils.paths import WORKSPACE_DIR

        output_dir = WORKSPACE_DIR / "generated_images"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 去除 data URI 前缀（如果有），同时检测实际格式
        if "," in base64_data and base64_data.startswith("data:"):
            prefix, base64_data = base64_data.split(",", 1)
            if "jpeg" in prefix or "jpg" in prefix:
                ext = "jpg"

        image_path = output_dir / f"{request_id}.{ext}"

        image_bytes = base64.b64decode(base64_data)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        return image_path

    async def _download_image(self, url: str, request_id: str) -> Path:
        """从 URL 下载图像

        Args:
            url: 图像 URL
            request_id: 请求 ID

        Returns:
            Path: 保存的图像路径
        """
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

    # =========================================================================
    # 图像变体生成 (img2img)
    # =========================================================================

    async def generate_variation(
        self,
        image_path: str,
        prompt: str,
        strength: float = 0.5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成图像变体（img2img）

        目前仅支持 Stable Diffusion API 的 img2img 模式。

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

        request_data = {
            "init_images": [image_b64],
            "prompt": prompt,
            "denoising_strength": 1 - strength,  # SD 使用 denoising_strength
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=request_data, headers=self._build_headers())
            response.raise_for_status()

            data = response.json()

            if "images" in data and data["images"]:
                image_data = data["images"][0]
                new_path = await self._save_base64_image(image_data, request_id)

                logger.info(f"[{request_id}] Variation generated: {new_path}")

                return {
                    "success": True,
                    "path": str(new_path),
                    "prompt": prompt,
                }

        raise RuntimeError("图像变体生成失败")
