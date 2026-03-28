"""网络搜索接入器

支持多种搜索引擎：
- Brave Search API
- Google Custom Search
- Bing Search
- 自定义搜索接口
"""

import asyncio
from typing import Optional, Any
from loguru import logger
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from .base import BaseConnector
from ..config import WebSearchSourceConfig


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    content: str = ""
    source: str = ""
    score: float = 0.0
    timestamp: str = ""


class WebSearchConnector(BaseConnector):
    """网络搜索接入器"""

    def __init__(self, config: dict | WebSearchSourceConfig):
        super().__init__(config)
        if isinstance(config, WebSearchSourceConfig):
            self.provider = config.provider
            self.api_key = config.api_key
            self.base_url = config.base_url
            self.max_results = config.max_results
            self.timeout = config.timeout
            self.custom_headers = config.custom_headers
            self.custom_params = config.custom_params
        else:
            self.provider = config.get("provider", "brave")
            self.api_key = config.get("api_key", "")
            self.base_url = config.get("base_url", "")
            self.max_results = config.get("max_results", 5)
            self.timeout = config.get("timeout", 10)
            self.custom_headers = config.get("custom_headers", {})
            self.custom_params = config.get("custom_params", {})

        self._client = None
        self._cache: dict[str, list[SearchResult]] = {}

    async def connect(self) -> bool:
        """验证配置"""
        if not self.api_key:
            logger.warning(f"Web search ({self.provider}): API key not configured")
            return False
        return True

    async def fetch(self, query: str = None) -> list[dict]:
        """获取搜索结果"""
        if not query:
            return []

        results = await self.search(query)
        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "content": r.content,
                "source": r.source or self.provider,
                "score": r.score,
                "timestamp": r.timestamp,
            }
            for r in results
        ]

    async def search(self, query: str) -> list[SearchResult]:
        """执行搜索"""
        # 检查缓存
        cache_key = self._cache_key(query)
        if cache_key in self._cache:
            logger.debug(f"Using cached results for: {query}")
            return self._cache[cache_key]

        # 根据提供商选择搜索方法
        if self.provider == "brave":
            results = await self._search_brave(query)
        elif self.provider == "google":
            results = await self._search_google(query)
        elif self.provider == "bing":
            results = await self._search_bing(query)
        elif self.provider == "custom":
            results = await self._search_custom(query)
        else:
            logger.warning(f"Unknown search provider: {self.provider}")
            results = []

        # 缓存结果
        self._cache[cache_key] = results
        return results

    async def _search_brave(self, query: str) -> list[SearchResult]:
        """Brave Search API"""
        try:
            import httpx

            url = self.base_url or "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key,
                **self.custom_headers,
            }
            params = {
                "q": query,
                "count": self.max_results,
                "search_lang": "zh-hans",
                **self.custom_params,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    content="",
                    source="brave",
                    score=item.get("score", 0.5),
                    timestamp=datetime.now().isoformat(),
                ))

            logger.info(f"Brave search returned {len(results)} results for: {query}")
            return results[:self.max_results]

        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return []

    async def _search_google(self, query: str) -> list[SearchResult]:
        """Google Custom Search API"""
        try:
            import httpx

            # Google Custom Search 需要 CX (自定义搜索引擎 ID)
            cx = self.custom_params.get("cx", "")
            if not cx:
                logger.warning("Google search requires 'cx' parameter (Custom Search Engine ID)")
                return []

            url = self.base_url or "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": cx,
                "q": query,
                "num": self.max_results,
                **{k: v for k, v in self.custom_params.items() if k != "cx"},
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("items", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    content="",
                    source="google",
                    score=0.5,
                    timestamp=datetime.now().isoformat(),
                ))

            logger.info(f"Google search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"Google search failed: {e}")
            return []

    async def _search_bing(self, query: str) -> list[SearchResult]:
        """Bing Search API"""
        try:
            import httpx

            url = self.base_url or "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                **self.custom_headers,
            }
            params = {
                "q": query,
                "count": self.max_results,
                "mkt": "zh-CN",
                **self.custom_params,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append(SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    content="",
                    source="bing",
                    score=item.get("score", 0.5),
                    timestamp=datetime.now().isoformat(),
                ))

            logger.info(f"Bing search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"Bing search failed: {e}")
            return []

    async def _search_custom(self, query: str) -> list[SearchResult]:
        """自定义搜索接口"""
        if not self.base_url:
            logger.warning("Custom search requires 'base_url' configuration")
            return []

        try:
            import httpx

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                **self.custom_headers,
            }

            # 支持在 URL 中使用 {query} 占位符
            url = self.base_url.replace("{query}", query)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if self.custom_params.get("method", "GET").upper() == "POST":
                    response = await client.post(
                        url,
                        headers=headers,
                        json={"query": query, **self.custom_params}
                    )
                else:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={"q": query, **self.custom_params}
                    )

                response.raise_for_status()
                data = response.json()

            # 尝试解析结果
            results = self._parse_custom_results(data)
            logger.info(f"Custom search returned {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"Custom search failed: {e}")
            return []

    def _parse_custom_results(self, data: dict | list) -> list[SearchResult]:
        """解析自定义搜索结果"""
        results = []

        # 尝试常见的结果格式
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # 尝试常见的字段名
            for key in ["results", "items", "data", "hits", "documents"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue

            results.append(SearchResult(
                title=item.get("title", item.get("name", "")),
                url=item.get("url", item.get("link", item.get("uri", ""))),
                snippet=item.get("snippet", item.get("description", item.get("summary", ""))),
                content=item.get("content", item.get("body", "")),
                source=item.get("source", "custom"),
                score=item.get("score", 0.5),
                timestamp=item.get("timestamp", datetime.now().isoformat()),
            ))

        return results[:self.max_results]

    async def fetch_content(self, url: str) -> str:
        """获取网页内容"""
        try:
            import httpx
            from readability import Document

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # 使用 readability 提取正文
                doc = Document(response.text)
                return doc.summary()

        except ImportError:
            logger.warning("readability-lxml not installed, returning raw HTML")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                return response.text[:5000]  # 限制长度

        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return ""

    async def search_with_content(self, query: str, fetch_content: bool = True) -> list[SearchResult]:
        """搜索并获取内容"""
        results = await self.search(query)

        if fetch_content:
            tasks = [self.fetch_content(r.url) for r in results]
            contents = await asyncio.gather(*tasks, return_exceptions=True)

            for result, content in zip(results, contents):
                if isinstance(content, str):
                    result.content = content
                else:
                    result.content = ""

        return results

    async def sync(self) -> int:
        """同步（网络搜索不需要同步）"""
        return 0

    def _cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{self.provider}:{query}".encode()).hexdigest()

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
