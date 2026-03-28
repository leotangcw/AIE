"""数据库接入器 - SQLAlchemy 通用实现

支持多种数据库：
- SQLite
- MySQL
- PostgreSQL
- SQL Server
- Oracle
"""

import re
from typing import Optional, Any
from loguru import logger

from .base import BaseConnector
from ..config import DatabaseSourceConfig

# 数据库驱动映射
DB_DRIVERS = {
    "sqlite": "sqlite",
    "mysql": "mysql+pymysql",
    "postgresql": "postgresql+psycopg2",
    "mssql": "mssql+pymssql",
    "oracle": "oracle+cx_oracle",
}


class DatabaseConnector(BaseConnector):
    """数据库接入器 - 支持多种数据库类型"""

    def __init__(self, config: dict | DatabaseSourceConfig):
        super().__init__(config)
        # 解析配置
        if isinstance(config, DatabaseSourceConfig):
            self.db_type = config.db_type
            self.connection_string = config.connection_string
            self.host = config.host
            self.port = config.port
            self.database = config.database
            self.username = config.username
            self.password = config.password
            self.tables = config.tables
            self.text_columns = config.text_columns
            self.id_column = config.id_column
            self.read_only = config.read_only
            self.allowed_operations = config.allowed_operations
        else:
            self.db_type = config.get("db_type", "sqlite")
            self.connection_string = config.get("connection_string", "")
            self.host = config.get("host", "")
            self.port = config.get("port", 0)
            self.database = config.get("database", "")
            self.username = config.get("username", "")
            self.password = config.get("password", "")
            self.tables = config.get("tables", [])
            self.text_columns = config.get("text_columns", [])
            self.id_column = config.get("id_column", "id")
            self.read_only = config.get("read_only", True)
            self.allowed_operations = config.get("allowed_operations", ["SELECT"])

        self._engine = None
        self._connection = None
        self._schema_cache: dict[str, dict] = {}
        self._llm_config = config.get("llm", {}) if isinstance(config, dict) else {}

    def _build_connection_string(self) -> str:
        """构建数据库连接字符串"""
        if self.connection_string:
            return self.connection_string

        driver = DB_DRIVERS.get(self.db_type, self.db_type)

        if self.db_type == "sqlite":
            return f"{driver}:///{self.database}"

        # 其他数据库类型
        port_part = f":{self.port}" if self.port else ""
        return f"{driver}://{self.username}:{self.password}@{self.host}{port_part}/{self.database}"

    async def connect(self) -> bool:
        """连接数据库"""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.ext.asyncio import create_async_engine

            conn_str = self._build_connection_string()

            # 根据数据库类型选择同步或异步引擎
            if "sqlite" in conn_str:
                self._engine = create_engine(conn_str, echo=False)
            else:
                # 异步引擎
                async_conn_str = conn_str.replace("://", "+aiosqlite://") if "sqlite" in conn_str else conn_str
                self._engine = create_engine(conn_str, echo=False)

            # 测试连接
            with self._engine.connect() as conn:
                conn.execute("SELECT 1")

            logger.info(f"Database connected: {self.db_type}")
            return True

        except ImportError:
            logger.error("SQLAlchemy not installed. Run: pip install sqlalchemy")
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    async def fetch(self, query: str = None, table: str = None) -> list[dict]:
        """获取数据"""
        if not self._engine:
            if not await self.connect():
                return []

        results = []
        tables_to_fetch = [table] if table else self.tables

        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                for tbl in tables_to_fetch:
                    try:
                        # 构建查询
                        columns = ", ".join(self.text_columns) if self.text_columns else "*"
                        sql = f"SELECT {columns} FROM {tbl} LIMIT 1000"

                        result = conn.execute(text(sql))
                        columns_names = result.keys()

                        for row in result:
                            row_dict = dict(zip(columns_names, row))
                            row_dict["_table"] = tbl
                            results.append(row_dict)

                    except Exception as e:
                        logger.warning(f"Failed to fetch from table {tbl}: {e}")

        except Exception as e:
            logger.error(f"Database fetch failed: {e}")

        return results

    async def sync(self) -> int:
        """同步表结构到缓存"""
        schema = await self.get_schema()
        total_columns = sum(
            len(tbl.get("columns", []))
            for tbl in schema.get("tables", [])
        )
        logger.info(f"Synced {len(schema.get('tables', []))} tables, {total_columns} columns")
        return len(schema.get("tables", []))

    async def get_schema(self) -> dict:
        """获取数据库表结构"""
        if self._schema_cache:
            return {"tables": list(self._schema_cache.values())}

        if not self._engine:
            if not await self.connect():
                return {"tables": []}

        tables_info = []

        try:
            from sqlalchemy import inspect, text

            inspector = inspect(self._engine)

            # 获取所有表名
            table_names = self.tables if self.tables else inspector.get_table_names()

            for table_name in table_names:
                try:
                    columns = inspector.get_columns(table_name)
                    table_info = {
                        "name": table_name,
                        "columns": [
                            {
                                "name": col["name"],
                                "type": str(col["type"]),
                                "nullable": col.get("nullable", True),
                                "primary_key": col.get("primary_key", False),
                            }
                            for col in columns
                        ],
                        "row_count": await self._get_row_count(table_name),
                    }
                    tables_info.append(table_info)
                    self._schema_cache[table_name] = table_info

                except Exception as e:
                    logger.warning(f"Failed to get schema for {table_name}: {e}")

        except Exception as e:
            logger.error(f"Schema inspection failed: {e}")

        return {"tables": tables_info}

    async def _get_row_count(self, table_name: str) -> int:
        """获取表行数"""
        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar() or 0
        except Exception:
            return 0

    async def execute_query(self, question: str) -> dict:
        """智能执行查询 - LLM 生成 SQL"""

        # 1. 获取表结构
        schema = await self.get_schema()

        # 2. LLM 生成 SQL
        sql = await self.generate_sql(question, schema)

        # 3. 验证 SQL
        if not self.validate_sql(sql):
            return {"error": "SQL验证失败：包含不允许的操作", "sql": sql}

        # 4. 执行 SQL
        result = await self.run_sql(sql)

        return {
            "sql": sql,
            "result": result,
            "schema": schema,
            "row_count": len(result) if isinstance(result, list) else 0,
        }

    async def generate_sql(self, question: str, schema: dict) -> str:
        """LLM 生成 SQL"""
        schema_desc = self._format_schema(schema)

        prompt = f"""根据用户问题生成 SQL 查询语句。

数据库类型: {self.db_type}

表结构：
{schema_desc}

用户问题：{question}

要求：
1. 只生成 SELECT 查询语句
2. 返回纯 SQL，不要包含解释
3. 确保 SQL 语法正确
4. 适当使用 LIMIT 限制结果数量
5. 如果涉及多表，使用 JOIN

SQL："""

        try:
            result = await self._call_llm(prompt)
            sql = self._extract_sql(result)
            return sql
        except Exception as e:
            logger.error(f"LLM 生成 SQL 失败: {e}")

        # 降级处理
        if self.tables:
            return f"SELECT * FROM {self.tables[0]} LIMIT 10"
        return "SELECT 1"

    def _format_schema(self, schema: dict) -> str:
        """格式化表结构"""
        lines = []
        for table in schema.get("tables", []):
            table_name = table.get("name", "unknown")
            row_count = table.get("row_count", 0)
            lines.append(f"表: {table_name} (约 {row_count} 行)")
            for col in table.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                nullable = "可空" if col.get("nullable", True) else "非空"
                pk = " [主键]" if col.get("primary_key") else ""
                lines.append(f"  - {col_name}: {col_type} ({nullable}){pk}")
            lines.append("")
        return "\n".join(lines)

    def _extract_sql(self, text: str) -> str:
        """从 LLM 输出中提取 SQL"""
        # 尝试提取代码块中的 SQL
        code_block_pattern = r"```(?:sql)?\s*([\s\S]*?)```"
        matches = re.findall(code_block_pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip()

        # 尝试找到 SELECT 语句
        lines = text.strip().split("\n")
        sql_lines = []
        in_sql = False

        for line in lines:
            stripped = line.strip()
            if stripped.upper().startswith("SELECT"):
                in_sql = True
            if in_sql:
                sql_lines.append(stripped)
                if ";" in stripped:
                    break

        if sql_lines:
            return " ".join(sql_lines).rstrip(";")

        # 回退：返回整个文本
        return text.strip()

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self._llm_config:
            raise ValueError("LLM 未配置")

        model = self._llm_config.get("model", "gpt-3.5-turbo")
        temperature = self._llm_config.get("temperature", 0.1)
        api_key = self._llm_config.get("api_key", "")
        base_url = self._llm_config.get("base_url", "")

        try:
            from litellm import acompletion
            import os

            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["OPENAI_API_BASE"] = base_url

            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=500,
            )
            return response.choices[0].message.content

        except ImportError:
            logger.warning("litellm not installed, trying direct OpenAI call")
            return await self._call_openai_direct(prompt, model, api_key, base_url, temperature)

    async def _call_openai_direct(
        self, prompt: str, model: str, api_key: str, base_url: str, temperature: float
    ) -> str:
        """直接调用 OpenAI API"""
        import httpx

        url = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 500,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def validate_sql(self, sql: str) -> bool:
        """验证 SQL 安全性"""
        upper_sql = sql.upper()

        # 检查危险操作
        dangerous = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"]
        for d in dangerous:
            if d in upper_sql:
                logger.warning(f"SQL contains dangerous operation: {d}")
                return False

        # 检查是否以 SELECT 开头
        if not upper_sql.strip().startswith("SELECT"):
            logger.warning("SQL must start with SELECT")
            return False

        # 检查是否在允许的操作列表中
        if "SELECT" not in self.allowed_operations:
            logger.warning("SELECT not in allowed operations")
            return False

        return True

    async def run_sql(self, sql: str) -> list[dict]:
        """执行 SQL 查询"""
        if not self._engine:
            if not await self.connect():
                return []

        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = result.keys()

                rows = []
                for row in result:
                    row_dict = dict(zip(columns, row))
                    rows.append(row_dict)

                logger.info(f"SQL executed, returned {len(rows)} rows")
                return rows

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return [{"error": str(e), "sql": sql}]

    async def search_text(self, query: str, table: str = None, limit: int = 100) -> list[dict]:
        """文本搜索 - 在文本列中搜索关键词"""
        if not self.text_columns:
            logger.warning("No text columns configured for search")
            return []

        tables_to_search = [table] if table else self.tables
        results = []

        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                for tbl in tables_to_search:
                    # 构建 LIKE 条件
                    conditions = " OR ".join(
                        f"{col} LIKE :query" for col in self.text_columns
                    )
                    sql = f"SELECT * FROM {tbl} WHERE {conditions} LIMIT {limit}"

                    result = conn.execute(text(sql), {"query": f"%{query}%"})
                    columns = result.keys()

                    for row in result:
                        row_dict = dict(zip(columns, row))
                        row_dict["_table"] = tbl
                        results.append(row_dict)

        except Exception as e:
            logger.error(f"Text search failed: {e}")

        return results
