"""Preview environment manager for per-project dev servers."""

import fcntl
import json
import os
import re
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class PreviewState(BaseModel):
    session_id: str
    port: int
    pid: int
    url: str
    working_directory: str
    setup_command: str
    teardown_command: str = ""


class PreviewManager:
    """Manages preview environment lifecycle: start, stop, track."""

    PORT_MIN = 3100
    PORT_MAX = 3199

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "preview_state.json"
        self.logs_dir = self.data_dir / "logs"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self.state_file.write_text("[]")

    @contextmanager
    def _lock_file(self, filepath: Path):
        with open(filepath, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load_states(self) -> list[PreviewState]:
        try:
            with open(self.state_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []
            return [PreviewState(**s) for s in data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_states(self, states: list[PreviewState], f) -> None:
        f.seek(0)
        f.truncate()
        json.dump([s.model_dump() for s in states], f, indent=2)

    def _allocate_port(self, states: list[PreviewState]) -> int:
        used_ports = {s.port for s in states}
        for port in range(self.PORT_MIN, self.PORT_MAX + 1):
            if port not in used_ports:
                return port
        raise RuntimeError(
            f"No available ports in range {self.PORT_MIN}-{self.PORT_MAX}"
        )

    @staticmethod
    def sanitize_task_name(name: str) -> str:
        """Lowercase, alphanum+hyphens, max 63 chars."""
        sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower())
        sanitized = re.sub(r"-+", "-", sanitized).strip("-")
        return sanitized[:63]

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def start_preview(
        self,
        session_id: str,
        task_name: str,
        working_directory: str,
        setup_command: str,
        teardown_command: str = "",
        url_template: str = "http://{task_name}.localhost:{port}",
        startup_timeout: int = 30,
    ) -> str:
        """Start a preview server and return the preview URL."""
        sanitized_name = self.sanitize_task_name(task_name)

        with self._lock_file(self.state_file) as f:
            f.seek(0)
            content = f.read()
            states = [
                PreviewState(**s)
                for s in (json.loads(content) if content.strip() else [])
            ]

            # Check if session already has a preview
            for s in states:
                if s.session_id == session_id:
                    return s.url

            port = self._allocate_port(states)
            url = url_template.format(task_name=sanitized_name, port=port)

            # Set up environment
            backend_port = port + 1000
            env = os.environ.copy()
            env["BEEHIVE_PORT"] = str(port)
            env["BEEHIVE_BACKEND_PORT"] = str(backend_port)
            env["BEEHIVE_TASK_NAME"] = sanitized_name
            env["BEEHIVE_SESSION_ID"] = session_id

            # Open log file
            log_file = self.logs_dir / f"preview-{session_id}.log"
            log_fh = open(log_file, "w")

            # Start process in its own process group
            proc = subprocess.Popen(
                setup_command,
                shell=True,
                cwd=working_directory,
                env=env,
                stdout=log_fh,
                stderr=log_fh,
                preexec_fn=os.setsid,
            )

            state = PreviewState(
                session_id=session_id,
                port=port,
                pid=proc.pid,
                url=url,
                working_directory=working_directory,
                setup_command=setup_command,
                teardown_command=teardown_command,
            )
            states.append(state)
            self._save_states(states, f)

        return url

    def stop_preview(self, session_id: str) -> bool:
        """Stop a preview by session ID. Returns True if found and stopped."""
        with self._lock_file(self.state_file) as f:
            f.seek(0)
            content = f.read()
            states = [
                PreviewState(**s)
                for s in (json.loads(content) if content.strip() else [])
            ]

            target = None
            remaining = []
            for s in states:
                if s.session_id == session_id:
                    target = s
                else:
                    remaining.append(s)

            if not target:
                return False

            # Run teardown command if specified
            if target.teardown_command:
                try:
                    subprocess.run(
                        target.teardown_command,
                        shell=True,
                        cwd=target.working_directory,
                        timeout=10,
                        capture_output=True,
                    )
                except Exception:
                    pass

            # Kill the process group
            if self._is_process_alive(target.pid):
                try:
                    os.killpg(os.getpgid(target.pid), signal.SIGTERM)
                except OSError:
                    try:
                        os.kill(target.pid, signal.SIGKILL)
                    except OSError:
                        pass

            self._save_states(remaining, f)
            return True

    def get_preview(self, session_id: str) -> Optional[PreviewState]:
        """Get preview state for a session."""
        states = self._load_states()
        for s in states:
            if s.session_id == session_id:
                return s
        return None

    def list_previews(self) -> list[PreviewState]:
        """List all tracked previews."""
        return self._load_states()

    def cleanup_dead_previews(self) -> int:
        """Remove stale entries for dead processes. Returns count removed."""
        with self._lock_file(self.state_file) as f:
            f.seek(0)
            content = f.read()
            states = [
                PreviewState(**s)
                for s in (json.loads(content) if content.strip() else [])
            ]

            alive = []
            removed = 0
            for s in states:
                if self._is_process_alive(s.pid):
                    alive.append(s)
                else:
                    removed += 1

            if removed > 0:
                self._save_states(alive, f)

        return removed
