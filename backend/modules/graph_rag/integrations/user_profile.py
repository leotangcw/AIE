"""用户画像管理器

基于 GraphRAG 构建用户长期记忆和画像。
从用户对话中自动抽取关键信息，构建用户偏好、习惯、兴趣等知识图谱。
"""

import json
from datetime import datetime
from typing import Any, Optional
from loguru import logger

from ..core import GraphRAGClient, get_graph_rag
from ..config import QueryResult


# 默认用户画像实体类型
DEFAULT_PROFILE_ENTITY_TYPES = [
    "偏好",       # 用户偏好设置
    "习惯",       # 用户日常习惯
    "兴趣",       # 用户兴趣爱好
    "职业",       # 职业相关信息
    "技能",       # 用户技能
    "目标",       # 用户目标
    "家庭成员",   # 家庭成员信息
    "常用工具",   # 常用工具和软件
    "工作项目",   # 工作项目信息
    "重要日期",   # 重要日期和事件
]


class UserProfileManager:
    """用户画像管理器

    从用户对话中抽取关键信息，构建和维护用户画像知识图谱。

    Features:
    - 自动从对话中抽取实体和关系
    - 构建用户偏好、习惯、兴趣图谱
    - 支持用户画像查询
    - 支持画像更新和合并

    Example:
        ```python
        profile = UserProfileManager(user_id="user_123")

        # 从对话中抽取信息
        await profile.extract_from_conversation(
            "我喜欢用 Python 写代码，偏好简洁的代码风格。"
        )

        # 查询用户兴趣
        interests = await profile.get_interests()

        # 查询用户偏好
        prefs = await profile.get_preferences("编程")
        ```
    """

    def __init__(
        self,
        user_id: str,
        entity_types: list[str] | None = None,
    ):
        """初始化用户画像管理器

        Args:
            user_id: 用户 ID
            entity_types: 自定义实体类型列表
        """
        self.user_id = user_id
        self.entity_types = entity_types or DEFAULT_PROFILE_ENTITY_TYPES

        # 每个用户独立的命名空间
        self._client: GraphRAGClient | None = None

    async def _get_client(self) -> GraphRAGClient:
        """获取 GraphRAG 客户端"""
        if self._client is None:
            self._client = await get_graph_rag(
                namespace=f"user_{self.user_id}",
                workspace="user_profiles"
            )
        return self._client

    async def extract_from_conversation(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """从对话内容中抽取用户画像信息

        Args:
            content: 对话内容
            metadata: 元数据（如时间戳、会话 ID 等）

        Returns:
            是否成功
        """
        try:
            client = await self._get_client()

            # 添加元数据标记
            if metadata:
                content = f"[元数据: {json.dumps(metadata)}]\n{content}"

            result = await client.insert(
                content,
                file_paths=[f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"]
            )

            return result.success

        except Exception as e:
            logger.error(f"Failed to extract user profile: {e}")
            return False

    async def extract_from_conversations(
        self,
        conversations: list[dict],
    ) -> int:
        """批量从对话中抽取信息

        Args:
            conversations: 对话列表，每项包含 'content' 和可选的 'metadata'

        Returns:
            成功处理的对话数量
        """
        success_count = 0

        for conv in conversations:
            content = conv.get("content", "")
            metadata = conv.get("metadata")

            if content:
                if await self.extract_from_conversation(content, metadata):
                    success_count += 1

        logger.info(
            f"Extracted profile from {success_count}/{len(conversations)} "
            f"conversations for user {self.user_id}"
        )
        return success_count

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
    ) -> QueryResult:
        """查询用户画像

        Args:
            query: 查询问题
            mode: 查询模式

        Returns:
            QueryResult
        """
        client = await self._get_client()
        return await client.query(query, mode=mode)

    async def get_interests(self) -> list[str]:
        """获取用户兴趣列表

        Returns:
            兴趣列表
        """
        result = await self.query(
            "用户的兴趣爱好有哪些？请列举出来。",
            mode="local"
        )

        return self._parse_list(result.content)

    async def get_preferences(self, domain: str | None = None) -> dict[str, Any]:
        """获取用户偏好

        Args:
            domain: 偏好领域（如 "编程"、"工作"、"学习"），None 表示全部

        Returns:
            偏好字典
        """
        if domain:
            query = f"用户在{domain}方面有什么偏好？"
        else:
            query = "用户在工作、生活、学习方面有什么偏好？"

        result = await self.query(query, mode="hybrid")

        return self._parse_preferences(result.content)

    async def get_habits(self) -> list[str]:
        """获取用户习惯

        Returns:
            习惯列表
        """
        result = await self.query(
            "用户有什么日常习惯？",
            mode="local"
        )

        return self._parse_list(result.content)

    async def get_skills(self) -> list[str]:
        """获取用户技能

        Returns:
            技能列表
        """
        result = await self.query(
            "用户掌握哪些技能？",
            mode="local"
        )

        return self._parse_list(result.content)

    async def get_goals(self) -> list[str]:
        """获取用户目标

        Returns:
            目标列表
        """
        result = await self.query(
            "用户的目标是什么？",
            mode="local"
        )

        return self._parse_list(result.content)

    async def get_summary(self) -> dict[str, Any]:
        """获取用户画像摘要

        Returns:
            画像摘要
        """
        result = await self.query(
            "请总结用户的基本信息、兴趣、偏好、习惯和目标。",
            mode="global"
        )

        return {
            "user_id": self.user_id,
            "summary": result.content,
            "interests": await self.get_interests(),
            "habits": await self.get_habits(),
            "skills": await self.get_skills(),
            "goals": await self.get_goals(),
        }

    async def get_related_info(self, topic: str) -> str:
        """获取与主题相关的用户信息

        Args:
            topic: 主题

        Returns:
            相关信息
        """
        result = await self.query(
            f"关于{topic}，用户有什么相关信息？",
            mode="local",
            only_need_context=True
        )

        return result.context or ""

    async def clear_profile(self) -> bool:
        """清空用户画像

        Returns:
            是否成功
        """
        client = await self._get_client()
        return await client.clear()

    def _parse_list(self, content: str) -> list[str]:
        """解析列表内容"""
        items = []

        # 尝试解析列表格式
        for line in content.split("\n"):
            line = line.strip()
            # 处理 "- item" 或 "1. item" 格式
            if line.startswith("- ") or line.startswith("* "):
                items.append(line[2:].strip())
            elif line and line[0].isdigit() and ". " in line:
                items.append(line.split(". ", 1)[1].strip())
            elif line and not line.startswith("#"):
                items.append(line)

        return [item for item in items if item]

    def _parse_preferences(self, content: str) -> dict[str, Any]:
        """解析偏好内容"""
        preferences = {}

        # 简单解析：按段落分割
        paragraphs = content.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if ":" in para or "：" in para:
                # 尝试解析 key: value 格式
                parts = para.replace("：", ":").split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    preferences[key] = value

        return preferences


# 便捷函数
async def get_user_profile(user_id: str) -> UserProfileManager:
    """获取用户画像管理器

    Args:
        user_id: 用户 ID

    Returns:
        UserProfileManager
    """
    return UserProfileManager(user_id)


async def get_user_interests(user_id: str) -> list[str]:
    """获取用户兴趣

    Args:
        user_id: 用户 ID

    Returns:
        兴趣列表
    """
    profile = UserProfileManager(user_id)
    return await profile.get_interests()


async def get_user_summary(user_id: str) -> dict[str, Any]:
    """获取用户画像摘要

    Args:
        user_id: 用户 ID

    Returns:
        画像摘要
    """
    profile = UserProfileManager(user_id)
    return await profile.get_summary()
