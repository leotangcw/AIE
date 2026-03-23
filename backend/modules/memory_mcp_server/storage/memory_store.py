"""Memory CRUD operations."""

from datetime import datetime

from ..models.memory import Memory, MemoryCreate, MemoryUpdate
from .database import Database


class MemoryStore:
    """CRUD operations for memories."""

    def __init__(self, db: Database):
        self.db = db

    async def create(self, memory: Memory) -> Memory:
        """Create a new memory."""
        data = memory.to_storage_dict()
        sql = """
            INSERT INTO memories (
                id, uri, parent_uri, context_type, level,
                abstract, overview, content, name, description,
                tags, source, metadata, vector_id,
                created_at, updated_at, active_count, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data["id"], data["uri"], data["parent_uri"], data["context_type"],
            data["level"], data["abstract"], data["overview"], data["content"],
            data["name"], data["description"], data["tags"], data["source"],
            data["metadata"], data["vector_id"], data["created_at"],
            data["updated_at"], data["active_count"], data["tenant_id"],
        )
        await self.db.execute(sql, params)
        return memory

    async def get_by_uri(self, uri: str, level: int | None = None) -> Memory | None:
        """Get a memory by its URI, optionally at a specific level."""
        if level is not None:
            sql = "SELECT * FROM memories WHERE uri = ? AND level = ?"
            row = await self.db.fetchone(sql, (uri, level))
        else:
            sql = "SELECT * FROM memories WHERE uri = ?"
            row = await self.db.fetchone(sql, (uri,))

        if row:
            return Memory.from_storage_dict(dict(row))
        return None

    async def get_by_id(self, memory_id: str) -> Memory | None:
        """Get a memory by its ID."""
        sql = "SELECT * FROM memories WHERE id = ?"
        row = await self.db.fetchone(sql, (memory_id,))
        if row:
            return Memory.from_storage_dict(dict(row))
        return None

    async def update(self, uri: str, update: MemoryUpdate) -> Memory | None:
        """Update a memory's content."""
        current = await self.get_by_uri(uri)
        if not current:
            return None

        # Build dynamic update
        updates = []
        params = []
        now = datetime.utcnow().isoformat()

        if update.content is not None:
            updates.append("content = ?")
            params.append(update.content)
            # Invalidate L0/L1 if content changes significantly
            updates.append("abstract = NULL")
            updates.append("overview = NULL")

        if update.name is not None:
            updates.append("name = ?")
            params.append(update.name)

        if update.abstract is not None:
            updates.append("abstract = ?")
            params.append(update.abstract)

        if update.overview is not None:
            updates.append("overview = ?")
            params.append(update.overview)

        if update.tags is not None:
            import json
            updates.append("tags = ?")
            params.append(json.dumps(update.tags))

        if update.metadata is not None:
            import json
            updates.append("metadata = ?")
            params.append(json.dumps(update.metadata))

        updates.append("updated_at = ?")
        params.append(now)

        if updates:
            sql = f"UPDATE memories SET {', '.join(updates)} WHERE uri = ?"
            params.append(uri)
            await self.db.execute(sql, tuple(params))

        return await self.get_by_uri(uri)

    async def delete(self, uri: str) -> bool:
        """Delete a memory and its children (by URI cascade)."""
        # First get all URIs that start with this prefix
        sql = "SELECT uri FROM memories WHERE uri = ? OR uri LIKE ? || '/%'"
        rows = await self.db.fetchall(sql, (uri, uri))
        uris = [row["uri"] for row in rows]

        if not uris:
            return False

        # Delete all (foreign key cascade handles children)
        placeholders = ",".join("?" * len(uris))
        sql = f"DELETE FROM memories WHERE uri IN ({placeholders})"
        await self.db.execute(sql, tuple(uris))
        return True

    async def list_by_prefix(
        self,
        uri_prefix: str,
        context_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Memory]:
        """List memories under a URI prefix."""
        pattern = uri_prefix.rstrip("/") + "/%"
        if context_type:
            sql = """
                SELECT * FROM memories
                WHERE (uri = ? OR uri LIKE ?) AND context_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = await self.db.fetchall(sql, (uri_prefix, pattern, context_type, limit, offset))
        else:
            sql = """
                SELECT * FROM memories
                WHERE uri = ? OR uri LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = await self.db.fetchall(sql, (uri_prefix, pattern, limit, offset))

        return [Memory.from_storage_dict(dict(row)) for row in rows]

    async def increment_active_count(self, uri: str) -> None:
        """Increment the active count for a memory."""
        sql = "UPDATE memories SET active_count = active_count + 1 WHERE uri = ?"
        await self.db.execute(sql, (uri,))

    async def get_children(self, parent_uri: str) -> list[Memory]:
        """Get direct children of a memory."""
        sql = "SELECT * FROM memories WHERE parent_uri = ? ORDER BY created_at DESC"
        rows = await self.db.fetchall(sql, (parent_uri,))
        return [Memory.from_storage_dict(dict(row)) for row in rows]

    async def get_stats(self, tenant_id: str | None = None) -> dict:
        """Get statistics about stored memories."""
        if tenant_id:
            sql_total = "SELECT COUNT(*) as count FROM memories WHERE tenant_id = ?"
            sql_by_type = """
                SELECT context_type, COUNT(*) as count
                FROM memories WHERE tenant_id = ?
                GROUP BY context_type
            """
            sql_by_level = """
                SELECT level, COUNT(*) as count
                FROM memories WHERE tenant_id = ?
                GROUP BY level
            """
            sql_by_source = """
                SELECT source, COUNT(*) as count
                FROM memories WHERE tenant_id = ?
                GROUP BY source
            """
            total = await self.db.fetchone(sql_total, (tenant_id,))
            by_type = await self.db.fetchall(sql_by_type, (tenant_id,))
            by_level = await self.db.fetchall(sql_by_level, (tenant_id,))
            by_source = await self.db.fetchall(sql_by_source, (tenant_id,))
        else:
            sql_total = "SELECT COUNT(*) as count FROM memories"
            sql_by_type = "SELECT context_type, COUNT(*) as count FROM memories GROUP BY context_type"
            sql_by_level = "SELECT level, COUNT(*) as count FROM memories GROUP BY level"
            sql_by_source = "SELECT source, COUNT(*) as count FROM memories GROUP BY source"
            total = await self.db.fetchone(sql_total)
            by_type = await self.db.fetchall(sql_by_type)
            by_level = await self.db.fetchall(sql_by_level)
            by_source = await self.db.fetchall(sql_by_source)

        return {
            "total": total["count"] if total else 0,
            "by_context_type": {row["context_type"]: row["count"] for row in by_type},
            "by_level": {row["level"]: row["count"] for row in by_level},
            "by_source": {row["source"]: row["count"] for row in by_source},
        }

    async def search_by_keywords(
        self,
        keywords: list[str],
        context_type: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Simple keyword search (fallback when vector search unavailable)."""
        conditions = ["content LIKE ?"]
        params = [f"%{kw}%" for kw in keywords]

        if context_type:
            conditions.append("context_type = ?")
            params.append(context_type)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM memories
            WHERE {where_clause}
            ORDER BY active_count DESC, created_at DESC
            LIMIT ?
        """
        params.append(limit)

        rows = await self.db.fetchall(sql, tuple(params))
        return [Memory.from_storage_dict(dict(row)) for row in rows]
