"""本地 Whisper 语音转文字 - 基于 openai-whisper"""

import os
from pathlib import Path
from typing import Optional

import whisper

from loguru import logger


class LocalTranscriptionProvider:
    """本地 Whisper 转录服务

    模型下载（首次使用时自动）：
    - 从 ModelScope (modelscope.cn) 下载
    - 模型文件保存到 ~/.cache/whisper/

    支持的模型大小：
    - tiny (~39M params, ~75MB) - 最快，质量最低
    - base (~74M params, ~150MB) - 推荐，中等速度和质量
    - small (~244M params, ~500MB) - 较慢，质量较高
    - medium (~769M params, ~1.5GB) - 慢，质量高
    - large (~1550M params, ~3GB) - 最慢，最高音质
    """

    # 模型映射：名称 -> 模型大小标识
    MODELS = {
        "tiny": "tiny",
        "base": "base",
        "small": "small",
        "medium": "medium",
        "large": "large",
    }

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """初始化本地 Whisper 转录服务

        Args:
            model_size: 模型大小 (tiny/base/small/medium/large)
            device: 运行设备 (cpu/cuda)
        """
        self.model_size = model_size.lower()
        if self.model_size not in self.MODELS:
            raise ValueError(
                f"不支持的模型大小: {model_size}. "
                f"可选: {list(self.MODELS.keys())}"
            )
        self.device = device
        self._model = None

        # 模型缓存目录
        self.cache_dir = Path.home() / ".cache" / "whisper"
        logger.info(f"Local Whisper 初始化: model={model_size}, device={device}, cache={self.cache_dir}")

    def _get_model(self):
        """懒加载模型"""
        if self._model is None:
            logger.info(f"正在加载 Whisper {self.model_size} 模型（首次可能需要下载）...")
            try:
                # Whisper 会自动从 ModelScope 下载模型
                self._model = whisper.load_model(
                    self.model_size,
                    device=self.device,
                    download_root=str(self.cache_dir)
                )
                logger.info(f"Whisper {self.model_size} 模型加载成功")
            except Exception as e:
                logger.error(f"模型加载失败: {e}")
                raise RuntimeError(
                    f"Whisper 模型加载失败: {e}\n"
                    "可能原因：\n"
                    "1. 网络无法访问 ModelScope\n"
                    "2. 磁盘空间不足\n"
                    "请检查网络后重试，或设置 GROQ_API_KEY 使用云端转录"
                ) from e
        return self._model

    async def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> str:
        """转录音频文件为文本

        Args:
            audio_file_path: 音频文件路径
            language: 语言代码（如 "zh"、"en"），None 则自动检测

        Returns:
            转录文本
        """
        model = self._get_model()

        try:
            # 构建转录参数
            options = {
                "fp16": self.device == "cuda",  # GPU 时使用半精度
                "task": "transcribe",
            }
            if language:
                options["language"] = language

            logger.info(f"开始转录: {audio_file_path}")
            result = model.transcribe(audio_file_path, **options)
            text = result.get("text", "").strip()

            logger.info(f"转录完成: {len(text)} 字符")
            return text

        except Exception as e:
            logger.error(f"转录失败: {e}")
            raise RuntimeError(f"音频转录失败: {e}") from e

    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "cache_dir": str(self.cache_dir),
            "model_path": str(self.cache_dir / f"{self.MODELS[self.model_size]}.pt"),
        }
