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

    @staticmethod
    def _build_claude_command(
        prompt_dir: str,
        has_initial_prompt: bool = False,
        auto_approve: bool = False,
    ) -> str:
        """Build the claude CLI command string.

        Reads the system prompt (and optional initial prompt) from files
        in prompt_dir, keeping the command short and free of quoting issues.
        Files expected: .beehive-system-prompt.txt, .beehive-prompt.txt
        """
        base_cmd = "unset CLAUDECODE && claude"
        if auto_approve:
            base_cmd += " --dangerously-skip-permissions"
            base_cmd += " -p"

        prompt_file = f"{prompt_dir}/.beehive-system-prompt.txt"
        cmd = f'{base_cmd} --system-prompt "$(cat {prompt_file})"'

        if auto_approve and has_initial_prompt:
            initial_file = f"{prompt_dir}/.beehive-prompt.txt"
            cmd += f' "$(cat {initial_file})"'
        elif auto_approve:
            cmd += ' "Execute the instructions in the system prompt."'

        return cmd

    def create_session(
        self,
        session_name: str,
        working_dir: Path,
        log_file: Path,
        prompt_dir: str,
        initial_prompt: Optional[str] = None,
        auto_approve: bool = False,
        docker_command: Optional[str] = None,
    ) -> None:
        """
        Create a new tmux session running Claude Code.

        Args:
            prompt_dir: Directory containing .beehive-system-prompt.txt
                        (and optionally .beehive-prompt.txt). For host mode
                        this is the worktree path; for docker mode it is
                        unused since docker_command is pre-built.

        Steps:
        1. Create detached tmux session
        2. Enable logging via pipe-pane
        3. Send Claude Code command (or docker_command)
        4. Optionally send initial prompt (interactive host mode only)
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

        if docker_command:
            # Docker mode: send the pre-built docker run command
            cmd = docker_command
        else:
            # Host mode: build the claude command from prompt files
            cmd = self._build_claude_command(
                prompt_dir,
                has_initial_prompt=bool(auto_approve and initial_prompt),
                auto_approve=auto_approve,
            )

        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, cmd, "Enter"], check=True
        )

        # Send initial prompt if provided (interactive host mode only)
        if not docker_command and not auto_approve and initial_prompt:
            time.sleep(2)  # Wait for Claude to start
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
