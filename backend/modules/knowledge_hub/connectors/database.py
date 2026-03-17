"""数据库接入器 - 自动SQL生成"""

import re
from typing import Optional
from loguru import logger

from .base import BaseConnector


class DatabaseConnector(BaseConnector):
    """数据库自动SQL接入器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.connection_string = config.get("connection_string", "")
        self.tables = config.get("tables", [])
        self.llm_config = config.get("llm", {})
        self._connection = None

    async def connect(self) -> bool:
        """连接数据库"""
        if not self.connection_string:
            return False

        # TODO: 实现数据库连接
        # 示例: self._connection = await create_connection(self.connection_string)
        return bool(self.connection_string)

    async def fetch(self, query: str = None) -> list[dict]:
        """获取数据（需要通过LLM生成SQL）"""
        return []

    async def sync(self) -> int:
        """同步表结构"""
        # TODO: 实现表结构获取
        return len(self.tables)

    async def execute_query(self, question: str) -> dict:
        """智能执行查询"""

        # 1. 获取表结构
        schema = await self.get_schema()

        # 2. LLM生成SQL
        sql = await self.generate_sql(question, schema)

        # 3. 验证SQL
        if not self.validate_sql(sql):
            return {"error": "SQL验证失败", "sql": sql}

        # 4. 执行SQL
        result = await self.run_sql(sql)

        return {
            "sql": sql,
            "result": result,
            "schema": schema
        }

    async def get_schema(self) -> dict:
        """获取数据库表结构"""
        # TODO: 实现表结构获取
        # 示例: 使用 SQLAlchemy 或原生数据库驱动获取表结构
        return {"tables": self.tables}

    async def generate_sql(self, question: str, schema: dict) -> str:
        """LLM生成SQL"""
        # 构建表结构描述
        schema_desc = self._format_schema(schema)

        # 构建提示词
        prompt = f"""根据用户问题生成SQL查询语句。

表结构：
{schema_desc}

用户问题：{question}

要求：
1. 只生成 SELECT 查询语句
2. 返回纯SQL，不要包含解释
3. 确保SQL语法正确

SQL："""

        # 调用LLM生成SQL
        try:
            if self.llm_config:
                result = await self._call_llm(prompt)
                # 提取SQL
                sql = self._extract_sql(result)
                return sql
        except Exception as e:
            logger.error(f"LLM生成SQL失败: {e}")

        # 降级处理
        return "SELECT * FROM table LIMIT 10"

    def _format_schema(self, schema: dict) -> str:
        """格式化表结构"""
        lines = []
        for table in schema.get("tables", []):
            table_name = table.get("name", "unknown")
            lines.append(f"表: {table_name}")
            for col in table.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_desc = col.get("description", "")
                lines.append(f"  - {col_name} ({col_type}){' - ' + col_desc if col_desc else ''}")
            lines.append("")
        return "\n".join(lines)

    def _extract_sql(self, text: str) -> str:
        """从LLM输出中提取SQL"""
        # 简单处理：取第一行或最后一个代码块
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.upper().startswith("SELECT"):
                return line

        # 如果没有找到，尝试最后一个代码块
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "SELECT" in part.upper():
                    return part.strip()

        return text.strip()

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        model = self.llm_config.get("model", "gpt-3.5-turbo")
        temperature = self.llm_config.get("temperature", 0.3)

        try:
            from litellm import acompletion
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=500
            )
            return response.choices[0].message.content
        except ImportError:
            return "LLM未配置"
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

    def validate_sql(self, sql: str) -> bool:
        """验证SQL安全性"""
        dangerous = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "CREATE", "GRANT", "REVOKE"]
        upper_sql = sql.upper()
        return not any(d in upper_sql for d in dangerous)

    async def run_sql(self, sql: str) -> list:
        """执行SQL"""
        # TODO: 实现SQL执行
        # 示例:
        # async with self._connection.cursor() as cursor:
        #     await cursor.execute(sql)
        #     results = await cursor.fetchall()
        #     return results
        return []
