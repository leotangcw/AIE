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
        self.ttl = config.ttl if config else 3600
        self.max_items = config.max_memory_items if config else 100

        self._memory = {}
        self._access_time = {}

    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        # 1. 先查内存
        if key in self._memory:
            if time.time() - self._access_time[key] < self.ttl:
                return self._memory[key]
            else:
                del self._memory[key]
                del self._access_time[key]

        # 2. 再查文件
        cache_file = self.cache_dir / f"{hash(key)}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if time.time() - data.get("timestamp", 0) < self.ttl:
                    self._memory[key] = data["content"]
                    self._access_time[key] = data["timestamp"]
                    return data["content"]
            except Exception:
                pass

        return None

    def set(self, key: str, value: str, ttl: int = None):
        """设置缓存"""
        self._memory[key] = value
        self._access_time[key] = time.time()

        # 简单内存淘汰
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
