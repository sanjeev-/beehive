"""Git operations wrapper."""

import re
import subprocess
from pathlib import Path
from typing import Optional


class GitOperations:
    """Git operations wrapper."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = Path(repo_path)

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run git command in repo."""
        return subprocess.run(
            ["git", "-C", str(self.repo_path)] + list(args),
            capture_output=True,
            text=True,
            check=check,
        )

    def is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        try:
            self._run_git("rev-parse", "--git-dir")
            return True
        except subprocess.CalledProcessError:
            return False

    def get_current_branch(self) -> str:
        """Get current branch name."""
        result = self._run_git("branch", "--show-current")
        return result.stdout.strip()

    def create_branch(self, branch_name: str, base_branch: str = "main") -> None:
        """Create and checkout new branch from base."""
        # First, try to fetch the base branch (don't fail if no remote)
        try:
            self._run_git("fetch", "origin", base_branch, check=False)
        except subprocess.CalledProcessError:
            pass  # No remote or fetch failed, continue anyway

        # Check if we should base off origin/base_branch or local base_branch
        result = self._run_git(
            "rev-parse", "--verify", f"origin/{base_branch}", check=False
        )
        if result.returncode == 0:
            base = f"origin/{base_branch}"
        else:
            # Fall back to local branch
            result = self._run_git("rev-parse", "--verify", base_branch, check=False)
            if result.returncode == 0:
                base = base_branch
            else:
                # Neither exists, just create from current HEAD
                base = "HEAD"

        # Create branch from base
        self._run_git("checkout", "-b", branch_name, base)

    def create_branch_from(self, branch_name: str, base: str) -> None:
        """Create a branch from base without checking it out (worktree-safe)."""
        self._run_git("fetch", "origin", base, check=False)
        # Prefer origin/<base> if it exists, otherwise fall back to local
        result = self._run_git(
            "rev-parse", "--verify", f"origin/{base}", check=False
        )
        if result.returncode == 0:
            base_ref = f"origin/{base}"
        else:
            base_ref = base
        self._run_git("branch", branch_name, base_ref)

    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists."""
        result = self._run_git("rev-parse", "--verify", branch_name, check=False)
        return result.returncode == 0

    def get_branch_commits_count(
        self, branch_name: str, base_branch: str = "main"
    ) -> int:
        """Count commits ahead of base branch."""
        result = self._run_git(
            "rev-list", "--count", f"{base_branch}..{branch_name}"
        )
        return int(result.stdout.strip())

    def has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes."""
        result = self._run_git("status", "--porcelain")
        return bool(result.stdout.strip())

    def get_diff_stat(
        self, branch_name: str, base_branch: str = "main"
    ) -> str:
        """Get diff statistics between branches."""
        result = self._run_git("diff", "--stat", f"{base_branch}...{branch_name}")
        return result.stdout

    def push_branch(self, branch_name: str) -> None:
        """Push branch to remote."""
        self._run_git("push", "-u", "origin", branch_name)

    def create_worktree(
        self, branch_name: str, worktree_path: Path, base_branch: str = "main"
    ) -> None:
        """
        Create a git worktree for isolated branch development.

        This creates a new working directory where the agent can work
        without affecting the main repository or other worktrees.
        """
        # Ensure worktree path is absolute
        worktree_path = Path(worktree_path).resolve()

        # First, try to fetch the base branch (don't fail if no remote)
        try:
            self._run_git("fetch", "origin", base_branch, check=False)
        except subprocess.CalledProcessError:
            pass  # No remote or fetch failed, continue anyway

        # Determine the base ref (prefer origin/base_branch if it exists)
        result = self._run_git(
            "rev-parse", "--verify", f"origin/{base_branch}", check=False
        )
        if result.returncode == 0:
            base = f"origin/{base_branch}"
        else:
            # Fall back to local branch
            result = self._run_git("rev-parse", "--verify", base_branch, check=False)
            if result.returncode == 0:
                base = base_branch
            else:
                # Neither exists, just create from current HEAD
                base = "HEAD"

        # Create worktree with new branch
        self._run_git(
            "worktree", "add", "-b", branch_name, str(worktree_path), base
        )

    def create_worktree_existing_branch(self, branch_name: str, worktree_path: Path) -> None:
        """Create a worktree for an existing branch (no -b flag)."""
        worktree_path = Path(worktree_path).resolve()
        self._run_git("fetch", "origin", branch_name, check=False)
        self._run_git("worktree", "add", str(worktree_path), branch_name)

    def clone_for_docker(
        self, branch_name: str, clone_path: Path, base_branch: str = "main"
    ) -> None:
        """Clone the repo into a standalone directory for Docker mounting.

        Git worktrees use absolute host paths in their .git file, which
        break inside containers.  A plain clone gives us a self-contained
        .git directory that works when mounted at any path.
        """
        clone_path = Path(clone_path).resolve()

        # Clone from local repo (fast, no network)
        subprocess.run(
            [
                "git", "clone",
                "--branch", base_branch,
                "--single-branch",
                str(self.repo_path),
                str(clone_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Set the remote to the original repo's remote (not the local path)
        result = self._run_git("remote", "get-url", "origin", check=False)
        if result.returncode == 0 and result.stdout.strip():
            remote_url = result.stdout.strip()
            subprocess.run(
                ["git", "-C", str(clone_path), "remote", "set-url", "origin", remote_url],
                capture_output=True,
                text=True,
                check=True,
            )

        # Create the feature branch
        subprocess.run(
            ["git", "-C", str(clone_path), "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            check=True,
        )

    def remove_worktree(self, worktree_path: Path, force: bool = False) -> None:
        """
        Remove a git worktree.

        Args:
            worktree_path: Path to the worktree to remove
            force: Force removal even if worktree has uncommitted changes
        """
        worktree_path = Path(worktree_path).resolve()
        args = ["worktree", "remove", str(worktree_path)]
        if force:
            args.append("--force")
        self._run_git(*args)

    def list_worktrees(self) -> list[dict]:
        """
        List all worktrees for this repository.

        Returns:
            List of dicts with 'worktree', 'branch', and 'commit' keys
        """
        result = self._run_git("worktree", "list", "--porcelain")
        worktrees = []
        current_worktree = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current_worktree:
                    worktrees.append(current_worktree)
                    current_worktree = {}
                continue

            if line.startswith("worktree "):
                current_worktree["worktree"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current_worktree["branch"] = line.split(" ", 1)[1]
            elif line.startswith("HEAD "):
                current_worktree["commit"] = line.split(" ", 1)[1]

        if current_worktree:
            worktrees.append(current_worktree)

        return worktrees

    def worktree_exists(self, worktree_path: Path) -> bool:
        """Check if a worktree exists at the given path."""
        worktree_path = Path(worktree_path).resolve()
        worktrees = self.list_worktrees()
        return any(Path(w["worktree"]) == worktree_path for w in worktrees)


def generate_branch_name(session_name: str, session_id: str) -> str:
    """Generate branch name: beehive/<sanitized-name>-<id>"""
    # Sanitize session name: lowercase, replace non-alphanumeric with dashes
    sanitized = re.sub(r"[^a-z0-9-]", "-", session_name.lower())
    # Remove consecutive dashes and trim
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    # Limit length to avoid overly long branch names
    sanitized = sanitized[:50]
    return f"beehive/{sanitized}-{session_id}"
