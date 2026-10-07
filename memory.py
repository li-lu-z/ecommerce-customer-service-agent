# memory.py
# 会话记忆：用 SQLite 持久化保存每个会话的对话历史，重启服务不丢失。

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "sessions.db"


class SessionStore:
    """基于 SQLite 的会话存储，支持多轮对话上下文与持久化。"""

    def __init__(self, max_history: int = 20, db_path: str | None = None):
        self.max_history = max_history
        self._conn = sqlite3.connect(
            str(db_path or DEFAULT_DB), check_same_thread=False
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                session_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                PRIMARY KEY (session_id, seq)
            )
            """
        )
        self._conn.commit()

    def get(self, session_id: str) -> list[dict]:
        """返回该会话最近的历史消息（按时间正序）。"""
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY seq DESC LIMIT ?",
            (session_id, self.max_history),
        ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息，并做长度截断。"""
        seq = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        self._conn.execute(
            "INSERT INTO messages (session_id, seq, role, content) VALUES (?, ?, ?, ?)",
            (session_id, seq, role, content),
        )
        # 只保留最近 max_history 条，避免历史无限增长
        self._conn.execute(
            "DELETE FROM messages WHERE session_id = ? AND seq NOT IN "
            "(SELECT seq FROM messages WHERE session_id = ? ORDER BY seq DESC LIMIT ?)",
            (session_id, session_id, self.max_history),
        )
        self._conn.commit()

    def clear(self, session_id: str) -> None:
        """清空某个会话。"""
        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self._conn.commit()


class RedisSessionStore:
    """基于 Redis 的会话存储（生产环境用，支持多实例并发与持久化）。"""

    def __init__(self, max_history: int = 20, redis_url: str | None = None):
        import redis  # 延迟导入，避免本地未安装 redis 包时影响 SQLite 模式

        self.max_history = max_history
        self.redis = redis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )

    def get(self, session_id: str) -> list[dict]:
        """返回该会话最近的历史消息（按时间正序）。"""
        key = f"chat:{session_id}"
        items = self.redis.lrange(key, 0, -1)
        history = [json.loads(i) for i in items if i]
        return history[-self.max_history :]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息，并裁剪到最近 max_history 条。"""
        key = f"chat:{session_id}"
        self.redis.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
        self.redis.ltrim(key, -self.max_history, -1)

    def clear(self, session_id: str) -> None:
        """清空某个会话。"""
        self.redis.delete(f"chat:{session_id}")


def create_store(max_history: int = 20):
    """根据环境变量选择会话存储：有 REDIS_URL 用 Redis，否则用本地 SQLite。"""
    if os.getenv("REDIS_URL"):
        return RedisSessionStore(max_history)
    return SessionStore(max_history)
