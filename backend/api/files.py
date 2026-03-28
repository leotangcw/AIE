"""文件访问 API - 提供上传文件及生成文件的访问"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.utils.paths import WORKSPACE_DIR

router = APIRouter(prefix="/api/files", tags=["files"])

# 允许访问的目录（白名单）
ALLOWED_DIRS = {
    "uploads": WORKSPACE_DIR / "uploads",
    "generated_images": WORKSPACE_DIR / "generated_images",
    "generated_audio": WORKSPACE_DIR / "generated_audio",
    "generated_video": WORKSPACE_DIR / "generated_video",
    "generated_videos": WORKSPACE_DIR / "generated_videos",
    "screenshots": WORKSPACE_DIR / "screenshots",
}


@router.get("/{path:path}")
async def get_file(path: str):
    """获取文件（支持 uploads、generated_images、generated_audio、screenshots 目录）

    Args:
        path: 文件路径（如 generated_images/xxx.png）

    Returns:
        文件内容
    """
    # 安全检查：禁止路径遍历和绝对路径
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=403, detail="非法路径")

    # 根据 path 第一段路由到对应目录
    first_segment = path.split("/")[0]
    if first_segment in ALLOWED_DIRS:
        base_dir = ALLOWED_DIRS[first_segment]
        relative = path[len(first_segment) + 1:]  # 去掉 "segment/"
        file_path = (base_dir / relative).resolve()
        # 安全检查：确保解析后的路径仍在允许的目录内
        if not str(file_path).startswith(str(base_dir.resolve())):
            raise HTTPException(status_code=403, detail="非法路径")
    else:
        raise HTTPException(status_code=404, detail="目录不允许访问")

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
