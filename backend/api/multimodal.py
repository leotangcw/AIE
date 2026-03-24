"""多模态生成 API - 图像生成、TTS"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modules.output import ImageGenerator, TTSProvider, VideoUnderstanding

router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])

# 全局实例（延迟初始化）
_image_generator: Optional[ImageGenerator] = None
_tts_provider: Optional[TTSProvider] = None
_video_understanding: Optional[VideoUnderstanding] = None


def get_image_generator() -> ImageGenerator:
    """获取或创建 ImageGenerator 实例"""
    global _image_generator
    if _image_generator is None:
        _image_generator = ImageGenerator()
    return _image_generator


def get_tts_provider() -> TTSProvider:
    """获取或创建 TTSProvider 实例"""
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = TTSProvider()
    return _tts_provider


def get_video_understanding() -> VideoUnderstanding:
    """获取或创建 VideoUnderstanding 实例"""
    global _video_understanding
    if _video_understanding is None:
        _video_understanding = VideoUnderstanding()
    return _video_understanding


# ============================================================================
# Image Generation API
# ============================================================================


class ImageGenerateRequest(BaseModel):
    """图像生成请求"""
    prompt: str = Field(..., description="生成提示词")
    negative_prompt: Optional[str] = Field(None, description="负面提示词")
    model: Optional[str] = Field(None, description="模型名称")
    width: int = Field(1024, description="图像宽度")
    height: int = Field(1024, description="图像高度")
    steps: int = Field(20, description="生成步数")
    seed: Optional[int] = Field(None, description="随机种子")


class ImageGenerateResponse(BaseModel):
    """图像生成响应"""
    success: bool
    path: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


@router.post("/image/generate", response_model=ImageGenerateResponse)
async def generate_image(request: ImageGenerateRequest) -> ImageGenerateResponse:
    """生成图像

    Args:
        request: 图像生成请求

    Returns:
        ImageGenerateResponse: 生成结果
    """
    try:
        generator = get_image_generator()

        result = await generator.generate(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            model=request.model,
            width=request.width,
            height=request.height,
            steps=request.steps,
            seed=request.seed,
        )

        # 构建访问 URL
        if result.get("success") and result.get("path"):
            url = f"/api/files/{result['path']}"
            return ImageGenerateResponse(success=True, path=result["path"], url=url)

        return ImageGenerateResponse(success=False, error="生成失败")

    except Exception as e:
        return ImageGenerateResponse(success=False, error=str(e))


# ============================================================================
# TTS API
# ============================================================================


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str = Field(..., description="要转换的文本")
    model: Optional[str] = Field(None, description="模型名称")
    voice: Optional[str] = Field(None, description="声音")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="语速")


class TTSResponse(BaseModel):
    """TTS 响应"""
    success: bool
    path: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


@router.post("/tts/speak", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """将文本转换为语音

    Args:
        request: TTS 请求

    Returns:
        TTSResponse: 转换结果
    """
    try:
        tts = get_tts_provider()

        result = await tts.speak(
            text=request.text,
            model=request.model,
            voice=request.voice,
            speed=request.speed,
        )

        if result.get("success") and result.get("path"):
            url = f"/api/files/{result['path']}"
            return TTSResponse(success=True, path=result["path"], url=url)

        return TTSResponse(success=False, error="TTS 转换失败")

    except Exception as e:
        return TTSResponse(success=False, error=str(e))


@router.get("/tts/voices")
async def list_voices() -> dict[str, list[str]]:
    """获取可用的声音列表

    Returns:
        dict: 声音列表
    """
    tts = get_tts_provider()
    return {"voices": tts.list_voices()}


@router.get("/tts/models")
async def list_models() -> dict[str, list[str]]:
    """获取支持的模型列表

    Returns:
        dict: 模型列表
    """
    tts = get_tts_provider()
    return {"models": tts.list_models()}


# ============================================================================
# Video Understanding API
# ============================================================================


class VideoUnderstandRequest(BaseModel):
    """视频理解请求"""
    video_path: str = Field(..., description="视频文件路径")
    prompt: str = Field("描述这个视频的内容", description="分析提示词")
    model: Optional[str] = Field(None, description="模型名称")


class VideoUnderstandResponse(BaseModel):
    """视频理解响应"""
    success: bool
    description: Optional[str] = None
    frames_analyzed: int = 0
    error: Optional[str] = None


@router.post("/video/understand", response_model=VideoUnderstandResponse)
async def understand_video(request: VideoUnderstandRequest) -> VideoUnderstandResponse:
    """理解视频内容

    Args:
        request: 视频理解请求

    Returns:
        VideoUnderstandResponse: 分析结果
    """
    try:
        video = get_video_understanding()

        result = await video.describe_video(
            video_path=request.video_path,
            prompt=request.prompt,
            model=request.model,
        )

        if result.get("success"):
            return VideoUnderstandResponse(
                success=True,
                description=result.get("description"),
                frames_analyzed=result.get("frames_analyzed", 0),
            )

        return VideoUnderstandResponse(success=False, error="视频理解失败")

    except Exception as e:
        return VideoUnderstandResponse(success=False, error=str(e))


@router.get("/video/info")
async def get_video_info(video_path: str) -> dict[str, Any]:
    """获取视频信息

    Args:
        video_path: 视频文件路径

    Returns:
        dict: 视频元数据
    """
    try:
        video = get_video_understanding()
        info = await video.get_video_info(video_path)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
