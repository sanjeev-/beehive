"""CTO AI logic — conversational advisor for projects."""

from datetime import datetime

from beehive.core.architect_storage import ArchitectStorage
from beehive.core.project import CTOMessageRole, Project
from beehive.core.project_storage import ProjectStorage
from beehive.core.session import SessionManager


class CTO:
    """AI-powered CTO that advises on project strategy."""

    def __init__(
        self,
        project: Project,
        project_storage: ProjectStorage,
        architect_storage: ArchitectStorage,
        session_manager: SessionManager,
    ):
        self.project = project
        self.project_storage = project_storage
        self.architect_storage = architect_storage
        self.session_manager = session_manager

    def chat(self, user_message: str) -> str:
        """Send a message and get a response, maintaining conversation history."""
        # Save user message
        self.project_storage.append_message(
            self.project.project_id, CTOMessageRole.USER, user_message
        )

        # Build messages from conversation history
        conv = self.project_storage.load_conversation(self.project.project_id)
        messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in conv.messages
        ]

        # Call Claude
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self._build_system_prompt(),
            messages=messages,
        )

        assistant_text = response.content[0].text

        # Save assistant response
        self.project_storage.append_message(
            self.project.project_id, CTOMessageRole.ASSISTANT, assistant_text
        )

        return assistant_text

    def brief(self) -> tuple[str, str]:
        """Generate a project brief: (raw_data, ai_summary)."""
        raw_data = self._build_project_context()

        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=(
                "You are a CTO reviewing project status. "
                "Provide a concise strategic summary: what's going well, "
                "what needs attention, and recommended next steps. "
                "Be direct and actionable."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Here is the current project state:\n\n{raw_data}",
                }
            ],
        )

        ai_summary = response.content[0].text
        return raw_data, ai_summary

    def _build_system_prompt(self) -> str:
        """Build system prompt with full project context. Rebuilt each call."""
        context = self._build_project_context()

        return f"""You are the CTO for the "{self.project.name}" project. You are a strategic technical advisor.

## Your Role
- Advise on architecture, priorities, and technical strategy
- Help break down complex problems into actionable work
- Review and suggest improvements to plans and tickets
- Never act directly — only advise and suggest
- When suggesting a new architect configuration, output a YAML config block that can be saved and used with `beehive architect create`

## Project Context
{context}

## Design Principles
{self.project.design_principles or "Not specified."}

## Engineering Principles
{self.project.engineering_principles or "Not specified."}

Be concise, direct, and actionable. Reference specific repos, architects, and tickets when relevant."""

    def _build_project_context(self) -> str:
        """Gather full project state: repos, architects, plans, tickets, sessions."""
        lines = []

        # Project info
        lines.append(f"Project: {self.project.name}")
        if self.project.description:
            lines.append(f"Description: {self.project.description}")
        lines.append("")

        # Repos
        lines.append("## Repositories")
        if self.project.repos:
            for r in self.project.repos:
                desc = f" — {r.description}" if r.description else ""
                lines.append(f"  - {r.name}: {r.path} (base: {r.base_branch}){desc}")
        else:
            lines.append("  No repos configured.")
        lines.append("")

        # Linked architects
        lines.append("## Linked Architects")
        architects = []
        for arch_id in self.project.architect_ids:
            arch = self.architect_storage.load_architect(arch_id)
            if arch:
                architects.append(arch)

        if not architects:
            lines.append("  No architects linked.")
        else:
            for arch in architects:
                lines.append(f"  ### {arch.name} ({arch.architect_id})")
                lines.append(f"  Repos: {', '.join(r.name for r in arch.repos)}")
                lines.append(f"  Plans: {len(arch.plans)}")
                for plan in arch.plans:
                    total = len(plan.tickets)
                    done = sum(1 for t in plan.tickets if t.status == "completed")
                    failed = sum(1 for t in plan.tickets if t.status == "failed")
                    pending = sum(1 for t in plan.tickets if t.status == "pending")
                    lines.append(
                        f"    Plan {plan.plan_id}: {plan.directive[:60]}"
                    )
                    lines.append(
                        f"      {total} tickets: {done} done, {failed} failed, {pending} pending"
                    )
                    for t in plan.tickets:
                        lines.append(
                            f"      - [{t.status}] {t.title} ({t.repo})"
                            + (f" PR: {t.pr_url}" if t.pr_url else "")
                        )
                lines.append("")

        # Active sessions
        lines.append("## Active Sessions")
        sessions = self.session_manager.list_sessions()
        running = [s for s in sessions if s.status == "running"]
        if running:
            for s in running:
                lines.append(f"  - {s.name} ({s.session_id}): {s.status} on {s.branch_name}")
        else:
            lines.append("  No running sessions.")

        return "\n".join(lines)
