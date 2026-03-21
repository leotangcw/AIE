"""解析会话级运行时配置 - 支持每个会话独立的模型/人格配置"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger


@dataclass
class SessionRuntimeConfig:
    """单个会话的最终运行时配置"""

    use_custom_config: bool
    has_custom_model_config: bool
    has_custom_persona_config: bool
    provider_name: str
    model_name: str
    temperature: float
    max_tokens: int
    max_iterations: int
    api_key: str
    api_base: Optional[str]
    model_config: Any  # ModelConfig
    persona_config: Any  # PersonaConfig
    model_response: dict[str, Any]
    persona_response: dict[str, Any]


def build_session_model_override(
    runtime_config: "SessionRuntimeConfig",
    *,
    force: bool = False,
) -> Optional[dict[str, Any]]:
    """将会话运行时配置转换为执行器可消费的模型覆盖参数"""

    if not force and not runtime_config.has_custom_model_config:
        return None

    return {
        "provider": runtime_config.provider_name,
        "model": runtime_config.model_name,
        "temperature": runtime_config.temperature,
        "max_tokens": runtime_config.max_tokens,
        "max_iterations": runtime_config.max_iterations,
        "api_key": runtime_config.api_key,
        "api_base": runtime_config.api_base or "",
    }


def _parse_session_json(
    raw: Optional[str], *, session_id: Optional[str], field_name: str
) -> dict[str, Any]:
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"会话配置解析失败：{session_id or '<unknown>'} / {field_name}")
        return {}

    if isinstance(data, dict):
        return data

    logger.warning(f"会话配置格式无效：{session_id or '<unknown>'} / {field_name}")
    return {}


def _normalized_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def resolve_session_runtime_config(
    app_config: Any, session: Optional[Any]
) -> SessionRuntimeConfig:
    """解析会话最终配置。

    优先级：会话配置 > 全局 provider 配置 > provider 默认值（仅 api_base）。
    """

    from backend.modules.config.schema import ModelConfig, PersonaConfig

    session_id = getattr(session, "id", None)
    use_custom_config = bool(session and getattr(session, "use_custom_config", False))

    raw_model_overrides = (
        _parse_session_json(
            getattr(session, "session_model_config", None),
            session_id=session_id,
            field_name="session_model_config",
        )
        if use_custom_config
        else {}
    )
    raw_persona_overrides = (
        _parse_session_json(
            getattr(session, "session_persona_config", None),
            session_id=session_id,
            field_name="session_persona_config",
        )
        if use_custom_config
        else {}
    )

    effective_model_data = app_config.model.model_dump()
    for key in ("provider", "model"):
        normalized = _normalized_text(raw_model_overrides.get(key))
        if normalized is not None:
            effective_model_data[key] = normalized
    for key in ("temperature", "max_tokens", "max_iterations"):
        if raw_model_overrides.get(key) is not None:
            effective_model_data[key] = raw_model_overrides[key]

    effective_persona_data = app_config.persona.model_dump()
    for key, value in raw_persona_overrides.items():
        if value is not None:
            effective_persona_data[key] = value

    effective_model_config = ModelConfig(**effective_model_data)
    effective_persona_config = PersonaConfig(**effective_persona_data)

    provider_name = effective_model_config.provider
    provider_config = app_config.providers.get(provider_name)

    session_api_key = _normalized_text(raw_model_overrides.get("api_key"))
    session_api_base = _normalized_text(raw_model_overrides.get("api_base"))

    api_key = session_api_key
    if api_key is None:
        api_key = provider_config.api_key if provider_config else ""

    api_base = session_api_base
    if api_base is None:
        api_base = provider_config.api_base if provider_config else None

    model_response = app_config.model.model_dump()
    for key, value in raw_model_overrides.items():
        if key in {"api_key", "api_base"}:
            continue
        if isinstance(value, str):
            normalized = _normalized_text(value)
            if normalized is not None:
                model_response[key] = normalized
        elif value is not None:
            model_response[key] = value
    model_response["api_key"] = raw_model_overrides.get("api_key", "") or ""
    model_response["api_base"] = raw_model_overrides.get("api_base", "") or ""

    persona_response = app_config.persona.model_dump()
    persona_response.update(raw_persona_overrides)

    return SessionRuntimeConfig(
        use_custom_config=use_custom_config,
        has_custom_model_config=bool(raw_model_overrides),
        has_custom_persona_config=bool(raw_persona_overrides),
        provider_name=provider_name,
        model_name=effective_model_config.model,
        temperature=effective_model_config.temperature,
        max_tokens=effective_model_config.max_tokens,
        max_iterations=effective_model_config.max_iterations,
        api_key=api_key,
        api_base=api_base,
        model_config=effective_model_config,
        persona_config=effective_persona_config,
        model_response=model_response,
        persona_response=persona_response,
    )


def get_session_model_override(session, app_config) -> Optional[dict[str, Any]]:
    """获取会话级模型覆盖参数（用于传递给 AgentLoop.process_message）

    Args:
        session: Session 模型实例
        app_config: 应用配置对象

    Returns:
        模型覆盖参数字典，如果会话没有自定义配置则返回 None
    """
    if not session:
        return None

    runtime_config = resolve_session_runtime_config(app_config, session)
    return build_session_model_override(runtime_config)
