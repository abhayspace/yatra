"""SQLite checkpointer for multi-turn planning conversations.

Uses AsyncSqliteSaver so the compiled graph can be driven with ``ainvoke``
(and checkpoint operations never block the event loop). Conversation
threads are keyed ``{user_id}:{thread_id}`` so replanning requests see full
history. aiosqlite opens connections lazily on first use, so constructing
the saver here is safe outside a running loop.
"""

from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import get_settings

_saver: AsyncSqliteSaver | None = None
_setup_done = False


def get_checkpointer() -> AsyncSqliteSaver:
    global _saver
    if _saver is not None:
        return _saver

    db_path = Path(get_settings().sqlite_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = aiosqlite.connect(str(db_path), check_same_thread=False)
    _saver = AsyncSqliteSaver(conn)
    return _saver


async def ensure_checkpointer_setup() -> None:
    """Create checkpoint tables once (CREATE TABLE IF NOT EXISTS)."""
    global _setup_done
    if not _setup_done:
        await get_checkpointer().setup()
        _setup_done = True
