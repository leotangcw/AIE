"""文件访问 API - 提供上传文件的访问"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.utils.paths import WORKSPACE_DIR

router = APIRouter(prefix="/api/files", tags=["files"])

# 上传目录
UPLOAD_DIR = WORKSPACE_DIR / "uploads"


@router.get("/{path:path}")
async def get_file(path: str):
    """获取上传的文件

    Args:
        path: 文件路径（如 uploads/xxx.png 或 xxx.png）

    Returns:
        文件内容
    """
    # 安全检查：只允许访问 uploads 目录下的文件
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=403, detail="非法路径")

    # 如果路径包含 uploads/ 前缀，去掉它
    if path.startswith("uploads/"):
        path = path[len("uploads/"):]

    file_path = UPLOAD_DIR / path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    # 根据文件扩展名确定 content-type
    ext = file_path.suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
        ".mp4": "video/mp4",
        ".pdf": "application/pdf",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(file_path, media_type=content_type)
