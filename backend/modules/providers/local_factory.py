"""本地模型 Provider 工厂"""

from typing import Optional, Any
from loguru import logger


def create_local_provider(
    provider_type: str = "ollama",
    api_base: str = "http://localhost:11434",
    default_model: str = "llama3",
    api_key: Optional[str] = None,
    timeout: float = 120.0,
    **kwargs: Any
):
    """
    创建本地模型 Provider

    Args:
        provider_type: 提供商类型 (ollama, vllm, llama_cpp, localai, chatglm, custom)
        api_base: API 基础地址
        default_model: 默认模型名称
        api_key: API 密钥（可选）
        timeout: 请求超时时间

    Returns:
        LocalLLMProvider 实例
    """
    from .local_provider import LocalLLMProvider

    provider_type = provider_type.lower()

    # 根据类型选择合适的 Provider
    if provider_type == "ollama":
        from .local_provider import OllamaProvider
        return OllamaProvider(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            timeout=timeout,
            **kwargs
        )
    elif provider_type == "vllm":
        from .local_provider import VLLMProvider
        return VLLMProvider(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            timeout=timeout,
            **kwargs
        )
    elif provider_type == "chatglm":
        from .local_provider import ChatGLMProvider
        return ChatGLMProvider(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            timeout=timeout,
            **kwargs
        )
    else:
        # 默认使用通用本地 Provider
        return LocalLLMProvider(
            api_base=api_base,
            default_model=default_model,
            api_key=api_key,
            timeout=timeout,
            provider_type=provider_type,
            **kwargs
        )


def is_local_provider(provider_type: str) -> bool:
    """判断是否为本地 Provider"""
    local_types = ["ollama", "vllm", "llama_cpp", "localai", "chatglm", "custom"]
    return provider_type.lower() in local_types


# 本地模型配置模板
LOCAL_PROVIDER_TEMPLATES = {
    "ollama": {
        "name": "Ollama",
        "api_base": "http://localhost:11434",
        "default_model": "llama3",
        "description": "Ollama 本地大模型服务",
    },
    "vllm": {
        "name": "vLLM",
        "api_base": "http://localhost:8000",
        "default_model": "llama3",
        "description": "vLLM 高性能推理服务",
    },
    "chatglm": {
        "name": "ChatGLM",
        "api_base": "http://localhost:8000",
        "default_model": "chatglm3",
        "description": "智谱 ChatGLM 本地服务",
    },
    "localai": {
        "name": "LocalAI",
        "api_base": "http://localhost:8080",
        "default_model": "llama2",
        "description": "LocalAI 统一本地模型服务",
    },
    "lmstudio": {
        "name": "LM Studio",
        "api_base": "http://localhost:1234",
        "default_model": "llama3",
        "description": "LM Studio 本地模型服务",
    },
}
