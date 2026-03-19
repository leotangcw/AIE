"""LLM加工处理器"""

import time
import json
from loguru import logger

from .base import BaseProcessor, KnowledgeResult


class LLMProcessor(BaseProcessor):
    """LLM加工模式 - 智能处理"""

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.client = None

    async def process(self, query: str, chunks: list = None, **kwargs) -> KnowledgeResult:
        """LLM加工处理"""
        start_time = time.time()

        # 1. 检索原始知识
        if chunks is None:
            chunks = await self._retrieve_chunks(query)

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
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # 降级到直接返回
            result = context

        processing_time = time.time() - start_time

        return KnowledgeResult(
            content=result,
            sources=[{"content": c.get("content", ""), "source": c.get("source", "")} for c in chunks],
            mode="llm",
            processing_time=processing_time,
            llm_used=True
        )

    async def _retrieve_chunks(self, query: str) -> list:
        """检索知识"""
        # TODO: 集成向量检索
        return []

    def _format_context(self, chunks: list) -> str:
        """格式化上下文"""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            formatted.append(f"【知识 {i}】\n{content}")
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

        try:
            from litellm import acompletion
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except ImportError:
            return "LLM未配置，请先安装 litellm 并配置API Key"
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
