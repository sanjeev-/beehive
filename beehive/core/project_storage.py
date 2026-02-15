"""Project persistence with file locking."""

import fcntl
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from beehive.core.project import CTOConversation, CTOMessage, CTOMessageRole, Project


class ProjectStorage:
    """Handles persistence of projects and CTO conversations."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.projects_file = self.projects_dir / "projects.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        if not self.projects_file.exists():
            self.projects_file.write_text("[]")

    def _project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def _conversation_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "conversation.json"

    @contextmanager
    def _lock_file(self, filepath: Path):
        with open(filepath, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # --- Project CRUD ---

    def save_project(self, project: Project) -> None:
        self._project_dir(project.project_id).mkdir(parents=True, exist_ok=True)

        with self._lock_file(self.projects_file) as f:
            f.seek(0)
            content = f.read()
            projects = json.loads(content) if content.strip() else []

            proj_data = project.model_dump(mode="json")

            updated = False
            for i, p in enumerate(projects):
                if p["project_id"] == project.project_id:
                    projects[i] = proj_data
                    updated = True
                    break

            if not updated:
                projects.append(proj_data)

            f.seek(0)
            f.truncate()
            json.dump(projects, f, indent=2, default=str)

    def load_project(self, project_id: str) -> Optional[Project]:
        projects = self.load_all_projects()
        for p in projects:
            if p.project_id.startswith(project_id):
                return p
        return None

    def load_all_projects(self) -> list[Project]:
        try:
            with open(self.projects_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []
            return [Project(**p) for p in data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def delete_project(self, project_id: str) -> None:
        project = self.load_project(project_id)
        if not project:
            return

        full_id = project.project_id

        with self._lock_file(self.projects_file) as f:
            f.seek(0)
            content = f.read()
            projects = json.loads(content) if content.strip() else []
            projects = [p for p in projects if p["project_id"] != full_id]
            f.seek(0)
            f.truncate()
            json.dump(projects, f, indent=2, default=str)

        import shutil

        proj_dir = self._project_dir(full_id)
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

    # --- Conversation CRUD ---

    def load_conversation(self, project_id: str) -> CTOConversation:
        conv_file = self._conversation_file(project_id)
        try:
            with open(conv_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else {}
            return CTOConversation(**data) if data else CTOConversation()
        except (FileNotFoundError, json.JSONDecodeError):
            return CTOConversation()

    def save_conversation(self, project_id: str, conversation: CTOConversation) -> None:
        self._project_dir(project_id).mkdir(parents=True, exist_ok=True)
        conv_file = self._conversation_file(project_id)
        conv_file.write_text(
            json.dumps(conversation.model_dump(mode="json"), indent=2, default=str)
        )

    def append_message(self, project_id: str, role: CTOMessageRole, content: str) -> None:
        conv = self.load_conversation(project_id)
        conv.messages.append(CTOMessage(role=role, content=content))
        conv.updated_at = datetime.utcnow()
        self.save_conversation(project_id, conv)

    def clear_conversation(self, project_id: str) -> None:
        self.save_conversation(project_id, CTOConversation())

    # --- Project CLAUDE.md ---

    def _claude_md_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "CLAUDE.md"

    def get_project_claude_md(self, project_id: str) -> Optional[str]:
        """Read the project-level CLAUDE.md. Returns None if missing or empty."""
        path = self._claude_md_file(project_id)
        if path.exists():
            content = path.read_text().strip()
            return content if content else None
        return None

    def set_project_claude_md(self, project_id: str, content: str) -> None:
        """Write the project-level CLAUDE.md."""
        self._project_dir(project_id).mkdir(parents=True, exist_ok=True)
        self._claude_md_file(project_id).write_text(content)

    def get_project_claude_md_path(self, project_id: str) -> Path:
        """Return the path to the project CLAUDE.md file."""
        return self._claude_md_file(project_id)
