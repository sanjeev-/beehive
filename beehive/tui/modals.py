"""Modal dialogs for Beehive TUI CRUD operations."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from beehive.core.architect import Architect, ArchitectRepo, Ticket, TicketStatus
from beehive.core.researcher import Experiment, ExperimentStatus, Researcher


# ─── Confirm modal ──────────────────────────────────────────────────────────


class ConfirmModal(ModalScreen[bool]):
    """Generic yes/no confirmation dialog."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, message: str, **kw):
        super().__init__(**kw)
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (y)", variant="warning", id="confirm-yes")
                yield Button("No (n)", variant="default", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ─── Send prompt modal ─────────────────────────────────────────────────────


class SendPromptModal(ModalScreen[str | None]):
    """Multi-line text input for sending a prompt to an agent."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, agent_name: str, **kw):
        super().__init__(**kw)
        self._agent_name = agent_name

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-dialog"):
            yield Static(
                f"[bold #333]Send prompt to {self._agent_name}[/]",
                id="prompt-title",
            )
            yield TextArea(id="prompt-input")
            with Horizontal(id="prompt-buttons"):
                yield Button("Send", variant="warning", id="prompt-send")
                yield Button("Cancel", variant="default", id="prompt-cancel")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-send":
            text = self.query_one("#prompt-input", TextArea).text.strip()
            self.dismiss(text if text else None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Link architect modal ──────────────────────────────────────────────────


class LinkArchitectModal(ModalScreen[str | None]):
    """Select an unlinked architect to link to a project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, project_name: str, choices: list[tuple[str, str]], **kw):
        """choices: list of (architect_id, display_name)"""
        super().__init__(**kw)
        self._project_name = project_name
        self._choices = choices

    def compose(self) -> ComposeResult:
        with Vertical(id="link-dialog"):
            yield Static(
                f"[bold #333]Link architect to {self._project_name}[/]",
                id="link-title",
            )
            yield Select(
                [(name, aid) for aid, name in self._choices],
                prompt="Select architect",
                id="link-select",
            )
            with Horizontal(id="link-buttons"):
                yield Button("Link", variant="warning", id="link-confirm")
                yield Button("Cancel", variant="default", id="link-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "link-confirm":
            select = self.query_one("#link-select", Select)
            value = select.value
            self.dismiss(value if value != Select.BLANK else None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Unlink architect modal ────────────────────────────────────────────────


class UnlinkArchitectModal(ModalScreen[str | None]):
    """Select a linked architect to unlink from a project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, project_name: str, choices: list[tuple[str, str]], **kw):
        """choices: list of (architect_id, display_name)"""
        super().__init__(**kw)
        self._project_name = project_name
        self._choices = choices

    def compose(self) -> ComposeResult:
        with Vertical(id="unlink-dialog"):
            yield Static(
                f"[bold #333]Unlink architect from {self._project_name}[/]",
                id="unlink-title",
            )
            yield Select(
                [(name, aid) for aid, name in self._choices],
                prompt="Select architect",
                id="unlink-select",
            )
            with Horizontal(id="unlink-buttons"):
                yield Button("Unlink", variant="error", id="unlink-confirm")
                yield Button("Cancel", variant="default", id="unlink-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "unlink-confirm":
            select = self.query_one("#unlink-select", Select)
            value = select.value
            self.dismiss(value if value != Select.BLANK else None)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Create architect modal ──────────────────────────────────────────────


class CreateArchitectModal(ModalScreen[dict | None]):
    """Create a new architect with repos."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._repos: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="create-arch-dialog"):
            yield Static("[bold #333]Create Architect[/]", id="create-arch-title")
            yield Label("Name")
            yield Input(placeholder="Architect name", id="arch-name-input")
            yield Label("Principles")
            yield TextArea(id="arch-principles-input")
            yield Static("[bold #555]Add Repo[/]", id="add-repo-heading")
            yield Label("Repo Name")
            yield Input(placeholder="e.g. my-service", id="repo-name-input")
            yield Label("Repo Path")
            yield Input(placeholder="/path/to/repo", id="repo-path-input")
            yield Label("Base Branch")
            yield Input(value="main", placeholder="main", id="repo-branch-input")
            with Horizontal(id="add-repo-buttons"):
                yield Button("Add repo", variant="default", id="add-repo-btn")
            yield Static("", id="repo-list-display")
            with Horizontal(id="create-arch-buttons"):
                yield Button("Create", variant="warning", id="create-arch-confirm")
                yield Button("Cancel", variant="default", id="create-arch-cancel")

    def on_mount(self) -> None:
        self.query_one("#arch-name-input", Input).focus()

    def _update_repo_list(self) -> None:
        if self._repos:
            lines = [f"  [#555]{r['name']}[/] — {r['path']} ({r['base_branch']})" for r in self._repos]
            self.query_one("#repo-list-display", Static).update(
                "[#888]Repos:[/]\n" + "\n".join(lines)
            )
        else:
            self.query_one("#repo-list-display", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-repo-btn":
            name = self.query_one("#repo-name-input", Input).value.strip()
            path = self.query_one("#repo-path-input", Input).value.strip()
            branch = self.query_one("#repo-branch-input", Input).value.strip() or "main"
            if name and path:
                self._repos.append({"name": name, "path": path, "base_branch": branch})
                self.query_one("#repo-name-input", Input).value = ""
                self.query_one("#repo-path-input", Input).value = ""
                self.query_one("#repo-branch-input", Input).value = "main"
                self._update_repo_list()
        elif event.button.id == "create-arch-confirm":
            name = self.query_one("#arch-name-input", Input).value.strip()
            principles = self.query_one("#arch-principles-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({"name": name, "principles": principles, "repos": self._repos})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Edit architect modal ────────────────────────────────────────────────


class EditArchitectModal(ModalScreen[dict | None]):
    """Edit an existing architect's name and principles."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, architect: Architect, **kw):
        super().__init__(**kw)
        self._architect = architect

    def compose(self) -> ComposeResult:
        a = self._architect
        with Vertical(id="edit-arch-dialog"):
            yield Static("[bold #333]Edit Architect[/]", id="edit-arch-title")
            yield Label("Name")
            yield Input(value=a.name, id="edit-arch-name-input")
            yield Label("Principles")
            yield TextArea(a.principles, id="edit-arch-principles-input")
            if a.repos:
                repo_lines = "\n".join(
                    f"  [#555]{r.name}[/] — {r.path} ({r.base_branch})" for r in a.repos
                )
                yield Static(f"[#888]Repos (read-only):[/]\n{repo_lines}", id="edit-arch-repos")
            with Horizontal(id="edit-arch-buttons"):
                yield Button("Save", variant="warning", id="edit-arch-save")
                yield Button("Cancel", variant="default", id="edit-arch-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-arch-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-arch-save":
            name = self.query_one("#edit-arch-name-input", Input).value.strip()
            principles = self.query_one("#edit-arch-principles-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({"name": name, "principles": principles})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Edit ticket modal ───────────────────────────────────────────────────


class EditTicketModal(ModalScreen[dict | None]):
    """Edit a ticket's title, description, and status."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, ticket: Ticket, **kw):
        super().__init__(**kw)
        self._ticket = ticket

    def compose(self) -> ComposeResult:
        t = self._ticket
        status_choices = [(s.value, s.value) for s in TicketStatus]
        with Vertical(id="edit-ticket-dialog"):
            yield Static("[bold #333]Edit Ticket[/]", id="edit-ticket-title")
            yield Label("Title")
            yield Input(value=t.title, id="edit-ticket-title-input")
            yield Label("Description")
            yield TextArea(t.description, id="edit-ticket-desc-input")
            yield Label("Status")
            yield Select(
                status_choices,
                value=str(t.status),
                id="edit-ticket-status-select",
            )
            with Horizontal(id="edit-ticket-buttons"):
                yield Button("Save", variant="warning", id="edit-ticket-save")
                yield Button("Cancel", variant="default", id="edit-ticket-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-ticket-title-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-ticket-save":
            title = self.query_one("#edit-ticket-title-input", Input).value.strip()
            description = self.query_one("#edit-ticket-desc-input", TextArea).text.strip()
            select = self.query_one("#edit-ticket-status-select", Select)
            status = select.value
            if not title:
                self.app.notify("Title is required", severity="warning")
                return
            self.dismiss({"title": title, "description": description, "status": status})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Create project modal ────────────────────────────────────────────────


class CreateProjectModal(ModalScreen[dict | None]):
    """Create a new project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="create-project-dialog"):
            yield Static("[bold #333]Create Project[/]", id="create-project-title")
            yield Label("Name")
            yield Input(placeholder="Project name", id="project-name-input")
            yield Label("Description")
            yield TextArea(id="project-desc-input")
            yield Label("Design Principles")
            yield TextArea(id="project-design-input")
            yield Label("Engineering Principles")
            yield TextArea(id="project-eng-input")
            with Horizontal(id="create-project-buttons"):
                yield Button("Create", variant="warning", id="create-project-confirm")
                yield Button("Cancel", variant="default", id="create-project-cancel")

    def on_mount(self) -> None:
        self.query_one("#project-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-project-confirm":
            name = self.query_one("#project-name-input", Input).value.strip()
            description = self.query_one("#project-desc-input", TextArea).text.strip()
            design = self.query_one("#project-design-input", TextArea).text.strip()
            engineering = self.query_one("#project-eng-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({
                "name": name,
                "description": description,
                "design_principles": design,
                "engineering_principles": engineering,
            })
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Edit project modal ──────────────────────────────────────────────────


class EditProjectModal(ModalScreen[dict | None]):
    """Edit an existing project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, project, **kw):
        super().__init__(**kw)
        self._project = project

    def compose(self) -> ComposeResult:
        p = self._project
        with Vertical(id="edit-project-dialog"):
            yield Static("[bold #333]Edit Project[/]", id="edit-project-title")
            yield Label("Name")
            yield Input(value=p.name, id="edit-project-name-input")
            yield Label("Description")
            yield TextArea(p.description, id="edit-project-desc-input")
            yield Label("Design Principles")
            yield TextArea(p.design_principles, id="edit-project-design-input")
            yield Label("Engineering Principles")
            yield TextArea(p.engineering_principles, id="edit-project-eng-input")
            with Horizontal(id="edit-project-buttons"):
                yield Button("Save", variant="warning", id="edit-project-save")
                yield Button("Cancel", variant="default", id="edit-project-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-project-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-project-save":
            name = self.query_one("#edit-project-name-input", Input).value.strip()
            description = self.query_one("#edit-project-desc-input", TextArea).text.strip()
            design = self.query_one("#edit-project-design-input", TextArea).text.strip()
            engineering = self.query_one("#edit-project-eng-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({
                "name": name,
                "description": description,
                "design_principles": design,
                "engineering_principles": engineering,
            })
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Create researcher modal ────────────────────────────────────────────


class CreateResearcherModal(ModalScreen[dict | None]):
    """Create a new researcher with repos."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._repos: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="create-researcher-dialog"):
            yield Static("[bold #333]Create Researcher[/]", id="create-researcher-title")
            yield Label("Name")
            yield Input(placeholder="Researcher name", id="researcher-name-input")
            yield Label("Principles")
            yield TextArea(id="researcher-principles-input")
            yield Static("[bold #555]Add Repo[/]", id="add-researcher-repo-heading")
            yield Label("Repo Name")
            yield Input(placeholder="e.g. ml-experiments", id="researcher-repo-name-input")
            yield Label("Repo Path")
            yield Input(placeholder="/path/to/repo", id="researcher-repo-path-input")
            yield Label("Base Branch")
            yield Input(value="main", placeholder="main", id="researcher-repo-branch-input")
            with Horizontal(id="add-researcher-repo-buttons"):
                yield Button("Add repo", variant="default", id="add-researcher-repo-btn")
            yield Static("", id="researcher-repo-list-display")
            with Horizontal(id="create-researcher-buttons"):
                yield Button("Create", variant="warning", id="create-researcher-confirm")
                yield Button("Cancel", variant="default", id="create-researcher-cancel")

    def on_mount(self) -> None:
        self.query_one("#researcher-name-input", Input).focus()

    def _update_repo_list(self) -> None:
        if self._repos:
            lines = [f"  [#555]{r['name']}[/] \u2014 {r['path']} ({r['base_branch']})" for r in self._repos]
            self.query_one("#researcher-repo-list-display", Static).update(
                "[#888]Repos:[/]\n" + "\n".join(lines)
            )
        else:
            self.query_one("#researcher-repo-list-display", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-researcher-repo-btn":
            name = self.query_one("#researcher-repo-name-input", Input).value.strip()
            path = self.query_one("#researcher-repo-path-input", Input).value.strip()
            branch = self.query_one("#researcher-repo-branch-input", Input).value.strip() or "main"
            if name and path:
                self._repos.append({"name": name, "path": path, "base_branch": branch})
                self.query_one("#researcher-repo-name-input", Input).value = ""
                self.query_one("#researcher-repo-path-input", Input).value = ""
                self.query_one("#researcher-repo-branch-input", Input).value = "main"
                self._update_repo_list()
        elif event.button.id == "create-researcher-confirm":
            name = self.query_one("#researcher-name-input", Input).value.strip()
            principles = self.query_one("#researcher-principles-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({"name": name, "principles": principles, "repos": self._repos})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Edit researcher modal ──────────────────────────────────────────────


class EditResearcherModal(ModalScreen[dict | None]):
    """Edit an existing researcher's name and principles."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, researcher: Researcher, **kw):
        super().__init__(**kw)
        self._researcher = researcher

    def compose(self) -> ComposeResult:
        r = self._researcher
        with Vertical(id="edit-researcher-dialog"):
            yield Static("[bold #333]Edit Researcher[/]", id="edit-researcher-title")
            yield Label("Name")
            yield Input(value=r.name, id="edit-researcher-name-input")
            yield Label("Principles")
            yield TextArea(r.principles, id="edit-researcher-principles-input")
            if r.repos:
                repo_lines = "\n".join(
                    f"  [#555]{repo.name}[/] \u2014 {repo.path} ({repo.base_branch})" for repo in r.repos
                )
                yield Static(f"[#888]Repos (read-only):[/]\n{repo_lines}", id="edit-researcher-repos")
            with Horizontal(id="edit-researcher-buttons"):
                yield Button("Save", variant="warning", id="edit-researcher-save")
                yield Button("Cancel", variant="default", id="edit-researcher-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-researcher-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-researcher-save":
            name = self.query_one("#edit-researcher-name-input", Input).value.strip()
            principles = self.query_one("#edit-researcher-principles-input", TextArea).text.strip()
            if not name:
                self.app.notify("Name is required", severity="warning")
                return
            self.dismiss({"name": name, "principles": principles})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Edit experiment modal ──────────────────────────────────────────────


class EditExperimentModal(ModalScreen[dict | None]):
    """Edit an experiment's title, description, and status."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, experiment: Experiment, **kw):
        super().__init__(**kw)
        self._experiment = experiment

    def compose(self) -> ComposeResult:
        e = self._experiment
        status_choices = [(s.value, s.value) for s in ExperimentStatus]
        with Vertical(id="edit-experiment-dialog"):
            yield Static("[bold #333]Edit Experiment[/]", id="edit-experiment-title")
            yield Label("Title")
            yield Input(value=e.title, id="edit-experiment-title-input")
            yield Label("Description")
            yield TextArea(e.description, id="edit-experiment-desc-input")
            yield Label("Status")
            yield Select(
                status_choices,
                value=str(e.status),
                id="edit-experiment-status-select",
            )
            with Horizontal(id="edit-experiment-buttons"):
                yield Button("Save", variant="warning", id="edit-experiment-save")
                yield Button("Cancel", variant="default", id="edit-experiment-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-experiment-title-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-experiment-save":
            title = self.query_one("#edit-experiment-title-input", Input).value.strip()
            description = self.query_one("#edit-experiment-desc-input", TextArea).text.strip()
            select = self.query_one("#edit-experiment-status-select", Select)
            status = select.value
            if not title:
                self.app.notify("Title is required", severity="warning")
                return
            self.dismiss({"title": title, "description": description, "status": status})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
