"""KnowledgeHub 配置模型"""

from typing import Optional, Literal
from pydantic import BaseModel
from pathlib import Path


class LLMConfig(BaseModel):
    """LLM处理配置"""
    enabled: bool = False
    model: str = "gpt-3.5-turbo"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    prompt_style: str = "compress"
    custom_prompts: dict = {}

    PROMPT_STYLES = {
        "compress": {
            "name": "信息压缩",
            "description": "极致压缩，只提取关键重点",
            "template": """请从以下知识中提取最核心的关键信息，以最简洁的方式呈现。

要求：
- 只保留核心要点
- 删除冗余描述
- 用最少的文字表达完整含义

知识内容：
{context}

用户问题：{query}

请输出压缩后的关键信息："""
        },
        "restate": {
            "name": "关键复述",
            "description": "关键语义原文复述",
            "template": """请根据以下知识回答用户问题，尽量保持原文语义，仅在必要时进行合理复述。

要求：
- 保持原文核心语义
- 可调整表达方式但不改原意
- 保留关键专业术语

知识内容：
{context}

用户问题：{query}

请输出回答："""
        },
        "rework": {
            "name": "加工改写",
            "description": "知识加工增加模型自我理解",
            "template": """请根据以下知识回答用户问题，在理解知识的基础上进行加工整合。

要求：
- 深入理解知识内涵
- 用自己的语言重新组织
- 可以补充相关背景说明
- 逻辑清晰便于理解

知识内容：
{context}

用户问题：{query}

请输出加工后的回答："""
        },
    }


class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool = True
    ttl: int = 3600
    max_memory_items: int = 100


class SourceConfig(BaseModel):
    """知识源配置"""
    id: str
    name: str
    source_type: Literal["local", "database", "web", "feishu", "wecom"]
    enabled: bool = True
    priority: int = 5
    config: dict = {}


class KnowledgeHubConfig(BaseModel):
    """模块配置"""
    enabled: bool = True
    default_mode: Literal["direct", "llm", "hybrid"] = "direct"
    llm: LLMConfig = LLMConfig()
    cache: CacheConfig = CacheConfig()
    sources: list[SourceConfig] = []

    storage_dir: str = "memory/knowledge_hub"

    @classmethod
    def load(cls, path: str) -> "KnowledgeHubConfig":
        """从文件加载配置"""
        p = Path(path)
        if p.exists():
            import json
            return cls(**json.loads(p.read_text()))
        return cls()

    def save(self, path: str):
        """保存配置到文件"""
        import json
        Path(path).write_text(json.dumps(self.model_dump(), ensure_ascii=False, indent=2))
