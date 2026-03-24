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

    # 生成唯一文件名
    ext = Path(file.filename).suffix or ""
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / unique_name

    try:
        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"文件上传成功: {file_path}")

        return {
            "success": True,
            "path": str(file_path),
            "filename": file.filename,
            "size": size,
            "type": content_type,
        }

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
