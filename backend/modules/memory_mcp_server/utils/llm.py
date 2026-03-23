"""LLM utilities for intent analysis and L0/L1 generation.

Falls back to template-based generation when LLM is unavailable.
"""

import json
import os
import re
from typing import Literal

from loguru import logger


class LLMClient:
    """Lightweight LLM client for text generation with fallback."""

    def __init__(
        self,
        provider: Literal["openai", "volcengine", "litellm"] = "openai",
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        enabled: bool = True,
    ):
        self.provider = provider
        self.model = model
        self.api_key = os.environ.get(api_key_env)
        self.enabled = enabled and bool(self.api_key)

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text from prompt with fallback."""
        if not self.enabled:
            logger.debug("LLM disabled or no API key, using fallback generation")
            return self._fallback_generate(prompt, system_prompt)

        try:
            if self.provider == "openai":
                return self._generate_openai(prompt, system_prompt)
            elif self.provider == "volcengine":
                return self._generate_volcengine(prompt, system_prompt)
            elif self.provider == "litellm":
                return self._generate_litellm(prompt, system_prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except Exception as e:
            logger.warning(f"LLM call failed: {e}, using fallback")
            return self._fallback_generate(prompt, system_prompt)

    def _generate_openai(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate using OpenAI API."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        return response.choices[0].message.content or ""

    def _generate_volcengine(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate using Volcengine ARK API."""
        import httpx

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }

        response = httpx.post(
            "https://ark.cn-beijing.volces.com/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _generate_litellm(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate using LiteLLM (unified interface)."""
        import litellm

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = litellm.completion(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        return response.choices[0].message.content or ""

    def _fallback_generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Fallback generation using simple templates when LLM unavailable."""
        # Extract key sentences from content for abstract
        if "abstract" in prompt.lower() or "one sentence" in prompt.lower():
            # Try to extract first meaningful sentence
            content_match = re.search(r"Content:\s*\n*(.+?)(?:\n\n|$)", prompt, re.DOTALL)
            if content_match:
                content = content_match.group(1).strip()
                # Get first sentence
                sentences = re.split(r"[.。!?]+", content)
                if sentences:
                    return sentences[0].strip() + "."
            return "Summary generated when LLM unavailable."

        # For overview, return first paragraph
        content_match = re.search(r"Content:\s*\n*(.+?)(?:\n\n|$)", prompt, re.DOTALL)
        if content_match:
            content = content_match.group(1).strip()
            paragraphs = re.split(r"\n\n+", content)
            if paragraphs:
                return paragraphs[0].strip()
        return "Overview generated when LLM unavailable."


class IntentAnalyzerPrompt:
    """Prompts for intent analysis."""

    SYSTEM_PROMPT = """You are a memory query analyzer. Given a user's query, analyze their real intent to help retrieve relevant memories.

Your task is to:
1. Understand the true intent behind the query
2. Determine what type of memory/context is needed
3. Identify any entities mentioned
4. Suggest search scope

Output your analysis as JSON."""

    USER_PROMPT = """Given the user query:「{query}」
Context: {context}

Analyze:
1. What is the user's real intent?
2. What type of memory is needed? (memory=personal experiences, resource=knowledge, skill=capabilities)
3. Should search be limited to specific scope? (session=current conversation, user=user's memories, agent=agent's knowledge, global=all)
4. What entities are mentioned?

Output JSON format:
{{
    "intent": "description of intent",
    "optimized_query": "refined search query",
    "context_type": "memory|resource|skill|all",
    "scope": "session|user|agent|global",
    "entities": ["entity1", "entity2"],
    "confidence": 0.0-1.0
}}"""


class TierGenerationPrompt:
    """Prompts for L0/L1 tier content generation."""

    L0_SYSTEM_PROMPT = """You are a text summarizer. Generate concise summaries."""

    L0_USER_PROMPT = """Generate a one-sentence abstract for the following content.
The abstract should capture the core essence in one clear sentence.

Content:
{content}

Respond with only the abstract sentence, nothing else."""

    L1_SYSTEM_PROMPT = """You are a text summarizer. Generate informative overviews."""

    L1_USER_PROMPT = """Generate a paragraph overview for the following content.
The overview should describe the key points in 2-4 sentences.

Content:
{content}

Respond with only the overview paragraph, nothing else."""


def generate_l0(content: str, llm: LLMClient) -> str:
    """Generate L0 abstract (one sentence summary)."""
    if not content or len(content.strip()) < 10:
        return content

    try:
        return llm.generate(
            TierGenerationPrompt.L0_USER_PROMPT.format(content=content[:2000]),
            system_prompt=TierGenerationPrompt.L0_SYSTEM_PROMPT,
        ).strip()
    except Exception as e:
        logger.warning(f"Failed to generate L0: {e}")
        # Fallback: extract first sentence
        sentences = re.split(r"[.。!?]+", content)
        return sentences[0].strip() + "." if sentences else content[:100]


def generate_l1(content: str, llm: LLMClient) -> str:
    """Generate L1 overview (paragraph summary)."""
    if not content or len(content.strip()) < 20:
        return content

    try:
        return llm.generate(
            TierGenerationPrompt.L1_USER_PROMPT.format(content=content[:3000]),
            system_prompt=TierGenerationPrompt.L1_SYSTEM_PROMPT,
        ).strip()
    except Exception as e:
        logger.warning(f"Failed to generate L1: {e}")
        # Fallback: use first paragraph
        paragraphs = re.split(r"\n\n+", content)
        return paragraphs[0].strip() if paragraphs else content[:500]


def analyze_intent(query: str, context: str | None, llm: LLMClient) -> dict:
    """Analyze user query intent."""
    from ..models.query import IntentResult

    try:
        user_prompt = IntentAnalyzerPrompt.USER_PROMPT.format(
            query=query,
            context=context or "No additional context",
        )

        response = llm.generate(
            user_prompt,
            system_prompt=IntentAnalyzerPrompt.SYSTEM_PROMPT,
        )

        # Parse JSON response
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        elif "{" in response:
            start = response.index("{")
            end = response.rindex("}") + 1
            json_str = response[start:end]

        data = json.loads(json_str)

        return IntentResult(
            intent=data.get("intent", ""),
            optimized_query=data.get("optimized_query", query),
            context_type=data.get("context_type", "all"),
            scope=data.get("scope", "global"),
            entities=data.get("entities", []),
            confidence=data.get("confidence", 1.0),
        )
    except Exception as e:
        logger.warning(f"Failed to analyze intent: {e}")
        # Return default intent
        return IntentResult(
            intent="General query",
            optimized_query=query,
            context_type="all",
            scope="global",
            entities=[],
            confidence=0.0,
        )
