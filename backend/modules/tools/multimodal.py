"""Multimodal file handler - 支持 PDF/图片/视频读取"""

import base64
import io
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class MultimodalFileHandler:
    """多模态文件处理器"""

    # 支持的文件类型
    PDF_EXTENSIONS = {'.pdf'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}

    def __init__(self, workspace: Path):
        self.workspace = workspace

    async def read_file(self, path: str) -> dict[str, Any]:
        """
        读取文件，根据类型自动处理

        Returns:
            dict: {
                "type": "text|image|pdf|video",
                "content": "内容或 base64",
                "text": "可读的文本内容(如果适用)",
                "metadata": {...}
            }
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = file_path.suffix.lower()

        if ext in self.PDF_EXTENSIONS:
            return await self._read_pdf(file_path)
        elif ext in self.IMAGE_EXTENSIONS:
            return await self._read_image(file_path)
        elif ext in self.VIDEO_EXTENSIONS:
            return await self._read_video(file_path)
        else:
            # 默认作为文本读取
            return await self._read_text(file_path)

    def _resolve_path(self, path: str) -> Path:
        """解析文件路径"""
        if Path(path).is_absolute():
            return Path(path).resolve()
        return (self.workspace / path).resolve()

    async def _read_text(self, path: Path) -> dict[str, Any]:
        """读取文本文件"""
        try:
            content = path.read_text(encoding='utf-8')
            return {
                "type": "text",
                "content": content,
                "text": content,
                "metadata": {
                    "file_name": path.name,
                    "size": path.stat().st_size,
                    "extension": path.suffix,
                }
            }
        except UnicodeDecodeError:
            # 尝试其他编码
            content = path.read_text(encoding='latin-1')
            return {
                "type": "text",
                "content": content,
                "text": content,
                "metadata": {
                    "file_name": path.name,
                    "size": path.stat().st_size,
                    "encoding": "latin-1",
                }
            }

    async def _read_pdf(self, path: Path) -> dict[str, Any]:
        """读取 PDF 文件"""
        try:
            import pypdf

            text_content = []
            with open(path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    text_content.append(f"--- Page {page_num + 1} ---\n{page.extract_text()}")

            full_text = "\n\n".join(text_content)

            return {
                "type": "pdf",
                "content": full_text,
                "text": full_text,
                "metadata": {
                    "file_name": path.name,
                    "size": path.stat().st_size,
                    "pages": len(reader.pages),
                }
            }
        except ImportError:
            # 如果没有 pypdf，尝试返回 base64
            logger.warning("pypdf not installed, returning base64")
            return await self._read_file_base64(path, "pdf")
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            raise

    async def _read_image(self, path: Path) -> dict[str, Any]:
        """读取图片文件 - 支持 OCR"""
        # 读取为 base64
        base64_result = await self._read_file_base64(path, "image")

        # 尝试 OCR 提取文字
        ocr_text = await self._try_ocr(path)

        return {
            "type": "image",
            "content": base64_result["base64"],
            "text": ocr_text,  # OCR 提取的文字
            "metadata": {
                **base64_result["metadata"],
                "has_ocr": bool(ocr_text),
            }
        }

    async def _read_file_base64(self, path: Path, file_type: str) -> dict:
        """读取文件为 base64"""
        with open(path, 'rb') as f:
            data = f.read()
            base64_data = base64.b64encode(data).decode('utf-8')

        mime_types = {
            'image': f'image/{path.suffix[1:]}',
            'pdf': 'application/pdf',
            'video': f'video/{path.suffix[1:]}',
        }

        return {
            "base64": f"data:{mime_types.get(file_type, 'application/octet-stream')};base64,{base64_data}",
            "metadata": {
                "file_name": path.name,
                "size": path.stat().st_size,
                "mime_type": mime_types.get(file_type, 'application/octet-stream'),
            }
        }

    async def _try_ocr(self, path: Path) -> Optional[str]:
        """尝试 OCR 提取文字"""
        try:
            # 尝试使用 pytesseract
            import pytesseract
            from PIL import Image

            image = Image.open(path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')

            if text.strip():
                logger.info(f"OCR extracted {len(text)} characters from {path.name}")
                return text.strip()

        except ImportError:
            logger.debug("pytesseract or PIL not installed, skipping OCR")
        except Exception as e:
            logger.warning(f"OCR failed: {e}")

        # 尝试 rapidocr
        try:
            from rapidocr_onnxruntime import RapidOCR

            engine = RapidOCR()
            result, _ = engine(str(path))

            if result:
                text_lines = [line[1] for line in result]
                text = "\n".join(text_lines)
                if text.strip():
                    logger.info(f"RapidOCR extracted {len(text)} characters from {path.name}")
                    return text.strip()

        except ImportError:
            logger.debug("rapidocr_onnxruntime not installed, skipping OCR")
        except Exception as e:
            logger.warning(f"RapidOCR failed: {e}")

        return None

    async def _read_video(self, path: Path) -> dict[str, Any]:
        """读取视频文件"""
        # 视频不支持直接读取内容，返回 base64 和元信息
        base64_result = await self._read_file_base64(path, "video")

        # 尝试提取视频元信息
        metadata = {
            **base64_result["metadata"],
            "duration_seconds": await self._get_video_duration(path),
        }

        return {
            "type": "video",
            "content": base64_result["base64"],
            "text": None,  # 视频没有可提取的文本
            "metadata": metadata
        }

    async def _get_video_duration(self, path: Path) -> Optional[float]:
        """获取视频时长"""
        try:
            import cv2
            video = cv2.VideoCapture(str(path))
            fps = video.get(cv2.CAP_PROP_FPS)
            frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
            video.release()

            if fps and frame_count:
                return round(frame_count / fps, 2)
        except ImportError:
            logger.debug("OpenCV not installed, cannot get video duration")
        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}")

        return None

    def get_supported_types(self) -> dict[str, list[str]]:
        """获取支持的文件类型"""
        return {
            "pdf": list(self.PDF_EXTENSIONS),
            "image": list(self.IMAGE_EXTENSIONS),
            "video": list(self.VIDEO_EXTENSIONS),
            "text": ["*"],  # 所有其他文件作为文本
        }
