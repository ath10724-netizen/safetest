"""SQLite 풀이 이력 저장소."""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from core.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mode        TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    total       INTEGER,
    correct     INTEGER,
    average     REAL,
    passed      INTEGER,
    state       TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    question_id TEXT NOT NULL,
    subject     TEXT NOT NULL,
    unit        TEXT NOT NULL,
    chosen      INTEGER,
    is_correct  INTEGER NOT NULL,
    elapsed_sec REAL,
    answered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_question ON attempts(question_id);
CREATE TABLE IF NOT EXISTS explanations (
    question_id TEXT NOT NULL,
    chosen      INTEGER NOT NULL,
    content     TEXT NOT NULL,
    model       TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (question_id, chosen)
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn, conn:
        conn.executescript(SCHEMA)
        # 이전 버전 DB에는 진행 상태(state) 열이 없으므로 추가한다
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
        if "state" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN state TEXT")


def create_session(mode: str) -> int:
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO sessions (mode, started_at) VALUES (?, ?)", (mode, _now())
        )
        return cur.lastrowid


def finish_session(session_id: int, total: int, correct: int, average: float, passed: bool) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE sessions SET finished_at = ?, total = ?, correct = ?, average = ?, passed = ?, state = NULL"
            " WHERE id = ?",
            (_now(), total, correct, average, int(passed), session_id),
        )


def delete_session(session_id: int) -> None:
    """기록이 하나도 없는 세션을 지운다."""
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM attempts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def save_session_state(session_id: int, state: str) -> None:
    """진행 중인 풀이 상태(JSON)를 저장한다. 새로고침 후 이어 풀기에 쓴다."""
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE sessions SET state = ? WHERE id = ? AND finished_at IS NULL", (state, session_id))


def load_unfinished_state() -> tuple[int, str] | None:
    """가장 최근에 시작한 미완료 세션의 (id, 상태 JSON)을 반환한다."""
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, state FROM sessions WHERE finished_at IS NULL AND state IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return (row["id"], row["state"]) if row else None


def unfinished_session_ids() -> list[int]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT id FROM sessions WHERE finished_at IS NULL").fetchall()
    return [r["id"] for r in rows]


def session_attempts(session_id: int) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM attempts WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
    return [dict(r) for r in rows]


def record_attempt(
    session_id: int, question: dict, chosen: int | None, correct: bool, elapsed_sec: float
) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO attempts (session_id, question_id, subject, unit, chosen, is_correct,"
            " elapsed_sec, answered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                question["id"],
                question["subject"],
                question["unit"],
                chosen,
                int(correct),
                round(elapsed_sec, 1),
                _now(),
            ),
        )


def fetch_attempts() -> list[dict]:
    """전체 풀이 이력을 오래된 순서로 반환한다."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM attempts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def fetch_sessions() -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE finished_at IS NOT NULL ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_explanation(question_id: str, chosen: int) -> str | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT content FROM explanations WHERE question_id = ? AND chosen = ?",
            (question_id, chosen),
        ).fetchone()
    return row["content"] if row else None


def save_explanation(question_id: str, chosen: int, content: str, model: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO explanations (question_id, chosen, content, model, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (question_id, chosen, content, model, _now()),
        )


def reset_history() -> None:
    """풀이 이력을 삭제한다. 비용이 드는 AI 해설 캐시는 유지한다."""
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM attempts")
        conn.execute("DELETE FROM sessions")
