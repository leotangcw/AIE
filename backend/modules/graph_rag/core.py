"""GraphRAG 核心封装

基于 LightRAG 的知识图谱检索客户端封装。
提供统一的接口用于文档索引、知识查询和图谱管理。
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Optional, Literal, Callable

import numpy as np
from loguru import logger

from backend.core.model_registry import get_model_registry, EmbedderUnavailableError
from backend.utils.paths import MEMORY_DIR
from .config import (
    GraphRAGSettings,
    GraphRAGStats,
    QueryResult,
    InsertResult,
    DEFAULT_WORKING_DIR,
    DEFAULT_MODE,
    DEFAULT_TOP_K,
    DEFAULT_CHUNK_TOP_K,
)


# 条件导入 LightRAG
_LightRAG = None
_QueryParam = None
_wrap_embedding_func_with_attrs = None
LIGHTERAG_AVAILABLE = False

try:
    from lightrag import LightRAG as _LightRAG
    from lightrag.base import QueryParam as _QueryParam
    from lightrag.utils import wrap_embedding_func_with_attrs as _wrap_embedding_func_with_attrs
    LIGHTERAG_AVAILABLE = True
except ImportError:
    logger.warning("LightRAG not installed. Install with: pip install lightrag-hku")


def _get_llm_config() -> tuple[str, str, str]:
    """获取 LLM 配置（从 ModelRegistry 或环境变量）

    Returns:
        (model, api_key, api_base)
    """
    try:
        # 尝试从 ModelRegistry 获取
        registry = get_model_registry()
        # ModelRegistry 使用 provider factory，我们需要从配置中提取信息
        # 这里使用环境变量作为回退
        pass
    except RuntimeError:
        pass  # ModelRegistry not initialized, use env vars

    # 从环境变量获取配置
    model = os.environ.get("LIGHTRAG_LLM_MODEL", os.environ.get("LLM_MODEL", "qwen3.5-plus"))
    api_key = os.environ.get("LIGHTRAG_API_KEY", os.environ.get("DASHSCOPE_API_KEY", ""))
    api_base = os.environ.get("LIGHTRAG_API_BASE", os.environ.get("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"))

    return model, api_key, api_base


def _get_embedding_config() -> tuple[str, str, str, int]:
    """获取 Embedding 配置（从 ModelRegistry 或环境变量）

    Returns:
        (model, api_key, api_base, dim)
    """
    try:
        # 尝试从 ModelRegistry 获取 embedder
        registry = get_model_registry()
        # 如果能获取到，直接返回默认值（实际嵌入由 UnifiedEmbedder 处理）
        pass
    except RuntimeError:
        pass  # ModelRegistry not initialized, use env vars

    # 从环境变量获取配置
    model = os.environ.get("LIGHTRAG_EMBED_MODEL", "text-embedding-v3")
    api_key = os.environ.get("LIGHTRAG_EMBED_API_KEY", os.environ.get("DASHSCOPE_API_KEY", ""))
    api_base = os.environ.get("LIGHTRAG_EMBED_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dim = int(os.environ.get("LIGHTRAG_EMBED_DIM", "1024"))

    return model, api_key, api_base, dim


async def _litellm_complete(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict] | None = None,
    **kwargs,
) -> str:
    """使用 LiteLLM 进行 LLM 完成

    兼容 LightRAG 的调用签名
    """
    import litellm

    model, api_key, api_base = _get_llm_config()

    # 构建消息
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    try:
        response = await litellm.acompletion(
            model=f"openai/{model}",
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LiteLLM completion failed: {e}")
        raise


async def _registry_embed(texts: list[str]) -> np.ndarray:
    """使用 ModelRegistry 的 Embedder 进行文本嵌入

    Returns:
        numpy array of embeddings
    """
    registry = get_model_registry()
    embedder = await registry.get_embedder()
    return await embedder.embed(texts)


async def _litellm_embed(texts: list[str], **kwargs) -> np.ndarray:
    """使用 LiteLLM 进行文本嵌入（回退方案）

    Returns:
        numpy array of embeddings
    """
    import litellm

    model, api_key, api_base, dim = _get_embedding_config()

    try:
        # LiteLLM embedding
        response = await litellm.aembedding(
            model=f"openai/{model}",
            input=texts,
            api_key=api_key,
            api_base=api_base,
        )

        # 提取 embeddings
        embeddings = [item["embedding"] for item in response.data]
        return np.array(embeddings, dtype=np.float32)
    except Exception as e:
        logger.error(f"LiteLLM embedding failed: {e}")
        raise


def _create_embedding_func(embedding_dim: int = 1024):
    """创建带属性的嵌入函数（LightRAG 要求）

    使用 ModelRegistry 获取 embedder，如果不可用则回退到 LiteLLM
    """
    if _wrap_embedding_func_with_attrs is None:
        return None

    # 尝试从 ModelRegistry 获取维度
    try:
        registry = get_model_registry()
        # 同步获取 embedder 维度比较麻烦，使用传入的默认值
    except RuntimeError:
        pass

    @_wrap_embedding_func_with_attrs(embedding_dim=embedding_dim, max_token_size=8192)
    async def embed_func(texts: list[str], **kwargs) -> np.ndarray:
        # 优先使用 ModelRegistry 的 embedder
        try:
            registry = get_model_registry()
            embedder = await registry.get_embedder()
            return await embedder.embed(texts)
        except EmbedderUnavailableError:
            logger.warning("ModelRegistry embedder unavailable, falling back to LiteLLM")
        except RuntimeError:
            logger.warning("ModelRegistry not initialized, falling back to LiteLLM")
        except Exception as e:
            logger.warning(f"ModelRegistry embedder failed: {e}, falling back to LiteLLM")

        # 回退到 LiteLLM
        return await _litellm_embed(texts, **kwargs)

    return embed_func


class GraphRAGClient:
    """LightRAG 客户端封装

    提供统一的接口用于：
    - 文档索引（自动抽取实体和关系）
    - 知识查询（多种检索模式）
    - 图谱管理

    Example:
        ```python
        client = GraphRAGClient(namespace="company_docs")

        # 初始化
        await client.initialize()

        # 索引文档
        await client.insert("AIE 是一个企业级 AI 办公助手...")

        # 查询
        result = await client.query("AIE 的主要功能是什么？")
        print(result.content)
        ```
    """

    _instances: dict[str, "GraphRAGClient"] = {}

    def __init__(
        self,
        namespace: str = "default",
        workspace: str = "default",
        config: GraphRAGSettings | None = None,
        llm_func: Callable | None = None,
        embedding_func: Callable | None = None,
    ):
        """初始化 GraphRAG 客户端

        Args:
            namespace: 命名空间，用于数据隔离
            workspace: 工作空间，用于更高层级的隔离
            config: 配置对象
            llm_func: 自定义 LLM 函数
            embedding_func: 自定义嵌入函数
        """
        self.namespace = namespace
        self.workspace = workspace
        self.config = config or GraphRAGSettings()
        self.llm_func = llm_func
        self.embedding_func = embedding_func

        self._rag: Optional[Any] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(
        cls,
        namespace: str,
        workspace: str = "default",
        config: GraphRAGSettings | None = None
    ) -> "GraphRAGClient":
        """获取单例实例

        Args:
            namespace: 命名空间
            workspace: 工作空间
            config: 配置（仅首次创建时使用）

        Returns:
            GraphRAGClient 实例
        """
        key = f"{workspace}:{namespace}"
        if key not in cls._instances:
            cls._instances[key] = cls(
                namespace=namespace,
                workspace=workspace,
                config=config
            )
        return cls._instances[key]

    @classmethod
    def clear_instance(cls, namespace: str, workspace: str = "default"):
        """清除缓存的实例"""
        key = f"{workspace}:{namespace}"
        if key in cls._instances:
            del cls._instances[key]

    @property
    def is_available(self) -> bool:
        """检查 LightRAG 是否可用"""
        return LIGHTERAG_AVAILABLE

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    async def initialize(self) -> bool:
        """初始化 LightRAG

        Returns:
            是否初始化成功
        """
        async with self._lock:
            if self._initialized:
                return True

            if not LIGHTERAG_AVAILABLE:
                logger.warning(
                    "LightRAG not installed. GraphRAG features disabled. "
                    "Install with: pip install lightrag-hku"
                )
                return False

            try:
                # 构建工作目录
                working_dir = (
                    Path(self.config.working_dir) / self.workspace / self.namespace
                )
                working_dir.mkdir(parents=True, exist_ok=True)

                # 获取 LLM 函数（优先使用传入的，否则使用 LiteLLM）
                llm_func = self.llm_func or _litellm_complete

                # 获取嵌入维度（尝试从 ModelRegistry，否则使用默认值）
                embedding_dim = 1024  # 默认维度
                try:
                    registry = get_model_registry()
                    embedder = await registry.get_embedder()
                    embedding_dim = embedder.dimension
                    logger.debug(f"Using embedder from ModelRegistry with dim={embedding_dim}")
                except EmbedderUnavailableError:
                    logger.warning("Embedder unavailable from ModelRegistry, using LiteLLM fallback")
                except RuntimeError:
                    logger.debug("ModelRegistry not initialized, using default embedding config")

                # 创建嵌入函数（优先使用传入的，否则使用 ModelRegistry/LiteLLM）
                embed_func = self.embedding_func or _create_embedding_func(embedding_dim)

                if embed_func is None:
                    logger.error("Failed to create embedding function")
                    return False

                # 创建 LightRAG 实例
                self._rag = _LightRAG(
                    working_dir=str(working_dir),
                    kv_storage=self.config.kv_storage,
                    vector_storage=self.config.vector_storage,
                    graph_storage=self.config.graph_storage,
                    llm_model_func=llm_func,
                    embedding_func=embed_func,
                )

                # 初始化存储
                await self._rag.initialize_storages()

                self._initialized = True
                logger.info(
                    f"GraphRAG initialized: workspace={self.workspace}, "
                    f"namespace={self.namespace}"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to initialize GraphRAG: {e}")
                self._rag = None
                return False

    async def insert(
        self,
        content: str | list[str],
        file_paths: list[str] | None = None,
        doc_type: str = "document",
    ) -> InsertResult:
        """插入文档到知识图谱

        自动从文档中抽取实体和关系，构建知识图谱。

        Args:
            content: 文档内容或内容列表
            file_paths: 文件路径列表（用于引用）
            doc_type: 文档类型 (document/conversation/code)

        Returns:
            InsertResult 插入结果
        """
        start_time = time.time()
        result = InsertResult(
            namespace=self.namespace,
            document_count=0,
        )

        if not self._initialized:
            if not await self.initialize():
                result.error = "GraphRAG not initialized"
                return result

        if not self._rag:
            result.error = "LightRAG not available"
            return result

        try:
            # 标准化输入
            if isinstance(content, str):
                content = [content]

            result.document_count = len(content)

            # 调用 LightRAG 插入
            await self._rag.ainsert(content, file_paths=file_paths)

            result.success = True
            result.processing_time = time.time() - start_time

            logger.info(
                f"GraphRAG inserted {len(content)} documents "
                f"in {result.processing_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to insert to GraphRAG: {e}")
            result.error = str(e)
            result.processing_time = time.time() - start_time
            return result

    async def query(
        self,
        query: str,
        mode: Literal["local", "global", "hybrid", "naive", "mix"] | None = None,
        top_k: int | None = None,
        only_need_context: bool = False,
        stream: bool = False,
        conversation_history: list[dict] | None = None,
        user_prompt: str | None = None,
    ) -> QueryResult:
        """查询知识图谱

        支持多种查询模式：
        - local: 基于实体的局部检索，适合具体事实查询
        - global: 基于社区的全局检索，适合概括性问题
        - hybrid: 混合 local + global
        - naive: 纯向量检索，适合简单相似度搜索
        - mix: KG + 向量 + 重排序，最高质量

        Args:
            query: 查询问题
            mode: 查询模式
            top_k: 返回结果数量
            only_need_context: 仅返回上下文，不生成回答
            stream: 是否流式返回
            conversation_history: 对话历史
            user_prompt: 用户自定义提示

        Returns:
            QueryResult 查询结果
        """
        start_time = time.time()
        result = QueryResult(
            mode=mode or self.config.default_mode,
        )

        if not self._initialized:
            if not await self.initialize():
                result.error = "GraphRAG not initialized"
                return result

        if not self._rag:
            result.error = "LightRAG not available"
            return result

        try:
            # 构建查询参数
            param = _QueryParam(
                mode=mode or self.config.default_mode,
                top_k=top_k or self.config.top_k,
                chunk_top_k=self.config.chunk_top_k,
                only_need_context=only_need_context,
                stream=stream,
                conversation_history=conversation_history or [],
                user_prompt=user_prompt,
            )

            # 执行查询
            response = await self._rag.aquery(query, param=param)

            # 处理响应
            if hasattr(response, '__aiter__'):
                # 流式响应
                result.content = "[Streaming response]"
            elif isinstance(response, str):
                result.content = response
            elif hasattr(response, 'content'):
                result.content = response.content
                if hasattr(response, 'context'):
                    result.context = response.context
            else:
                result.content = str(response)

            result.processing_time = time.time() - start_time

            logger.debug(
                f"GraphRAG query completed in {result.processing_time:.2f}s "
                f"(mode={result.mode})"
            )

            return result

        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}")
            result.error = str(e)
            result.processing_time = time.time() - start_time
            return result

    async def query_stream(
        self,
        query: str,
        mode: Literal["local", "global", "hybrid", "naive", "mix"] | None = None,
        **kwargs,
    ):
        """流式查询知识图谱

        Yields:
            str: 流式响应文本块
        """
        if not self._initialized:
            if not await self.initialize():
                yield "Error: GraphRAG not initialized"
                return

        if not self._rag:
            yield "Error: LightRAG not available"
            return

        try:
            param = _QueryParam(
                mode=mode or self.config.default_mode,
                stream=True,
                **kwargs
            )

            async for chunk in await self._rag.aquery(query, param=param):
                yield chunk

        except Exception as e:
            logger.error(f"GraphRAG stream query failed: {e}")
            yield f"Error: {str(e)}"

    async def get_stats(self) -> GraphRAGStats:
        """获取图谱统计信息

        Returns:
            GraphRAGStats 统计信息
        """
        stats = GraphRAGStats(
            available=LIGHTERAG_AVAILABLE and self._initialized,
            namespace=self.namespace,
            workspace=self.workspace,
        )

        if not self._initialized or not self._rag:
            return stats

        try:
            # 获取图存储统计
            if hasattr(self._rag, 'chunk_entity_relation_graph'):
                graph = self._rag.chunk_entity_relation_graph
                if hasattr(graph, '_graph'):
                    nx_graph = graph._graph
                    stats.node_count = nx_graph.number_of_nodes()
                    stats.edge_count = nx_graph.number_of_edges()

            stats.available = True
            return stats

        except Exception as e:
            stats.error = str(e)
            return stats

    async def clear(self) -> bool:
        """清空当前命名空间的知识图谱

        Returns:
            是否成功
        """
        if not self._initialized or not self._rag:
            return True

        try:
            # 清空所有存储
            if hasattr(self._rag, 'drop'):
                await self._rag.drop()
            else:
                # 手动清空各存储
                for storage_name in ['full_docs', 'text_chunks',
                                     'chunk_entity_relation_graph',
                                     'entities_vdb', 'relationships_vdb',
                                     'chunks_vdb']:
                    storage = getattr(self._rag, storage_name, None)
                    if storage and hasattr(storage, 'drop'):
                        await storage.drop()

            logger.info(f"Cleared GraphRAG: {self.namespace}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear GraphRAG: {e}")
            return False

    async def finalize(self):
        """清理资源"""
        if self._rag:
            try:
                if hasattr(self._rag, 'finalize_storages'):
                    await self._rag.finalize_storages()
            except Exception as e:
                logger.warning(f"Error finalizing GraphRAG: {e}")

        self._initialized = False

    def __repr__(self) -> str:
        return (
            f"GraphRAGClient(namespace={self.namespace}, "
            f"workspace={self.workspace}, initialized={self._initialized})"
        )


# 模块级缓存
_graph_rag_clients: dict[str, GraphRAGClient] = {}


async def get_graph_rag(
    namespace: str = "default",
    workspace: str = "default",
    config: GraphRAGSettings | None = None,
) -> GraphRAGClient:
    """获取 GraphRAG 客户端实例

    Args:
        namespace: 命名空间
        workspace: 工作空间
        config: 配置

    Returns:
        GraphRAGClient 实例
    """
    client = GraphRAGClient.get_instance(namespace, workspace, config)
    if not client.is_initialized:
        await client.initialize()
    return client


async def index_documents(
    content: str | list[str],
    namespace: str = "default",
    workspace: str = "default",
) -> InsertResult:
    """便捷函数：索引文档到知识图谱

    Args:
        content: 文档内容
        namespace: 命名空间
        workspace: 工作空间

    Returns:
        InsertResult
    """
    client = await get_graph_rag(namespace, workspace)
    return await client.insert(content)


async def query_knowledge(
    query: str,
    namespace: str = "default",
    workspace: str = "default",
    mode: str = "hybrid",
    **kwargs,
) -> QueryResult:
    """便捷函数：查询知识图谱

    Args:
        query: 查询问题
        namespace: 命名空间
        workspace: 工作空间
        mode: 查询模式

    Returns:
        QueryResult
    """
    client = await get_graph_rag(namespace, workspace)
    return await client.query(query, mode=mode, **kwargs)
