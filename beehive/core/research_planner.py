"""Research study generation using Claude API via Anthropic SDK."""

import json
import uuid
from datetime import datetime

import anthropic

from beehive.core.researcher import Experiment, Researcher, Study


class ResearchPlanner:
    """Generates studies by calling Claude to break directives into experiments."""

    def __init__(self, researcher: Researcher):
        self.researcher = researcher

    def _build_system_prompt(self) -> str:
        """Build system prompt with researcher context."""
        repo_descriptions = "\n".join(
            f"  - {r.name}: {r.description} (base branch: {r.base_branch})"
            for r in self.researcher.repos
        )

        return f"""You are a research scientist planning experiments across repositories.

## Principles
{self.researcher.principles}

## Available Repositories
{repo_descriptions}

## Constraints
- Each experiment MUST target exactly ONE repository from the list above.
- Each experiment should produce reports, artifacts, W&B logs, or other research outputs.
- Experiments should be focused and independently runnable.
- The "repo" field must match one of the repository names exactly.
- Results should be saved to the working directory (RESULTS.md, logs, code, training runs, dataset samples).

## Output Format
Respond with ONLY a JSON array of experiments. No other text.
Each experiment must have these fields:
- "title": short descriptive title
- "description": detailed experiment description that an AI coding agent can follow
- "repo": repository name (must match one of the available repos exactly)

Example:
[
  {{
    "title": "Benchmark attention variants on CIFAR-10",
    "description": "Run training with standard, linear, and flash attention on CIFAR-10. Log metrics to W&B. Save results to RESULTS.md with accuracy/throughput tables.",
    "repo": "ml-experiments"
  }}
]"""

    def generate_study(self, directive: str) -> Study:
        """Call Claude API to break directive into experiments."""
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self._build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": f"Break this research directive into experiments:\n\n{directive}",
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

        experiment_data = json.loads(raw_text)

        # Validate repo names
        valid_repos = {r.name for r in self.researcher.repos}
        now = datetime.utcnow()

        experiments = []
        for e in experiment_data:
            if e["repo"] not in valid_repos:
                raise ValueError(
                    f"Experiment '{e['title']}' targets unknown repo '{e['repo']}'. "
                    f"Valid repos: {', '.join(valid_repos)}"
                )
            experiments.append(
                Experiment(
                    experiment_id=str(uuid.uuid4())[:8],
                    title=e["title"],
                    description=e["description"],
                    repo=e["repo"],
                    created_at=now,
                    updated_at=now,
                )
            )

        study = Study(
            study_id=str(uuid.uuid4())[:8],
            directive=directive,
            experiments=experiments,
            created_at=now,
            updated_at=now,
        )

        return study
