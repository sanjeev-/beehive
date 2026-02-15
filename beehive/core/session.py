"""Session data models and management."""

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionStatus(str, Enum):
    """Status of an agent session."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AgentSession(BaseModel):
    """Represents a Claude Code agent session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    branch_name: str
    instructions: str
    status: SessionStatus = SessionStatus.RUNNING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    tmux_session_name: str  # e.g., "beehive-a1b2c3d4"
    log_file: str  # Store as string for JSON serialization
    working_directory: str  # Git worktree path (isolated workspace)
    original_repo: str  # Original repository path
    pr_url: Optional[str] = None
    preview_url: Optional[str] = None
    container_name: Optional[str] = None  # e.g. "beehive-a1b2c3d4" or None
    runtime: str = "host"  # "host" or "docker"

    model_config = ConfigDict(use_enum_values=True)


class SessionManager:
    """Manages session lifecycle and state."""

    def __init__(self, storage_path: Path):
        """Initialize session manager with storage path."""
        self.storage_path = storage_path
        # Import here to avoid circular dependency
        from beehive.core.storage import SessionStorage

        self.storage = SessionStorage(storage_path)

    def create_session(
        self,
        name: str,
        instructions: str,
        working_dir: Path,
        base_branch: str = "main",
        use_docker: bool = False,
    ) -> AgentSession:
        """Create new session with worktree and tmux session."""
        from beehive.core.git_ops import generate_branch_name

        # Generate session ID and branch name
        session_id = str(uuid.uuid4())[:8]
        branch_name = generate_branch_name(name, session_id)
        tmux_session_name = f"beehive-{session_id}"

        # Get log file path
        log_file = self.storage.get_log_path(session_id)

        # Get worktree path (isolated workspace for this agent)
        worktree_path = self.storage.get_worktree_path(session_id)

        # Create session object
        session = AgentSession(
            session_id=session_id,
            name=name,
            branch_name=branch_name,
            instructions=instructions,
            tmux_session_name=tmux_session_name,
            log_file=str(log_file),
            working_directory=str(worktree_path),
            original_repo=str(working_dir),
            container_name=f"beehive-{session_id}" if use_docker else None,
            runtime="docker" if use_docker else "host",
        )

        # Save to storage
        self.storage.save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Retrieve session by ID (supports partial ID matching)."""
        return self.storage.load_session(session_id)

    def list_sessions(
        self, status_filter: Optional[SessionStatus] = None
    ) -> list[AgentSession]:
        """List all sessions, optionally filtered by status."""
        sessions = self.storage.load_all_sessions()
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        # Sort by created_at, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def update_session(self, session_id: str, **kwargs) -> AgentSession:
        """Update session fields and persist."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Update fields
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        # Special handling for completed_at
        if "status" in kwargs and kwargs["status"] == SessionStatus.COMPLETED:
            if not session.completed_at:
                session.completed_at = datetime.utcnow()

        # Save updated session
        self.storage.save_session(session)
        return session

    def auto_complete_sessions(self) -> list[str]:
        """Detect sessions whose agent process has finished and mark them completed.

        Detection methods:
        1. `.beehive-done` marker file (written by agent command on exit)
        2. Docker container no longer running (for docker sessions)

        Returns list of session IDs that were auto-completed.
        """
        import subprocess as _sp

        completed_ids = []
        for session in self.list_sessions(status_filter=SessionStatus.RUNNING):
            done = False

            # Check 1: marker file
            done_marker = Path(session.working_directory) / ".beehive-done"
            if done_marker.exists():
                done = True

            # Check 2: Docker container exited
            if not done and session.container_name:
                result = _sp.run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", session.container_name],
                    capture_output=True, text=True,
                )
                # Container doesn't exist (removed by --rm) or is not running
                if result.returncode != 0 or result.stdout.strip() != "true":
                    done = True

            if done:
                self.update_session(session.session_id, status=SessionStatus.COMPLETED)
                completed_ids.append(session.session_id)
        return completed_ids

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self.storage.delete_session(session_id)
