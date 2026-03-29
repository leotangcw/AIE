"""KnowledgeHub 工具

提供给 Agent 的企业知识库访问能力:
- knowledge_retrieve: 从知识库中检索相关知识
- knowledge_query_db: 使用自然语言查询企业数据库
- knowledge_list_sources: 列出所有可用的知识源
"""

from typing import Any
from loguru import logger

from backend.modules.tools.base import Tool


class KnowledgeRetrieveTool(Tool):
    """从企业知识库中检索相关知识"""

    def __init__(self, hub):
        """
        初始化知识检索工具

        Args:
            hub: KnowledgeHub 实例
        """
        self._hub = hub

    @property
    def name(self) -> str:
        return "knowledge_retrieve"

    @property
    def description(self) -> str:
        return (
            "从企业知识库中检索相关知识。支持多种检索模式："
            "direct(关键词)、vector(向量)、hybrid(混合推荐)、graph(知识图谱)。"
            "适用于查找企业文档、政策法规、技术资料等。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询文本",
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "direct", "vector", "hybrid", "graph"],
                    "default": "auto",
                    "description": "检索模式。auto 自动选择最佳模式，direct 关键词匹配，vector 语义向量检索，hybrid 混合检索，graph 知识图谱",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "返回结果数量",
                    "minimum": 1,
                    "maximum": 20,
                },
                "use_cache": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否使用缓存",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, mode: str = "auto", top_k: int = 5, use_cache: bool = True, **kwargs) -> str:
        try:
            # auto 模式由 hub 根据配置自动选择
            retrieve_mode = None if mode == "auto" else mode

            logger.info(f"Knowledge retrieve: query='{query[:50]}...' mode={mode} top_k={top_k}")

            result = await self._hub.retrieve(
                query=query,
                mode=retrieve_mode,
                use_cache=use_cache,
                top_k=top_k,
            )

            if not result.content:
                return f"未找到与 \"{query}\" 相关的知识内容。"

            # 格式化输出
            lines = [
                f"检索模式: {result.mode}",
                f"处理耗时: {result.processing_time:.3f}s",
                "",
                "=== 检索结果 ===",
                result.content,
            ]

            # 附加来源信息
            if result.sources:
                lines.append("")
                lines.append("=== 来源 ===")
                for i, source in enumerate(result.sources[:top_k], 1):
                    source_name = source.get("source", "未知来源")
                    score = source.get("score", "")
                    content_preview = source.get("content", "")
                    if content_preview and len(content_preview) > 80:
                        content_preview = content_preview[:80] + "..."

                    line = f"{i}. {source_name}"
                    if score:
                        line += f" (相关度: {score:.2f})"
                    if content_preview:
                        line += f"\n   {content_preview}"
                    lines.append(line)

            logger.info(f"Knowledge retrieve completed: {len(result.sources)} sources found")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Knowledge retrieve failed: {e}")
            return f"知识检索失败: {e}"


class KnowledgeQueryDBTool(Tool):
    """使用自然语言查询企业数据库"""

    def __init__(self, hub):
        """
        初始化数据库查询工具

        Args:
            hub: KnowledgeHub 实例
        """
        self._hub = hub

    @property
    def name(self) -> str:
        return "knowledge_query_db"

    @property
    def description(self) -> str:
        return (
            "使用自然语言查询企业数据库。自动生成SQL查询语句并执行，获取结构化数据。"
            "适用于查询业务数据、统计报表等。需要先配置数据库知识源。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "自然语言问题，例如 '查询2026年Q1销售总额'",
                },
                "source_id": {
                    "type": "string",
                    "description": "指定数据库源ID（可选，不指定则使用默认数据库）",
                },
            },
            "required": ["question"],
        }

    async def execute(self, question: str, source_id: str = None, **kwargs) -> str:
        try:
            logger.info(f"Knowledge DB query: question='{question[:50]}...' source_id={source_id}")

            result = await self._hub.query_database(
                question=question,
                source_id=source_id,
            )

            if "error" in result:
                return f"数据库查询错误: {result['error']}"

            # 格式化输出
            lines = [
                f"问题: {question}",
                "",
            ]

            if "sql" in result:
                lines.append("=== 生成的SQL ===")
                lines.append(result["sql"])
                lines.append("")

            if "data" in result:
                data = result["data"]
                if isinstance(data, list) and data:
                    # 表格格式输出
                    if isinstance(data[0], dict):
                        headers = list(data[0].keys())
                        # 计算列宽
                        col_widths = {}
                        for h in headers:
                            col_widths[h] = max(
                                len(str(h)),
                                max((len(str(row.get(h, ""))) for row in data), default=0)
                            )
                            # 限制列宽
                            col_widths[h] = min(col_widths[h], 40)

                        # 表头
                        header_line = " | ".join(
                            str(h).ljust(col_widths[h]) for h in headers
                        )
                        lines.append("=== 查询结果 ===")
                        lines.append(header_line)
                        lines.append("-+-".join("-" * col_widths[h] for h in headers))

                        # 数据行
                        for row in data[:20]:  # 最多显示20行
                            row_line = " | ".join(
                                str(row.get(h, ""))[:col_widths[h]].ljust(col_widths[h])
                                for h in headers
                            )
                            lines.append(row_line)

                        total = len(data)
                        if total > 20:
                            lines.append(f"... 共 {total} 条记录，仅显示前 20 条")
                    else:
                        lines.append("=== 查询结果 ===")
                        for item in data[:20]:
                            lines.append(f"- {item}")
                        if len(data) > 20:
                            lines.append(f"... 共 {len(data)} 条记录")
                elif isinstance(data, str):
                    lines.append("=== 查询结果 ===")
                    lines.append(data)
                else:
                    lines.append("=== 查询结果 ===")
                    lines.append(str(data))
            else:
                lines.append(str(result))

            logger.info(f"Knowledge DB query completed successfully")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Knowledge DB query failed: {e}")
            return f"数据库查询失败: {e}"


class KnowledgeListSourcesTool(Tool):
    """列出所有可用的企业知识源"""

    def __init__(self, hub):
        """
        初始化知识源列表工具

        Args:
            hub: KnowledgeHub 实例
        """
        self._hub = hub

    @property
    def name(self) -> str:
        return "knowledge_list_sources"

    @property
    def description(self) -> str:
        return (
            "列出所有可用的企业知识源，包括本地文件、数据库、网络搜索等。"
            "用于了解当前知识库中有哪些数据来源可供检索。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs) -> str:
        try:
            sources = self._hub.get_sources()
            logger.info(f"Knowledge list sources: {len(sources)} sources")

            if not sources:
                return "当前没有配置任何知识源。请在知识库管理中添加知识源。"

            # 类型映射为中文
            type_names = {
                "local": "本地文件",
                "database": "数据库",
                "web_search": "网络搜索",
            }

            lines = [f"共 {len(sources)} 个知识源：", ""]

            enabled_count = 0
            for i, source in enumerate(sources, 1):
                status = "启用" if source.enabled else "禁用"
                if source.enabled:
                    enabled_count += 1

                type_label = type_names.get(source.source_type, source.source_type)
                name = source.name or source.id

                line = f"{i}. [{status}] {name} (ID: {source.id})"
                lines.append(line)
                lines.append(f"   类型: {type_label} | 优先级: {source.priority}")

                if source.description:
                    lines.append(f"   描述: {source.description}")
                if source.tags:
                    lines.append(f"   标签: {', '.join(source.tags)}")
                lines.append("")

            lines.append(f"已启用 {enabled_count}/{len(sources)} 个知识源")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Knowledge list sources failed: {e}")
            return f"获取知识源列表失败: {e}"
