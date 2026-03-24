"""音频 API 端点 - 语音转文字

支持多种转录方式（按优先级尝试）：
1. 本地 Whisper (base 模型) - 默认，离线可用
2. Groq Whisper API - 免费额度，离线时跳过
3. OpenAI Whisper API - 收费备选

首次使用本地模式时，会自动从 ModelScope 下载 Whisper base 模型（约 150MB）。
"""

from enum import Enum
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter(prefix="/api/audio", tags=["audio"])


class TranscriptionMode(str, Enum):
    """转录模式"""
    LOCAL = "local"           # 本地 Whisper
    GROQ = "groq"            # Groq 免费 API
    OPENAI = "openai"        # OpenAI API


# 转录服务状态
class TranscriptionService:
    """转录服务管理器"""

    def __init__(self):
        self.local_provider = None
        self.api_provider = None
        self.mode = TranscriptionMode.LOCAL
        self.local_available = False
        self.api_available = False
        self.groq_api_key: Optional[str] = None
        self.model_size = "base"

    def initialize(self, groq_api_key: Optional[str] = None, model_size: str = "base"):
        """初始化转录服务

        Args:
            groq_api_key: Groq API 密钥（可选，用于云端备用）
            model_size: 本地模型大小 (tiny/base/small)
        """
        self.groq_api_key = groq_api_key
        self.model_size = model_size

        # 尝试初始化本地模型
        self._init_local_provider()

        # 如果有 Groq API Key，也初始化云端备用
        if groq_api_key:
            self._init_api_provider()

        logger.info(
            f"Transcription service initialized: "
            f"local={'✓' if self.local_available else '✗'}, "
            f"groq={'✓' if self.api_available else '✗'}"
        )

    def _init_local_provider(self):
        """初始化本地 Whisper 模型"""
        try:
            from backend.modules.providers.local_transcription import LocalTranscriptionProvider

            self.local_provider = LocalTranscriptionProvider(
                model_size=self.model_size,
                device="cpu"
            )
            # 预热模型（首次加载）
            logger.info("正在加载本地 Whisper 模型（首次可能需要下载）...")
            self.local_provider._get_model()
            self.local_available = True
            self.mode = TranscriptionMode.LOCAL
            logger.info("本地 Whisper 模型加载成功")
        except Exception as e:
            logger.warning(f"本地 Whisper 初始化失败: {e}")
            self.local_available = False
            self.local_provider = None

    def _init_api_provider(self):
        """初始化云端 API 转录"""
        if not self.groq_api_key:
            self.api_available = False
            return

        try:
            from backend.modules.providers.transcription import TranscriptionProvider

            self.api_provider = TranscriptionProvider(
                api_key=self.groq_api_key,
                provider="groq"
            )
            self.api_available = True
        except Exception as e:
            logger.warning(f"Groq API 初始化失败: {e}")
            self.api_available = False
            self.api_provider = None

    async def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        """转录音频文件

        尝试顺序：
        1. 本地 Whisper（优先）
        2. Groq API（备用）
        3. 抛出错误
        """
        # 优先使用本地模型
        if self.local_available and self.local_provider:
            try:
                logger.info("使用本地 Whisper 转录...")
                return await self.local_provider.transcribe(audio_path, language)
            except Exception as e:
                logger.warning(f"本地转录失败: {e}，尝试云端...")

        # 回退到云端 API
        if self.api_available and self.api_provider:
            try:
                logger.info("使用 Groq Whisper API 转录...")
                return await self.api_provider.transcribe(audio_path, language)
            except Exception as e:
                logger.error(f"云端转录也失败: {e}")

        # 全部失败
        raise RuntimeError(
            "语音转文字服务不可用：\n"
            "1. 本地 Whisper 模型未安装或加载失败\n"
            "2. 云端 API (Groq) 也不可用\n"
            "请检查网络连接或设置 GROQ_API_KEY"
        )

    def get_status(self) -> dict:
        """获取服务状态"""
        return {
            "local_available": self.local_available,
            "api_available": self.api_available,
            "mode": self.mode.value if self.local_available else (
                TranscriptionMode.GROQ.value if self.api_available else None
            ),
            "model_size": self.model_size,
            "cache_dir": str(Path.home() / ".cache" / "whisper") if self.local_available else None,
        }


# 全局转录服务实例
transcription_service = TranscriptionService()


def init_transcription_service(groq_api_key: Optional[str] = None, model_size: str = "base"):
    """初始化转录服务（供外部调用）"""
    transcription_service.initialize(groq_api_key=groq_api_key, model_size=model_size)


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="音频文件（支持 mp3/mp4/wav/webm/m4a，最大 25MB）")
):
    """转录音频文件为文本

    使用本地 Whisper 模型或云端 API（自动选择可用方案）
    """
    # 验证文件类型
    allowed_extensions = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"]

    file_ext = os.path.splitext(file.filename or "audio.wav")[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}\n支持的格式: {', '.join(allowed_extensions)}"
        )

    # 验证文件大小（25MB）
    max_size = 25 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（最大 25MB）"
        )

    # 如果服务未初始化，尝试初始化
    if not transcription_service.local_available and not transcription_service.api_available:
        transcription_service.initialize(groq_api_key=os.environ.get("GROQ_API_KEY"))

    # 检查服务状态
    status = transcription_service.get_status()
    if not status["local_available"] and not status["api_available"]:
        raise HTTPException(
            status_code=503,
            detail=(
                "语音转文字服务不可用：\n"
                "1. 本地 Whisper 模型未安装\n"
                "2. 未设置 GROQ_API_KEY 环境变量\n\n"
                "请执行以下任一操作：\n"
                "1. 首次使用时会自动下载本地模型（约 150MB）\n"
                "2. 设置 GROQ_API_KEY 环境变量使用免费云端转录"
            )
        )

    temp_path = None
    try:
        # 保存到临时文件
        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext).name
        with open(temp_path, "wb") as f:
            f.write(content)

        logger.info(f"开始转录: {file.filename or 'audio'} ({len(content)} bytes)")

        # 执行转录
        text = await transcription_service.transcribe(temp_path)

        logger.info(f"转录成功: {len(text)} 字符")

        return JSONResponse(content={
            "text": text,
            "filename": file.filename or "audio",
            "size": len(content),
            "mode": status["mode"],
        })

    except RuntimeError as e:
        logger.error(f"转录失败: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        logger.error(f"转录异常: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

    finally:
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@router.get("/status")
async def get_transcription_status():
    """获取转录服务状态"""
    status = transcription_service.get_status()

    return JSONResponse(content={
        "available": status["local_available"] or status["api_available"],
        "local": {
            "available": status["local_available"],
            "model": status["model_size"],
            "cache_dir": status["cache_dir"],
        },
        "cloud": {
            "available": status["api_available"],
            "provider": "groq" if status["api_available"] else None,
        },
        "mode": status["mode"],
    })
