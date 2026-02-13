"""Tests for session management."""

import tempfile
from pathlib import Path

import pytest

from beehive.core.session import AgentSession, SessionManager, SessionStatus


def test_session_creation():
    """Test creating a session."""
    session = AgentSession(
        name="test-session",
        branch_name="beehive/test-session-a1b2",
        instructions="Do something",
        tmux_session_name="beehive-a1b2",
        log_file="/tmp/test.log",
        working_directory="/tmp/worktree",
        original_repo="/tmp/repo",
    )

    assert session.name == "test-session"
    assert session.status == SessionStatus.RUNNING
    assert session.session_id is not None
    assert len(session.session_id) == 8
    assert session.original_repo == "/tmp/repo"


def test_session_manager_create():
    """Test session manager creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(Path(tmpdir))
        session = manager.create_session(
            name="test",
            instructions="Test instructions",
            working_dir=Path("/tmp"),
        )

        assert session.name == "test"
        assert session.branch_name.startswith("beehive/test-")
        assert session.tmux_session_name.startswith("beehive-")
        assert session.original_repo == "/tmp"
        assert "/worktrees/" in session.working_directory


def test_session_manager_get():
    """Test retrieving a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(Path(tmpdir))
        session = manager.create_session(
            name="test",
            instructions="Test",
            working_dir=Path("/tmp"),
        )

        # Full ID
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

        # Partial ID
        partial = session.session_id[:4]
        retrieved = manager.get_session(partial)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id


def test_session_manager_list():
    """Test listing sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(Path(tmpdir))

        # Create multiple sessions
        session1 = manager.create_session("test1", "Instructions", Path("/tmp"))
        session2 = manager.create_session("test2", "Instructions", Path("/tmp"))

        # List all
        sessions = manager.list_sessions()
        assert len(sessions) == 2

        # Update one to completed
        manager.update_session(session1.session_id, status=SessionStatus.COMPLETED)

        # Filter by status
        running = manager.list_sessions(SessionStatus.RUNNING)
        assert len(running) == 1
        assert running[0].session_id == session2.session_id

        completed = manager.list_sessions(SessionStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].session_id == session1.session_id


def test_session_manager_update():
    """Test updating a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(Path(tmpdir))
        session = manager.create_session("test", "Instructions", Path("/tmp"))

        # Update status
        updated = manager.update_session(
            session.session_id,
            status=SessionStatus.COMPLETED,
            pr_url="https://github.com/test/pr/1",
        )

        assert updated.status == SessionStatus.COMPLETED
        assert updated.pr_url == "https://github.com/test/pr/1"
        assert updated.completed_at is not None


def test_session_manager_delete():
    """Test deleting a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(Path(tmpdir))
        session = manager.create_session("test", "Instructions", Path("/tmp"))

        # Delete
        manager.delete_session(session.session_id)

        # Verify deleted
        retrieved = manager.get_session(session.session_id)
        assert retrieved is None
