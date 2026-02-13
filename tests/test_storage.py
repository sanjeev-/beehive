"""Tests for storage layer."""

import tempfile
from pathlib import Path

from beehive.core.session import AgentSession, SessionStatus
from beehive.core.storage import SessionStorage


def test_storage_initialization():
    """Test storage initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        assert storage.data_dir.exists()
        assert storage.logs_dir.exists()
        assert storage.worktrees_dir.exists()
        assert storage.sessions_file.exists()
        assert storage.sessions_file.read_text() == "[]"


def test_save_and_load_session():
    """Test saving and loading a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        session = AgentSession(
            session_id="a1b2c3d4",
            name="test",
            branch_name="beehive/test-a1b2",
            instructions="Test",
            tmux_session_name="beehive-a1b2",
            log_file="/tmp/test.log",
            working_directory="/tmp/worktree",
            original_repo="/tmp/repo",
        )

        # Save
        storage.save_session(session)

        # Load
        loaded = storage.load_session("a1b2c3d4")
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.name == session.name
        assert loaded.original_repo == session.original_repo


def test_partial_id_matching():
    """Test partial ID matching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        session = AgentSession(
            session_id="a1b2c3d4",
            name="test",
            branch_name="beehive/test",
            instructions="Test",
            tmux_session_name="beehive-a1b2",
            log_file="/tmp/test.log",
            working_directory="/tmp/worktree",
            original_repo="/tmp/repo",
        )

        storage.save_session(session)

        # Full ID
        assert storage.load_session("a1b2c3d4") is not None

        # Partial IDs
        assert storage.load_session("a1b2") is not None
        assert storage.load_session("a1") is not None

        # Non-matching
        assert storage.load_session("z9z9") is None


def test_load_all_sessions():
    """Test loading all sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        # Create multiple sessions
        for i in range(3):
            session = AgentSession(
                session_id=f"id{i}",
                name=f"test{i}",
                branch_name=f"beehive/test{i}",
                instructions="Test",
                tmux_session_name=f"beehive-{i}",
                log_file=f"/tmp/test{i}.log",
                working_directory=f"/tmp/worktree{i}",
                original_repo="/tmp/repo",
            )
            storage.save_session(session)

        # Load all
        sessions = storage.load_all_sessions()
        assert len(sessions) == 3


def test_update_session():
    """Test updating an existing session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        session = AgentSession(
            session_id="a1b2c3d4",
            name="test",
            branch_name="beehive/test",
            instructions="Test",
            tmux_session_name="beehive-a1b2",
            log_file="/tmp/test.log",
            working_directory="/tmp/worktree",
            original_repo="/tmp/repo",
        )

        # Save initial
        storage.save_session(session)

        # Update
        session.status = SessionStatus.COMPLETED
        session.pr_url = "https://github.com/test/pr/1"
        storage.save_session(session)

        # Load and verify
        loaded = storage.load_session("a1b2c3d4")
        assert loaded.status == SessionStatus.COMPLETED
        assert loaded.pr_url == "https://github.com/test/pr/1"


def test_delete_session():
    """Test deleting a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        session = AgentSession(
            session_id="a1b2c3d4",
            name="test",
            branch_name="beehive/test",
            instructions="Test",
            tmux_session_name="beehive-a1b2",
            log_file="/tmp/test.log",
            working_directory="/tmp/worktree",
            original_repo="/tmp/repo",
        )

        storage.save_session(session)
        assert storage.load_session("a1b2") is not None

        # Delete
        storage.delete_session("a1b2")
        assert storage.load_session("a1b2") is None


def test_get_log_path():
    """Test log path generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        log_path = storage.get_log_path("a1b2c3d4")
        assert log_path == storage.logs_dir / "a1b2c3d4.log"


def test_get_worktree_path():
    """Test worktree path generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SessionStorage(Path(tmpdir))

        worktree_path = storage.get_worktree_path("a1b2c3d4")
        assert worktree_path == storage.worktrees_dir / "beehive-a1b2c3d4"
