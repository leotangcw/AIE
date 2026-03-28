"""简单缓存 - 内存+本地文件"""

import json
import time
from typing import Optional
from pathlib import Path
from loguru import logger


class SimpleCache:
    """简单缓存实现"""

    def __init__(self, cache_dir: str = None, config=None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("memory/knowledge_hub/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.config = config
        # 支持字典或对象配置
        if config is None:
            self.ttl = 3600
            self.max_items = 100
        elif isinstance(config, dict):
            self.ttl = config.get('ttl', 3600)
            self.max_items = config.get('max_memory_items', 100)
        else:
            self.ttl = getattr(config, 'ttl', 3600)
            self.max_items = getattr(config, 'max_memory_items', 100)
        self.max_file_items = 1000  # 文件缓存最大条目数

        self._memory = {}
        self._access_time = {}
        self._cleanup_done = False

    def _cleanup_expired_files(self):
        """清理过期的缓存文件"""
        try:
            current_time = time.time()
            expired_files = []
            for f in self.cache_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if current_time - data.get("timestamp", 0) >= self.ttl:
                        expired_files.append(f)
                except Exception:
                    expired_files.append(f)

            # 如果过期文件过多，删除最旧的
            if len(expired_files) > self.max_file_items:
                expired_files.sort(key=lambda f: f.stat().st_mtime)
                expired_files = expired_files[:len(expired_files) - self.max_file_items]

            for f in expired_files:
                try:
                    f.unlink()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")

    def _ensure_cleanup(self):
        """延迟清理 - 仅在第一次访问时执行"""
        if not self._cleanup_done:
            self._cleanup_expired_files()
            self._cleanup_done = True

    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        self._ensure_cleanup()
        # 1. 先查内存
        if key in self._memory:
            if time.time() - self._access_time[key] < self.ttl:
                return self._memory[key]
            else:
                del self._memory[key]
                del self._access_time[key]

        # 2. 再查文件
        cache_file = self.cache_dir / f"{hash(key)}.json"
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) < self.ttl:
                self._memory[key] = data["content"]
                self._access_time[key] = data["timestamp"]
                return data["content"]
            else:
                # 已过期，删除文件
                try:
                    cache_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass

        return None

    def set(self, key: str, value: str, ttl: int = None):
        """设置缓存"""
        self._ensure_cleanup()
        self._memory[key] = value
        self._access_time[key] = time.time()

        # 简单内存淘汰 - 使用 list 而非 OrderedDict 以保持简单
        if len(self._memory) > self.max_items:
            oldest_key = min(self._access_time, key=self._access_time.get)
            del self._memory[oldest_key]
            del self._access_time[oldest_key]

    def clear(self, pattern: str = None):
        """清空缓存"""
        self._memory.clear()
        self._access_time.clear()
        if pattern:
            for f in self.cache_dir.glob(f"{pattern}*.json"):
                f.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()

    def invalidate(self, key: str):
        """失效指定缓存"""
        if key in self._memory:
            del self._memory[key]
            del self._access_time[key]
