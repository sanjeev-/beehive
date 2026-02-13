"""tmux session lifecycle management."""

import subprocess
import time
from pathlib import Path
from typing import Optional


class TmuxManager:
    """Manages tmux sessions for agent execution."""

    @staticmethod
    def check_tmux_installed() -> bool:
        """Verify tmux is available."""
        try:
            subprocess.run(["tmux", "-V"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def create_session(
        self,
        session_name: str,
        working_dir: Path,
        log_file: Path,
        instructions: str,
        initial_prompt: Optional[str] = None,
        auto_approve: bool = False,
    ) -> None:
        """
        Create a new tmux session running Claude Code.

        Steps:
        1. Create detached tmux session
        2. Enable logging via pipe-pane
        3. Send Claude Code command with instructions
        4. Optionally send initial prompt
        """
        # Create tmux session
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",  # detached
                "-s",
                session_name,
                "-c",
                str(working_dir),
            ],
            check=True,
        )

        # Enable pipe-pane for logging
        subprocess.run(
            [
                "tmux",
                "pipe-pane",
                "-o",  # append to file
                "-t",
                session_name,
                f"cat >> {log_file}",
            ],
            check=True,
        )

        # Start Claude Code with instructions
        # Unset CLAUDECODE to allow nested sessions, then escape quotes in instructions
        escaped_instructions = instructions.replace('"', '\\"').replace("$", "\\$")

        # Build command with optional auto-approve flag
        base_cmd = "unset CLAUDECODE && claude"
        if auto_approve:
            base_cmd += " --dangerously-skip-permissions"
        cmd = f'{base_cmd} --system-prompt "{escaped_instructions}"'

        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, cmd, "Enter"], check=True
        )

        # Send initial prompt if provided
        if initial_prompt:
            time.sleep(2)  # Wait for Claude to start
            # Escape quotes in prompt
            escaped_prompt = initial_prompt.replace('"', '\\"').replace("$", "\\$")
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, escaped_prompt, "Enter"],
                check=True,
            )

    def session_exists(self, session_name: str) -> bool:
        """Check if tmux session exists."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name], capture_output=True
        )
        return result.returncode == 0

    def attach_session(self, session_name: str) -> None:
        """Attach to tmux session (blocks until detach)."""
        subprocess.run(["tmux", "attach-session", "-t", session_name])

    def send_keys(self, session_name: str, keys: str) -> None:
        """Send keys/text to tmux session."""
        # Escape quotes
        escaped_keys = keys.replace('"', '\\"').replace("$", "\\$")
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, escaped_keys, "Enter"],
            check=True,
        )

    def kill_session(self, session_name: str) -> None:
        """Terminate tmux session."""
        if self.session_exists(session_name):
            subprocess.run(["tmux", "kill-session", "-t", session_name], check=True)

    def list_sessions(self) -> list[str]:
        """List all tmux sessions."""
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
        return []

    def capture_pane(self, session_name: str, last_n_lines: int = 50) -> str:
        """Capture current content from tmux pane."""
        result = subprocess.run(
            [
                "tmux",
                "capture-pane",
                "-t",
                session_name,
                "-p",  # print to stdout
                "-S",
                f"-{last_n_lines}",
            ],
            capture_output=True,
            text=True,
        )
        return result.stdout if result.returncode == 0 else ""
