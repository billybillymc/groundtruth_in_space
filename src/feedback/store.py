"""SQLite feedback storage for /criticize command."""

import sqlite3
from typing import Dict, List

from src.config import FEEDBACK_DB_PATH


def init_feedback_db(db_path: str = FEEDBACK_DB_PATH) -> None:
    """Create feedback table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_feedback(
    query: str, answer: str, feedback_text: str, db_path: str = FEEDBACK_DB_PATH
) -> None:
    """Save user feedback to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO feedback (query, answer, feedback_text) VALUES (?, ?, ?)",
        (query, answer, feedback_text),
    )
    conn.commit()
    conn.close()


def get_all_feedback(db_path: str = FEEDBACK_DB_PATH) -> List[Dict]:
    """Retrieve all feedback entries."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, query, answer, feedback_text, created_at FROM feedback ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
