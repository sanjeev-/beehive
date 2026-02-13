"""Session persistence with file locking."""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from beehive.core.session import AgentSession


class SessionStorage:
    """Handles persistence of session metadata."""

    def __init__(self, data_dir: Path):
        """Initialize storage with data directory."""
        self.data_dir = Path(data_dir)
        self.sessions_file = self.data_dir / "sessions.json"
        self.logs_dir = self.data_dir / "logs"
        self.worktrees_dir = self.data_dir / "worktrees"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.worktrees_dir.mkdir(exist_ok=True)
        if not self.sessions_file.exists():
            self.sessions_file.write_text("[]")

    @contextmanager
    def _lock_file(self):
        """File locking for concurrent access safety."""
        with open(self.sessions_file, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def save_session(self, session: AgentSession) -> None:
        """Save or update a session atomically."""
        with self._lock_file() as f:
            f.seek(0)
            content = f.read()
            sessions = json.loads(content) if content.strip() else []

            # Update or append
            updated = False
            for i, s in enumerate(sessions):
                if s["session_id"] == session.session_id:
                    sessions[i] = session.model_dump(mode="json")
                    updated = True
                    break

            if not updated:
                sessions.append(session.model_dump(mode="json"))

            # Atomic write
            f.seek(0)
            f.truncate()
            json.dump(sessions, f, indent=2, default=str)

    def load_session(self, session_id: str) -> Optional[AgentSession]:
        """Load session by ID (supports partial match)."""
        sessions = self.load_all_sessions()
        for s in sessions:
            if s.session_id.startswith(session_id):
                return s
        return None

    def load_all_sessions(self) -> list[AgentSession]:
        """Load all sessions."""
        try:
            with open(self.sessions_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []
                return [AgentSession(**s) for s in data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def delete_session(self, session_id: str) -> None:
        """Remove session from storage."""
        with self._lock_file() as f:
            f.seek(0)
            content = f.read()
            sessions = json.loads(content) if content.strip() else []
            sessions = [
                s for s in sessions if not s["session_id"].startswith(session_id)
            ]
            f.seek(0)
            f.truncate()
            json.dump(sessions, f, indent=2, default=str)

    def get_log_path(self, session_id: str) -> Path:
        """Get log file path for session."""
        return self.logs_dir / f"{session_id}.log"

    def get_worktree_path(self, session_id: str) -> Path:
        """Get worktree directory path for session."""
        return self.worktrees_dir / f"beehive-{session_id}"
