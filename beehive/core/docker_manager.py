"""Docker container management for isolated agent execution."""

import subprocess
from pathlib import Path


class DockerManager:
    """Manages Docker containers for running agents in isolation."""

    IMAGE_NAME = "beehive-agent"

    def is_available(self) -> bool:
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def ensure_image(self) -> bool:
        """Build the beehive-agent image from .devcontainer/Dockerfile if it doesn't exist.

        Returns True if image is ready, False on failure.
        """
        # Check if image already exists
        result = subprocess.run(
            ["docker", "image", "inspect", self.IMAGE_NAME],
            capture_output=True,
        )
        if result.returncode == 0:
            return True

        # Build from .devcontainer/Dockerfile
        dockerfile_dir = Path(__file__).resolve().parent.parent.parent / ".devcontainer"
        if not (dockerfile_dir / "Dockerfile").exists():
            return False

        result = subprocess.run(
            [
                "docker", "build",
                "-t", self.IMAGE_NAME,
                "-f", str(dockerfile_dir / "Dockerfile"),
                str(dockerfile_dir),
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def build_run_command(
        self,
        session_id: str,
        worktree_path: Path,
        claude_cmd: str,
    ) -> str:
        """Build the full `docker run` command string.

        The claude_cmd should use $(cat ...) references to read prompts
        from files in /workspace, keeping it short and quoting-safe.
        """
        home = Path.home()
        parts = [
            "docker", "run", "--rm", "-t",
            f"--name beehive-{session_id}",
            "--cap-add=NET_ADMIN",
            "-e ANTHROPIC_API_KEY",
            f"-v {worktree_path}:/workspace",
        ]

        # Mount prepared gitconfig (writable so gh/git can extend it)
        gitconfig = worktree_path / ".beehive-gitconfig"
        if gitconfig.exists():
            parts.append(f"-v {gitconfig}:/home/node/.gitconfig")

        # Conditionally mount other host configs (read-only)
        optional_mounts = [
            (home / ".ssh", "/home/node/.ssh"),
            (home / ".config" / "gh", "/home/node/.config/gh"),
        ]
        for src, dest in optional_mounts:
            if src.exists():
                parts.append(f"-v {src}:{dest}:ro")

        # Single quotes prevent host-shell interpretation; the inner
        # bash expands $(cat ...) to read prompt files from /workspace.
        # gh auth setup-git: configures git credential helper for HTTPS push
        # url rewrite: converts SSH remote URLs to HTTPS (gh handles auth)
        inner = (
            "sudo /usr/local/bin/init-firewall.sh >/dev/null 2>&1;"
            " gh auth setup-git 2>/dev/null || true;"
            ' git config --global url.https://github.com/.insteadOf git@github.com: 2>/dev/null || true;'
            f" {claude_cmd}"
        )

        parts.extend([
            "-w /workspace",
            self.IMAGE_NAME,
            "bash", "-c",
            f"'{inner}'",
        ])

        return " ".join(parts)

    def stop_container(self, session_id: str) -> bool:
        """Stop a running container. Returns True if stopped successfully."""
        container_name = f"beehive-{session_id}"
        result = subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0

    def container_running(self, session_id: str) -> bool:
        """Check if a container is currently running."""
        container_name = f"beehive-{session_id}"
        result = subprocess.run(
            [
                "docker", "inspect",
                "--format", "{{.State.Running}}",
                container_name,
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
