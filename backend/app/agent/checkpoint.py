"""SQLite checkpointer for multi-turn planning conversations.

A single shared connection is reused across requests (the saver is
thread-safe for a demo-scale single process). Conversation threads are keyed
``{user_id}:{thread_id}`` so replanning requests see full history.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings

_connection: sqlite3.Connection | None = None
_saver: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    global _connection, _saver
    if _saver is not None:
        return _saver

    db_path = Path(get_settings().sqlite_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _connection = sqlite3.connect(str(db_path), check_same_thread=False)
    _saver = SqliteSaver(_connection)
    _saver.setup()
    return _saver
