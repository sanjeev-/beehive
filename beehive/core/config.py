"""Configuration and system prompt management."""

from pathlib import Path
from typing import Optional


CLAUDE_MD_MARKER = "<!-- Beehive Agent Defaults -->"
CLAUDE_MD_PROJECT_MARKER = "<!-- Project CLAUDE.md -->"


class BeehiveConfig:
    """Manages Beehive configuration including global system prompts."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.system_prompt_file = self.data_dir / "system_prompt.txt"
        self.config_file = self.data_dir / "config.json"
        self.claude_md_file = self.data_dir / "CLAUDE.md"

    def get_system_prompt(self) -> Optional[str]:
        """
        Load the global system prompt that applies to all agents.

        This file contains rules and guidelines that every agent must follow.
        It's prepended to user-provided instructions.
        """
        if self.system_prompt_file.exists():
            return self.system_prompt_file.read_text().strip()
        return None

    def set_system_prompt(self, prompt: str) -> None:
        """Set the global system prompt."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt_file.write_text(prompt)

    def get_system_prompt_path(self) -> Path:
        """Get the path to the system prompt file for editing."""
        return self.system_prompt_file

    def combine_prompts(self, user_instructions: str) -> str:
        """
        Combine global system prompt with user instructions.

        Format:
        ---
        [GLOBAL RULES - All agents must follow these]
        <system prompt content>

        ---
        [TASK INSTRUCTIONS]
        <user instructions>
        """
        system_prompt = self.get_system_prompt()
        if not system_prompt:
            return user_instructions

        combined = f"""{'='*80}
GLOBAL RULES - All agents must follow these rules:
{'='*80}

{system_prompt}

{'='*80}
TASK INSTRUCTIONS:
{'='*80}

{user_instructions}
"""
        return combined

    def get_claude_md(self) -> Optional[str]:
        """Read the default CLAUDE.md template. Returns None if missing or empty."""
        if self.claude_md_file.exists():
            content = self.claude_md_file.read_text().strip()
            return content if content else None
        return None

    def set_claude_md(self, content: str) -> None:
        """Write the default CLAUDE.md template."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.claude_md_file.write_text(content)

    def get_claude_md_path(self) -> Path:
        """Return the path to the CLAUDE.md template file."""
        return self.claude_md_file

    def inject_claude_md(self, worktree_path: Path) -> bool:
        """Copy/prepend the default CLAUDE.md template into a worktree.

        Returns True if the file was written/modified, False otherwise.
        """
        template = self.get_claude_md()
        if not template:
            return False

        target = Path(worktree_path) / "CLAUDE.md"

        if target.exists():
            existing = target.read_text()
            # Already injected — idempotent no-op
            if CLAUDE_MD_MARKER in existing:
                return False
            # Prepend beehive defaults above existing content
            combined = (
                f"{CLAUDE_MD_MARKER}\n{template}\n\n---\n\n"
                f"{CLAUDE_MD_PROJECT_MARKER}\n{existing}"
            )
            target.write_text(combined)
        else:
            target.write_text(f"{CLAUDE_MD_MARKER}\n{template}\n")

        return True
