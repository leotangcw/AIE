"""LLM加工处理器

使用 LLM 对检索结果进行加工处理。
"""

import time
from loguru import logger
from typing import Optional

from .base import BaseProcessor, KnowledgeResult


class LLMProcessor(BaseProcessor):
    """LLM加工模式 - 智能处理"""

    def __init__(self, config: dict, hub=None):
        super().__init__(config)
        self.config = config
        self.hub = hub
        self._vector_store = None

    @property
    def vector_store(self):
        """延迟获取向量存储"""
        if self._vector_store is None and self.hub:
            self._vector_store = self.hub.vector_store
        return self._vector_store

    async def process(self, query: str, chunks: list = None, **kwargs) -> KnowledgeResult:
        """LLM加工处理"""
        start_time = time.time()

        # 1. 检索原始知识
        if chunks is None:
            chunks = await self._retrieve_chunks(query, **kwargs)

        if not chunks:
            return KnowledgeResult(
                content="未找到相关知识",
                sources=[],
                mode="llm",
                processing_time=time.time() - start_time,
                llm_used=False
            )

        # 2. 调用LLM处理
        context = self._format_context(chunks)
        prompt = self._build_prompt(query, context)

        try:
            result = await self._call_llm(prompt)
            llm_used = True
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # 降级到直接返回原始内容
            result = context
            llm_used = False

        processing_time = time.time() - start_time

        return KnowledgeResult(
            content=result,
            sources=[{"content": c.get("content", ""), "source": c.get("source", "")} for c in chunks],
            mode="llm",
            processing_time=processing_time,
            llm_used=llm_used
        )

    async def _retrieve_chunks(self, query: str, top_k: int = 10, **kwargs) -> list:
        """检索知识 - 集成向量检索"""
        results = []

        # 优先使用向量检索
        if self.vector_store:
            try:
                vector_results = await self._vector_search(query, top_k)
                results.extend(vector_results)
                logger.debug(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # 如果向量检索结果不足，使用关键词检索补充
        if len(results) < top_k // 2 and self.hub and self.hub.connectors:
            keyword_results = await self._keyword_search(query, top_k - len(results))
            results.extend(keyword_results)
            logger.debug(f"Keyword search returned {len(keyword_results)} results")

        # 去重
        seen = set()
        unique_results = []
        for r in results:
            key = r.get("content", "")[:100]  # 使用内容前100字符作为去重键
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return unique_results[:top_k]

    async def _vector_search(self, query: str, top_k: int) -> list[dict]:
        """向量检索"""
        if not self.vector_store:
            return []

        try:
            # 使用向量存储的 search 方法
            results = self.vector_store.search(query, top_k=top_k)

            formatted = []
            for r in results:
                formatted.append({
                    "content": r.get("content", ""),
                    "source": r.get("source", r.get("source_id", "vector")),
                    "score": r.get("score", 0.5),
                    "metadata": r.get("metadata", {}),
                })

            return formatted

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    async def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """关键词检索"""
        if not self.hub or not self.hub.connectors:
            return []

        results = []
        query_lower = query.lower()

        for source_id, connector in self.hub.connectors.items():
            try:
                if hasattr(connector, "fetch"):
                    docs = await connector.fetch(query)
                    for doc in docs:
                        chunks = doc.get("content", [])
                        if isinstance(chunks, str):
                            chunks = [chunks]

                        for chunk in chunks:
                            if query_lower in chunk.lower():
                                results.append({
                                    "content": chunk,
                                    "source": doc.get("source", source_id),
                                    "score": 0.5,  # 关键词匹配默认分数
                                })

                                if len(results) >= top_k:
                                    return results

            except Exception as e:
                logger.warning(f"Connector {source_id} search failed: {e}")

        return results

    def _format_context(self, chunks: list) -> str:
        """格式化上下文"""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            source = chunk.get("source", "unknown")
            formatted.append(f"【知识 {i} 来源: {source}】\n{content}")
        return "\n\n".join(formatted)

    def _build_prompt(self, query: str, context: str) -> str:
        """构建提示词"""
        prompt_style = self.config.get("prompt_style", "compress")

        # 获取提示词模板
        from ..config import PROMPT_STYLES
        templates = PROMPT_STYLES

        template = templates.get(prompt_style, templates["compress"])
        prompt = template["template"].format(query=query, context=context)
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        model = self.config.get("model", "gpt-3.5-turbo")
        temperature = self.config.get("temperature", 0.7)
        max_tokens = self.config.get("max_tokens", 2000)
        api_key = self.config.get("api_key", "")
        base_url = self.config.get("base_url", "")

        try:
            import os

            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["OPENAI_API_BASE"] = base_url

            from litellm import acompletion
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        except ImportError:
            # 尝试直接调用
            return await self._call_llm_direct(prompt, model, api_key, base_url, temperature, max_tokens)

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

    async def _call_llm_direct(
        self,
        prompt: str,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """直接调用 OpenAI API"""
        import httpx

        url = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
