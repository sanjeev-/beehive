"""Plan generation using Claude API via Anthropic SDK."""

import json
import uuid
from datetime import datetime

import anthropic

from beehive.core.architect import Architect, Plan, Ticket


class Planner:
    """Generates plans by calling Claude to break directives into tickets."""

    def __init__(self, architect: Architect):
        self.architect = architect

    def _build_system_prompt(self) -> str:
        """Build system prompt with architect context."""
        repo_descriptions = "\n".join(
            f"  - {r.name}: {r.description} (base branch: {r.base_branch})"
            for r in self.architect.repos
        )

        return f"""You are a software architect planning work across repositories.

## Principles
{self.architect.principles}

## Available Repositories
{repo_descriptions}

## Constraints
- Each ticket MUST target exactly ONE repository from the list above.
- Each ticket should result in exactly one PR.
- Tickets should be small, focused, and independently completable.
- The "repo" field must match one of the repository names exactly.

## Output Format
Respond with ONLY a JSON array of tickets. No other text.
Each ticket must have these fields:
- "title": short descriptive title
- "description": detailed work description that an AI coding agent can follow
- "repo": repository name (must match one of the available repos exactly)

Example:
[
  {{
    "title": "Add user profile endpoint",
    "description": "Create a new GET /api/users/:id/profile endpoint that returns...",
    "repo": "api"
  }}
]"""

    def generate_plan(self, directive: str) -> Plan:
        """Call Claude API to break directive into tickets."""
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self._build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": f"Break this directive into tickets:\n\n{directive}",
                }
            ],
        )

        # Extract text from response
        raw_text = response.content[0].text.strip()

        # Parse JSON — handle markdown code blocks if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            # Remove first and last lines (``` markers)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_text = "\n".join(lines)

        ticket_data = json.loads(raw_text)

        # Validate repo names
        valid_repos = {r.name for r in self.architect.repos}
        now = datetime.utcnow()

        tickets = []
        for idx, t in enumerate(ticket_data):
            if t["repo"] not in valid_repos:
                raise ValueError(
                    f"Ticket '{t['title']}' targets unknown repo '{t['repo']}'. "
                    f"Valid repos: {', '.join(valid_repos)}"
                )
            tickets.append(
                Ticket(
                    ticket_id=str(uuid.uuid4())[:8],
                    title=t["title"],
                    description=t["description"],
                    repo=t["repo"],
                    order=idx + 1,
                    created_at=now,
                    updated_at=now,
                )
            )

        plan = Plan(
            plan_id=str(uuid.uuid4())[:8],
            directive=directive,
            tickets=tickets,
            created_at=now,
            updated_at=now,
        )

        return plan
