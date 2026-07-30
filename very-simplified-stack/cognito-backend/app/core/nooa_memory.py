import sqlite3
import os
import json
import logging
from typing import List, Dict, Any, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)

class NOOAMemoryManager:
    """
    Long-term episodic and semantic memory based on SQLite + optional vector embeddings (NOOA-18).
    Includes direct retrieval tool.
    """
    def __init__(self, db_path: str = "nooa_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT,
                    embedding TEXT, -- JSON array of floats if using embedding mock
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def remember(self, content: str, category: Optional[str] = "general", embedding: Optional[List[float]] = None):
        conn = sqlite3.connect(self.db_path)
        try:
            emb_str = json.dumps(embedding) if embedding else "[]"
            conn.execute(
                "INSERT INTO memories (content, category, embedding) VALUES (?, ?, ?)",
                (content, category, emb_str)
            )
            conn.commit()
        finally:
            conn.close()

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # Simple keyword search fallback if vector extension is not configured
            cursor.execute(
                "SELECT id, content, category, timestamp FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "content": row[1],
                    "category": row[2],
                    "timestamp": row[3]
                })
            return results
        finally:
            conn.close()

class MemoryToolsMixin:
    """
    Mixin adding recall/search/remember cognitive methods to any Agent.
    """
    @property
    def memory_manager(self) -> NOOAMemoryManager:
        if not hasattr(self, "_memory_mgr"):
            self._memory_mgr = NOOAMemoryManager()
        return self._memory_mgr

    async def remember_episodic(self, content: str, category: str = "episodic"):
        self.memory_manager.remember(content, category=category)

    async def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.memory_manager.search(query, limit=limit)
