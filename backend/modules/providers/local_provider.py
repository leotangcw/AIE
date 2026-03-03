"""本地模型 Provider - 支持 Ollama, vLLM, LLaMA.cpp 等本地部署模型"""

import json
import os
from typing import AsyncIterator, Any, Optional
from loguru import logger
from .base import LLMProvider, StreamChunk, ToolCall


class LocalLLMProvider(LLMProvider):
    """本地 LLM Provider - 支持各种本地部署的模型服务"""

    def __init__(
        self,
        api_base: str = "http://localhost:11434",
        default_model: str = "llama3",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        provider_type: str = "ollama",  # ollama, vllm, llama_cpp, localai, chatglm
        **kwargs: Any
    ):
        """
        初始化本地 LLM Provider

        Args:
            api_base: API 基础地址
            default_model: 默认模型名称
            api_key: API 密钥（可选）
            timeout: 请求超时时间
            max_retries: 最大重试次数
            provider_type: 提供商类型 (ollama, vllm, llama_cpp, localai, chatglm)
        """
        super().__init__(api_key, api_base, default_model, timeout, max_retries)
        self.provider_type = provider_type
        self._validate_provider()

    def _validate_provider(self) -> None:
        """验证 provider 类型"""
        valid_providers = ["ollama", "vllm", "llama_cpp", "localai", "chatglm", "custom"]
        if self.provider_type not in valid_providers:
            logger.warning(f"Unknown provider type: {self.provider_type}, using 'custom'")
            self.provider_type = "custom"

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """流式聊天补全"""
        import aiohttp

        model = model or self.default_model
        url = f"{self.api_base}/v1/chat/completions"

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 构建消息格式
        formatted_messages = self._format_messages(messages)

        # 构建请求体
        request_body = {
            "model": model,
            "messages": formatted_messages,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # 添加 tools（如果支持）
        if tools:
            request_body["tools"] = tools

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Local LLM error: {response.status} - {error_text}")
                        yield StreamChunk(
                            type="error",
                            content=f"API Error: {response.status}",
                            tool_calls=[]
                        )
                        return

                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line or not line.startswith('data: '):
                            continue

                        data = line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            break

                        try:
                            chunk_data = json.loads(data)
                            delta = chunk_data.get("choices", [{}])[0].get("delta", {})

                            content = delta.get("content", "")
                            tool_calls = delta.get("tool_calls", [])

                            if content or tool_calls:
                                yield StreamChunk(
                                    type="content",
                                    content=content,
                                    tool_calls=tool_calls
                                )
                        except json.JSONDecodeError:
                            continue

        except aiohttp.ClientError as e:
            logger.error(f"Connection error: {e}")
            yield StreamChunk(
                type="error",
                content=f"Connection error: {str(e)}",
                tool_calls=[]
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            yield StreamChunk(
                type="error",
                content=f"Error: {str(e)}",
                tool_calls=[]
            )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> tuple[str, list[ToolCall]]:
        """非流式聊天补全"""
        import aiohttp

        model = model or self.default_model
        url = f"{self.api_base}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        formatted_messages = self._format_messages(messages)

        request_body = {
            "model": model,
            "messages": formatted_messages,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            request_body["tools"] = tools

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return f"API Error: {response.status} - {error_text}", []

                    result = await response.json()
                    message = result.get("choices", [{}])[0].get("message", {})

                    content = message.get("content", "")
                    tool_calls = message.get("tool_calls", [])

                    return content, tool_calls

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error: {str(e)}", []

    async def embeddings(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """获取文本嵌入"""
        import aiohttp

        # 尝试不同的嵌入端点
        model = model or self.default_model

        # Ollama 嵌入端点
        ollama_url = f"{self.api_base}/api/embeddings"
        # OpenAI 兼容端点
        openai_url = f"{self.api_base}/v1/embeddings"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 先尝试 OpenAI 兼容格式
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    openai_url,
                    json={"model": model, "input": texts},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return [item["embedding"] for item in result.get("data", [])]
        except Exception:
            pass

        # 回退到 Ollama 格式
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ollama_url,
                    json={"model": model, "prompt": texts[0] if texts else ""},
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return [result.get("embedding", [])]
        except Exception as e:
            logger.error(f"Embeddings error: {e}")

        return []

    def _format_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """格式化消息以适配不同 Provider"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 处理 Role 类型
            if role == "system":
                formatted.append({"role": "system", "content": content})
            elif role == "user":
                formatted.append({"role": "user", "content": content})
            elif role == "assistant":
                formatted.append({"role": "assistant", "content": content})
            else:
                formatted.append({"role": "user", "content": str(msg)})

        return formatted

    @staticmethod
    def get_default_config() -> dict:
        """获取默认配置"""
        return {
            "provider_type": "ollama",
            "api_base": "http://localhost:11434",
            "default_model": "llama3",
            "timeout": 120,
        }


class OllamaProvider(LocalLLMProvider):
    """Ollama 专用 Provider"""

    def __init__(
        self,
        api_base: str = "http://localhost:11434",
        default_model: str = "llama3",
        api_key: Optional[str] = None,
        **kwargs: Any
    ):
        super().__init__(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            provider_type="ollama",
            **kwargs
        )


class VLLMProvider(LocalLLMProvider):
    """vLLM 专用 Provider"""

    def __init__(
        self,
        api_base: str = "http://localhost:8000",
        default_model: str = "llama3",
        api_key: Optional[str] = None,
        **kwargs: Any
    ):
        super().__init__(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            provider_type="vllm",
            **kwargs
        )


class ChatGLMProvider(LocalLLMProvider):
    """ChatGLM 专用 Provider"""

    def __init__(
        self,
        api_base: str = "http://localhost:8000",
        default_model: str = "chatglm3",
        api_key: Optional[str] = None,
        **kwargs: Any
    ):
        super().__init__(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            provider_type="chatglm",
            **kwargs
        )
