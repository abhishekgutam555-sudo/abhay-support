"""
database.py
-----------
SQLite se saari conversations save aur load karo.
Har restart ke baad bhi history safe rahegi.
"""

import sqlite3
from datetime import datetime

DB_FILE = "abhay_data.db"


class Database:

    def __init__(self):
        self._init_tables()

    def _connect(self):
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT    NOT NULL,
                    role       TEXT    NOT NULL,
                    content    TEXT    NOT NULL,
                    intent     TEXT    DEFAULT 'general',
                    escalated  INTEGER DEFAULT 0,
                    ts         TEXT    NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    name       TEXT,
                    phone      TEXT,
                    email      TEXT,
                    ts         TEXT NOT NULL
                )
            """)

    # ── Messages ───────────────────────────────────────────────────────────────

    def save_message(self, session_id: str, role: str, content: str,
                     intent: str = "general", escalated: bool = False):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO messages (session_id, role, content, intent, escalated, ts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, intent,
                  int(escalated), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def get_history(self, session_id: str, max_turns: int = 8) -> list:
        """Last N turns — Groq API format mein."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT role, content FROM messages
                WHERE session_id = ? AND role IN ('user','assistant')
                ORDER BY id DESC LIMIT ?
            """, (session_id, max_turns * 2)).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── Dashboard data ─────────────────────────────────────────────────────────

    def get_all_sessions(self) -> list:
        with self._connect() as conn:
            return conn.execute("""
                SELECT
                    session_id,
                    COUNT(*)        AS msg_count,
                    MAX(ts)         AS last_active,
                    SUM(escalated)  AS escalations
                FROM messages
                GROUP BY session_id
                ORDER BY last_active DESC
                LIMIT 50
            """).fetchall()

    def get_session_messages(self, session_id: str) -> list:
        with self._connect() as conn:
            return conn.execute("""
                SELECT role, content, intent, escalated, ts
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,)).fetchall()

    def get_total_stats(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT session_id) AS total_sessions,
                    COUNT(*)                   AS total_messages,
                    SUM(escalated)             AS total_escalations
                FROM messages
            """).fetchone()
        return dict(row) if row else {}

    # ── Lead capture ───────────────────────────────────────────────────────────

    def save_lead(self, session_id: str, name: str = None,
                  phone: str = None, email: str = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO leads (session_id, name, phone, email, ts)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, name, phone, email,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def get_leads(self) -> list:
        with self._connect() as conn:
            return conn.execute("""
                SELECT * FROM leads ORDER BY ts DESC LIMIT 100
            """).fetchall()
