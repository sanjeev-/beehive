"""Configuration and system prompt management."""

from pathlib import Path
from typing import Optional


CLAUDE_MD_MARKER = "<!-- Beehive Agent Defaults -->"
CLAUDE_MD_PROJECT_MARKER = "<!-- Project CLAUDE.md -->"

AGENT_DELIVERABLE_INSTRUCTIONS = """
When you have completed the task:
1. git add -A && git commit -m "<descriptive message>"
2. git push -u origin HEAD
3. gh pr create --fill --base {base_branch}
4. Print the PR URL as the last line of output
These steps are MANDATORY. You must commit, push, and create a PR before finishing.
""".strip()

RESEARCH_DELIVERABLE_INSTRUCTIONS = """
When you have completed the experiment:
1. Save all results, logs, and artifacts to the working directory
2. Create a RESULTS.md summarizing findings, metrics, and observations
3. git add -A && git commit -m "<descriptive message>"
Do NOT create a PR or push. Just commit your results locally.
""".strip()


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

    def combine_prompts(
        self,
        user_instructions: str,
        base_branch: str = "main",
        include_deliverable: bool = False,
        plan_context: Optional[str] = None,
    ) -> str:
        """
        Combine global system prompt with user instructions.

        Format:
        ---
        [GLOBAL RULES - All agents must follow these]
        <system prompt content>

        ---
        [PLAN CONTEXT] (optional - for ordered plans)
        <previous/future ticket summaries>

        ---
        [TASK INSTRUCTIONS]
        <user instructions>

        ---
        [DELIVERABLE] (optional)
        <commit + PR instructions>
        """
        system_prompt = self.get_system_prompt()

        parts = []
        if system_prompt:
            parts.append(
                f"{'='*80}\n"
                f"GLOBAL RULES - All agents must follow these rules:\n"
                f"{'='*80}\n\n"
                f"{system_prompt}"
            )

        if plan_context:
            parts.append(
                f"{'='*80}\n"
                f"PLAN CONTEXT - Your task is part of an ordered plan:\n"
                f"{'='*80}\n\n"
                f"{plan_context}"
            )

        parts.append(
            f"{'='*80}\n"
            f"TASK INSTRUCTIONS:\n"
            f"{'='*80}\n\n"
            f"{user_instructions}"
        )

        if include_deliverable:
            deliverable = AGENT_DELIVERABLE_INSTRUCTIONS.format(
                base_branch=base_branch
            )
            parts.append(
                f"{'='*80}\n"
                f"DELIVERABLE - Complete these steps when done:\n"
                f"{'='*80}\n\n"
                f"{deliverable}"
            )

        return "\n\n".join(parts) + "\n"

    def combine_research_prompts(
        self,
        user_instructions: str,
        include_deliverable: bool = False,
    ) -> str:
        """
        Combine global system prompt with user instructions for research experiments.

        Same as combine_prompts() but uses RESEARCH_DELIVERABLE_INSTRUCTIONS
        (commit locally, no PR creation).
        """
        system_prompt = self.get_system_prompt()

        parts = []
        if system_prompt:
            parts.append(
                f"{'='*80}\n"
                f"GLOBAL RULES - All agents must follow these rules:\n"
                f"{'='*80}\n\n"
                f"{system_prompt}"
            )

        parts.append(
            f"{'='*80}\n"
            f"TASK INSTRUCTIONS:\n"
            f"{'='*80}\n\n"
            f"{user_instructions}"
        )

        if include_deliverable:
            parts.append(
                f"{'='*80}\n"
                f"DELIVERABLE - Complete these steps when done:\n"
                f"{'='*80}\n\n"
                f"{RESEARCH_DELIVERABLE_INSTRUCTIONS}"
            )

        return "\n\n".join(parts) + "\n"

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

    def inject_claude_md(
        self, worktree_path: Path, project_claude_md: Optional[str] = None
    ) -> bool:
        """Copy/prepend CLAUDE.md templates into a worktree.

        Layers (top to bottom in the resulting file):
          1. Global beehive defaults (~/.beehive/CLAUDE.md)
          2. Project-level CLAUDE.md (passed in)
          3. Repo-level CLAUDE.md (already in the worktree)

        Returns True if the file was written/modified, False otherwise.
        """
        global_template = self.get_claude_md()
        if not global_template and not project_claude_md:
            return False

        target = Path(worktree_path) / "CLAUDE.md"

        if target.exists():
            existing = target.read_text()
            # Already injected — idempotent no-op
            if CLAUDE_MD_MARKER in existing:
                return False
            # Build combined content: global > project > repo
            parts = []
            parts.append(CLAUDE_MD_MARKER)
            if global_template:
                parts.append(global_template)
            if project_claude_md:
                parts.append(f"\n---\n\n{CLAUDE_MD_PROJECT_MARKER}\n{project_claude_md}")
            parts.append(f"\n---\n\n{existing}")
            target.write_text("\n".join(parts))
        else:
            parts = [CLAUDE_MD_MARKER]
            if global_template:
                parts.append(global_template)
            if project_claude_md:
                parts.append(f"\n---\n\n{CLAUDE_MD_PROJECT_MARKER}\n{project_claude_md}")
            target.write_text("\n".join(parts) + "\n")

        return True
