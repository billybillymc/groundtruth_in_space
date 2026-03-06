"""Tests for SQLite feedback storage."""

import os
import tempfile

from src.feedback.store import get_all_feedback, init_feedback_db, save_feedback


def test_init_creates_table():
    """init_feedback_db should create the feedback table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_feedback_db(db_path)
        assert os.path.exists(db_path)


def test_save_and_retrieve_feedback():
    """Feedback should round-trip through SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_feedback_db(db_path)

        save_feedback("What is X?", "X is a component.", "Good answer!", db_path)
        save_feedback("What is Y?", "Y is a type.", "Needs more detail.", db_path)

        feedback = get_all_feedback(db_path)
        assert len(feedback) == 2
        # Verify both entries exist
        queries = {f["query"] for f in feedback}
        assert "What is X?" in queries
        assert "What is Y?" in queries


def test_feedback_has_timestamp():
    """Each feedback entry should have a created_at timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_feedback_db(db_path)
        save_feedback("q", "a", "f", db_path)

        feedback = get_all_feedback(db_path)
        assert feedback[0]["created_at"] is not None


def test_empty_feedback():
    """Should return empty list when no feedback exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_feedback_db(db_path)
        assert get_all_feedback(db_path) == []
