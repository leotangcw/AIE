"""文件上传 API"""

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from loguru import logger

from backend.utils.paths import WORKSPACE_DIR

router = APIRouter(prefix="/api/upload", tags=["upload"])

# 允许的文件类型
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/m4a",
    "audio/webm",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/avi",
    "video/mov",
    "video/mkv",
    "video/webm",
}

ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_AUDIO_TYPES | ALLOWED_VIDEO_TYPES

# 最大文件大小 (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# 上传目录
UPLOAD_DIR = WORKSPACE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...,
)) -> dict[str, Any]:
    """上传文件

    Args:
        file: 上传的文件

    Returns:
        文件路径信息
    """
    # 检查文件类型
    content_type = file.content_type
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {content_type}。支持的类型: {', '.join(ALLOWED_TYPES)}",
        )

    # 检查文件大小
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)",
        )

    # 读取文件内容并验证实际类型（magic bytes）
    content = await file.read()

    # 通过文件头 magic bytes 验证真实文件类型
    actual_type = _detect_mime_type(content)
    if actual_type and actual_type != content_type:
        logger.warning(f"File type mismatch: claimed={content_type}, detected={actual_type}, filename={file.filename}")
        raise HTTPException(
            status_code=400,
            detail=f"文件内容与声明类型不匹配: 声称 {content_type}，实际为 {actual_type}",
        )

    # 生成唯一文件名（使用实际检测到的类型决定扩展名，防止伪造扩展名）
    ext = _get_safe_extension(content_type)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / unique_name

    try:
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"文件上传成功: {file_path}")

        # 返回相对路径（相对于 uploads 目录）
        relative_path = f"uploads/{unique_name}"

        return {
            "success": True,
            "path": relative_path,
            "filename": file.filename,
            "size": size,
            "type": content_type,
        }

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 文件类型检测工具函数（基于 magic bytes，无外部依赖）
# ---------------------------------------------------------------------------

# 常见文件头签名 → MIME 类型
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    # 图片
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # RIFF....WEBP
    (b"BM", "image/bmp"),
    (b"II*\x00", "image/tiff"),  # little-endian TIFF
    (b"MM\x00*", "image/tiff"),  # big-endian TIFF
    # 音频
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
    (b"ID3", "audio/mpeg"),
    (b"fLaC", "audio/flac"),  # FLAC (不在白名单但检测到)
    (b"RIFF", "audio/wav"),  # RIFF....WAVE
    (b"\x4f\x67\x67\x53", "audio/ogg"),
    # 视频
    (b"\x00\x00\x00\x18ftypmp42", "video/mp4"),
    (b"\x00\x00\x00\x1cftypisom", "video/mp4"),
    (b"\x00\x00\x00\x20ftypisom", "video/mp4"),
    (b"\x00\x00\x00", "video/mp4"),  # 通用 MP4 ftyp box
    (b"RIFF", "video/avi"),  # RIFF....AVI
]


def _detect_mime_type(data: bytes) -> str | None:
    """通过文件头 magic bytes 检测真实 MIME 类型。"""
    if not data or len(data) < 4:
        return None

    # JPEG / PNG / GIF / BMP / TIFF 等图片
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:2] == b"BM":
        return "image/bmp"
    if data[:4] == b"II*\x00" or data[:4] == b"MM\x00*":
        return "image/tiff"

    # RIFF 容器: WebP / WAV / AVI
    if data[:4] == b"RIFF" and len(data) >= 12:
        riff_type = data[8:12]
        if riff_type == b"WEBP":
            return "image/webp"
        elif riff_type == b"WAVE":
            return "audio/wav"
        elif riff_type == b"AVI ":
            return "video/avi"

    # MP3 (ID3 tag or sync word)
    if data[:3] == b"ID3":
        return "audio/mpeg"
    if data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"

    # OGG
    if data[:4] == b"\x4f\x67\x67\x53":
        return "audio/ogg"

    # MP4 / MOV / M4A (ftyp box)
    if data[:4] == b"\x00\x00\x00" and len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"isom", b"mp42", b"mp41", b"M4V ", b"iso2", b"avc1"):
            return "video/mp4"
        if brand == b"M4A " or brand == b"isom":
            # M4A 和部分 isom 也可能是音频
            if data[:4] == b"\x00\x00\x00":
                return "audio/m4a"
        return "video/mp4"

    # WebM (Matroska / EBML)
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"

    return None


# MIME 类型 → 安全扩展名映射
_SAFE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/m4a": ".m4a",
    "audio/webm": ".weba",
    "video/mp4": ".mp4",
    "video/avi": ".avi",
    "video/mov": ".mov",
    "video/mkv": ".mkv",
    "video/webm": ".webm",
}


def _get_safe_extension(content_type: str) -> str:
    """根据声明类型返回安全扩展名，不信任用户上传的文件名扩展名。"""
    return _SAFE_EXTENSIONS.get(content_type, "")
