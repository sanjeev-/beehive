"""Beehive TUI Application — terminal dashboard."""

import subprocess
import shutil
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Label, Static

from beehive.core.architect import Architect, ArchitectRepo, TicketStatus
from beehive.core.architect_storage import ArchitectStorage
from beehive.core.docker_manager import DockerManager
from beehive.core.git_ops import GitOperations
from beehive.core.preview import PreviewManager
from beehive.core.project import Project
from beehive.core.project_storage import ProjectStorage
from beehive.core.researcher import ExperimentStatus, Researcher
from beehive.core.researcher_storage import ResearcherStorage
from beehive.core.session import SessionManager, SessionStatus
from beehive.core.tmux_manager import TmuxManager
from beehive.tui.modals import (
    ConfirmModal,
    CreateArchitectModal,
    CreateProjectModal,
    CreateResearcherModal,
    EditArchitectModal,
    EditExperimentModal,
    EditProjectModal,
    EditResearcherModal,
    EditTicketModal,
    LinkArchitectModal,
    SendPromptModal,
    UnlinkArchitectModal,
)


# ─── Data layer ───────────────────────────────────────────────────────────────


class DataStore:
    """Reads beehive data from disk. Shared by all views."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.session_mgr = SessionManager(data_dir)
        self.architect_storage = ArchitectStorage(data_dir)
        self.project_storage = ProjectStorage(data_dir)
        self.researcher_storage = ResearcherStorage(data_dir)
        self.preview_mgr = PreviewManager(data_dir)
        self.tmux = TmuxManager()
        self.docker = DockerManager()

    def sessions(self):
        return self.session_mgr.list_sessions()

    def architects(self):
        return self.architect_storage.load_all_architects()

    def projects(self):
        return self.project_storage.load_all_projects()

    def researchers(self):
        return self.researcher_storage.load_all_researchers()


# ─── Header ───────────────────────────────────────────────────────────────────


class BeehiveHeader(Static):
    """Top bar — dark strip with bee-yellow logo."""

    def render(self):
        return "  [bold #FEE100]bh[/] \U0001f41d"


# ─── Sidebar ─────────────────────────────────────────────────────────────────


NAV_ITEMS = [
    ("home", "\u2302  Home"),
    ("projects", "\u2630  Projects"),
    ("architects", "\u2692  Architects"),
    ("researchers", "\U0001F52C  Researchers"),
    ("agents", "\u2699  Agents"),
]


class NavItem(Static):
    """Single navigation item in the sidebar."""

    def __init__(self, key: str, label: str, **kw):
        super().__init__(label, **kw)
        self.nav_key = key


class Sidebar(Vertical):
    """Left navigation column."""

    can_focus = True

    active_view: reactive[str] = reactive("home")

    def compose(self) -> ComposeResult:
        yield Label("Views", id="sidebar-title")
        for key, label in NAV_ITEMS:
            item = NavItem(key, label, id=f"nav-{key}")
            yield item

    def watch_active_view(self, value: str) -> None:
        for child in self.query(NavItem):
            child.set_class(child.nav_key == value, "active")

    def on_click(self, event) -> None:
        for child in self.query(NavItem):
            if child is event.widget or child in event.widget.ancestors:
                self.active_view = child.nav_key
                self.app.set_view(child.nav_key)
                break

    def on_key(self, event: events.Key) -> None:
        items = list(NAV_ITEMS)
        current_idx = next(
            (i for i, (k, _) in enumerate(items) if k == self.active_view), 0
        )
        if event.key == "down":
            new_idx = min(current_idx + 1, len(items) - 1)
            self.active_view = items[new_idx][0]
            self.app.set_view(items[new_idx][0])
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            new_idx = max(current_idx - 1, 0)
            self.active_view = items[new_idx][0]
            self.app.set_view(items[new_idx][0])
            event.prevent_default()
            event.stop()
        elif event.key in ("right", "enter"):
            self.app._focus_table()
            event.prevent_default()
            event.stop()


# ─── Home view ────────────────────────────────────────────────────────────────


class SummaryCard(Static):
    """A metric card with label and value."""

    def __init__(self, title: str, value: str = "0", card_id: str = "", **kw):
        super().__init__(**kw)
        self.card_title = title
        self.card_value = value
        self.card_id = card_id

    def render(self):
        return f"[bold #FFFFFF]{self.card_value}[/]\n[#888888]{self.card_title}[/]"

    def update_value(self, value: str):
        self.card_value = value
        self.refresh()


class HomeView(Container):
    """Dashboard — summary cards, stats, activity feed."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="cards-row"):
            yield SummaryCard("Agents running", "—", id="card-running")
            yield SummaryCard("Total agents", "—", id="card-total")
            yield SummaryCard("Architects", "—", id="card-architects")
            yield SummaryCard("Researchers", "—", id="card-researchers")
            yield SummaryCard("Open PRs", "—", id="card-prs")

        with Horizontal(id="home-body"):
            with Vertical(id="stats-panel"):
                yield Label("Quick stats", id="stats-title")
                yield Static("", id="stats-content")
            with Vertical(id="activity-panel"):
                yield Label("Recent activity", id="activity-title")
                yield Static("", id="activity-content")

    def refresh_data(self, store: DataStore) -> None:
        sessions = store.sessions()
        architects = store.architects()
        researchers = store.researchers()

        running = sum(1 for s in sessions if s.status == "running")
        completed = sum(1 for s in sessions if s.status == "completed")
        failed = sum(1 for s in sessions if s.status == "failed")
        stopped = sum(1 for s in sessions if s.status == "stopped")
        prs = sum(1 for s in sessions if s.pr_url)

        self.query_one("#card-running", SummaryCard).update_value(str(running))
        self.query_one("#card-total", SummaryCard).update_value(str(len(sessions)))
        self.query_one("#card-architects", SummaryCard).update_value(str(len(architects)))
        self.query_one("#card-researchers", SummaryCard).update_value(str(len(researchers)))
        self.query_one("#card-prs", SummaryCard).update_value(str(prs))

        from datetime import datetime, timedelta

        today = datetime.utcnow().date()
        today_sessions = sum(
            1 for s in sessions if s.created_at.date() == today
        )

        total_tickets = 0
        completed_tickets = 0
        for a in architects:
            for p in a.plans:
                for t in p.tickets:
                    total_tickets += 1
                    if t.status == TicketStatus.COMPLETED:
                        completed_tickets += 1

        total_experiments = 0
        completed_experiments = 0
        for r in researchers:
            for s in r.studies:
                for e in s.experiments:
                    total_experiments += 1
                    if e.status == ExperimentStatus.COMPLETED:
                        completed_experiments += 1

        success_rate = (
            f"{completed / len(sessions) * 100:.0f}%"
            if sessions
            else "—"
        )

        active_previews = len(store.preview_mgr.list_previews())

        stats_text = (
            f"[#888888]Sessions today[/]    [bold #FFFFFF]{today_sessions}[/]\n"
            f"[#888888]Completed[/]         [#5a8a5a]{completed}[/]\n"
            f"[#888888]Failed[/]            [#b84040]{failed}[/]\n"
            f"[#888888]Stopped[/]           [#888888]{stopped}[/]\n"
            f"[#888888]Success rate[/]      [bold #FFFFFF]{success_rate}[/]\n"
            f"\n"
            f"[#888888]Total tickets[/]     [bold #FFFFFF]{total_tickets}[/]\n"
            f"[#888888]Tickets done[/]      [#5a8a5a]{completed_tickets}[/]\n"
            f"[#888888]Experiments[/]       [bold #FFFFFF]{total_experiments}[/]\n"
            f"[#888888]Experiments done[/]  [#5a8a5a]{completed_experiments}[/]\n"
            f"[#888888]Active previews[/]   [bold #FFFFFF]{active_previews}[/]"
        )
        self.query_one("#stats-content", Static).update(stats_text)

        # Activity feed
        activities = []
        for s in sessions:
            verb = {
                "running": "[#FEE100]started[/]",
                "completed": "[#5a8a5a]completed[/]",
                "failed": "[#b84040]failed[/]",
                "stopped": "[#888888]stopped[/]",
            }.get(s.status, s.status)
            ts = s.created_at.strftime("%m/%d %H:%M")
            activities.append(
                (s.created_at, f"[#777777]{ts}[/]  [#CCCCCC]{s.name}[/] {verb}")
            )
            if s.pr_url:
                activities.append(
                    (s.created_at, f"[#777777]{ts}[/]  [#CCCCCC]PR opened[/] [#888888]{s.pr_url}[/]")
                )

        for a in architects:
            for p in a.plans:
                ts = p.created_at.strftime("%m/%d %H:%M")
                activities.append(
                    (
                        p.created_at,
                        f"[#777777]{ts}[/]  Plan [#CCCCCC]{p.plan_id[:8]}[/] "
                        f'[#CCCCCC]"{p.directive[:40]}"[/]',
                    )
                )
                for t in p.tickets:
                    if t.session_id:
                        ts2 = t.updated_at.strftime("%m/%d %H:%M")
                        activities.append(
                            (
                                t.updated_at,
                                f"[#777777]{ts2}[/]  [#CCCCCC]{t.title[:30]}[/] "
                                f"\u2192 [#888888]{t.session_id}[/]",
                            )
                        )

        for r in researchers:
            for s in r.studies:
                ts = s.created_at.strftime("%m/%d %H:%M")
                activities.append(
                    (
                        s.created_at,
                        f"[#777777]{ts}[/]  Study [#CCCCCC]{s.study_id[:8]}[/] "
                        f'[#CCCCCC]"{s.directive[:40]}"[/]',
                    )
                )
                for e in s.experiments:
                    if e.session_id:
                        ts2 = e.updated_at.strftime("%m/%d %H:%M")
                        activities.append(
                            (
                                e.updated_at,
                                f"[#777777]{ts2}[/]  [#CCCCCC]{e.title[:30]}[/] "
                                f"\u2192 [#888888]{e.session_id}[/]",
                            )
                        )

        activities.sort(key=lambda x: x[0], reverse=True)
        feed_lines = [line for _, line in activities[:20]]
        if not feed_lines:
            feed_lines = ["[#666666]No activity yet.[/]"]
        self.query_one("#activity-content", Static).update("\n".join(feed_lines))


# ─── Projects view ───────────────────────────────────────────────────────────


class ProjectsView(Container):
    """Projects list with detail panel."""

    BINDINGS = [
        Binding("c", "create_project", "Create", show=True),
        Binding("e", "edit_project", "Edit", show=True),
        Binding("d", "delete_project", "Delete", show=True),
        Binding("l", "link_architect", "Link arch", show=True),
        Binding("u", "unlink_architect", "Unlink arch", show=True),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._projects = []
        self._columns_added = False
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Label("Projects", id="projects-title")
        with Horizontal(id="projects-body"):
            yield DataTable(id="projects-table")
            with Vertical(id="project-detail-panel"):
                yield Static("", id="project-detail-content")

    def on_mount(self) -> None:
        table = self.query_one("#projects-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def refresh_data(self, store: DataStore) -> None:
        self._loading = True
        try:
            self._projects = store.projects()
            table = self.query_one("#projects-table", DataTable)
            if not self._columns_added:
                table.add_columns("Id", "Name", "Repos", "Architects", "Created")
                self._columns_added = True
            else:
                table.clear()
            for p in self._projects:
                repo_names = ", ".join(r.name for r in p.repos) if p.repos else "—"
                table.add_row(
                    p.project_id,
                    p.name[:25],
                    repo_names,
                    str(len(p.architect_ids)),
                    p.created_at.strftime("%m/%d %H:%M"),
                )
            if not self._projects:
                self.query_one("#project-detail-content", Static).update(
                    "[#666666]No projects found.[/]"
                )
        finally:
            self._loading = False

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._loading:
            self._show_detail(event.cursor_row)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._loading:
            self._show_detail(event.cursor_row)

    def _show_detail(self, idx: int) -> None:
        if not (0 <= idx < len(self._projects)):
            return
        p = self._projects[idx]

        lines = [
            f"[bold #FFFFFF]{p.name}[/]",
            "",
            f"[#888888]Id[/]           {p.project_id}",
            f"[#888888]Created[/]      {p.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if p.description:
            lines.append(f"[#888888]Description[/]  {p.description[:120]}")

        if p.design_principles:
            lines.append("")
            lines.append("[#777777]Design principles[/]")
            for line in p.design_principles.strip().split("\n")[:6]:
                lines.append(f"  [#999999]{line}[/]")

        if p.engineering_principles:
            lines.append("")
            lines.append("[#777777]Engineering principles[/]")
            for line in p.engineering_principles.strip().split("\n")[:6]:
                lines.append(f"  [#999999]{line}[/]")

        if p.repos:
            lines.append("")
            lines.append("[#777777]Repos[/]")
            for r in p.repos:
                desc = f" — {r.description}" if r.description else ""
                lines.append(f"  [#CCCCCC]{r.name}[/]  {r.path}{desc}")

        if p.preview:
            lines.append("")
            lines.append("[#777777]Preview config[/]")
            lines.append(f"  [#999999]Command: {p.preview.setup_command}[/]")
            lines.append(f"  [#999999]URL: {p.preview.url_template}[/]")
            if p.preview.teardown_command:
                lines.append(f"  [#999999]Teardown: {p.preview.teardown_command}[/]")
            lines.append(f"  [#999999]Timeout: {p.preview.startup_timeout}s[/]")

        if p.architect_ids:
            lines.append("")
            lines.append("[#777777]Linked architects[/]")
            for arch_id in p.architect_ids:
                lines.append(f"  [#CCCCCC]{arch_id}[/]")

        self.query_one("#project-detail-content", Static).update("\n".join(lines))

    def _get_selected_project(self):
        """Return the currently highlighted project, or None."""
        try:
            table = self.query_one("#projects-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._projects):
                return self._projects[idx]
        except Exception:
            pass
        return None

    def action_create_project(self) -> None:
        self.app.push_screen(
            CreateProjectModal(),
            callback=self._do_create_project,
        )

    def _do_create_project(self, result: dict | None) -> None:
        if not result:
            return
        try:
            project = Project(
                name=result["name"],
                description=result.get("description", ""),
                design_principles=result.get("design_principles", ""),
                engineering_principles=result.get("engineering_principles", ""),
            )
            self.app.store.project_storage.save_project(project)
            self.app.notify(f"Created project {project.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_edit_project(self) -> None:
        project = self._get_selected_project()
        if not project:
            self.app.notify("No project selected", severity="warning")
            return
        self.app.push_screen(
            EditProjectModal(project),
            callback=lambda result: self._do_edit_project(project, result) if result else None,
        )

    def _do_edit_project(self, project, result: dict) -> None:
        try:
            full_project = self.app.store.project_storage.load_project(project.project_id)
            if full_project:
                full_project.name = result["name"]
                full_project.description = result.get("description", "")
                full_project.design_principles = result.get("design_principles", "")
                full_project.engineering_principles = result.get("engineering_principles", "")
                self.app.store.project_storage.save_project(full_project)
                self.app.notify(f"Updated project {full_project.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_delete_project(self) -> None:
        project = self._get_selected_project()
        if not project:
            self.app.notify("No project selected", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Delete project [bold]{project.name}[/]?"),
            callback=lambda confirmed: self._do_delete_project(project) if confirmed else None,
        )

    def _do_delete_project(self, project) -> None:
        try:
            self.app.store.project_storage.delete_project(project.project_id)
            self.app.notify(f"Deleted project {project.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_link_architect(self) -> None:
        project = self._get_selected_project()
        if not project:
            self.app.notify("No project selected", severity="warning")
            return
        all_architects = self.app.store.architects()
        unlinked = [
            (a.architect_id, a.name)
            for a in all_architects
            if a.architect_id not in project.architect_ids
        ]
        if not unlinked:
            self.app.notify("No unlinked architects available", severity="warning")
            return
        self.app.push_screen(
            LinkArchitectModal(project.name, unlinked),
            callback=lambda arch_id: self._do_link_architect(project, arch_id) if arch_id else None,
        )

    def _do_link_architect(self, project, architect_id: str) -> None:
        try:
            full_project = self.app.store.project_storage.load_project(project.project_id)
            if full_project and architect_id not in full_project.architect_ids:
                full_project.architect_ids.append(architect_id)
                self.app.store.project_storage.save_project(full_project)
                self.app.notify(f"Linked architect to {project.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_unlink_architect(self) -> None:
        project = self._get_selected_project()
        if not project:
            self.app.notify("No project selected", severity="warning")
            return
        if not project.architect_ids:
            self.app.notify("No linked architects to unlink", severity="warning")
            return
        all_architects = self.app.store.architects()
        arch_map = {a.architect_id: a.name for a in all_architects}
        linked = [
            (aid, arch_map.get(aid, aid))
            for aid in project.architect_ids
        ]
        self.app.push_screen(
            UnlinkArchitectModal(project.name, linked),
            callback=lambda arch_id: self._do_unlink_architect(project, arch_id) if arch_id else None,
        )

    def _do_unlink_architect(self, project, architect_id: str) -> None:
        try:
            full_project = self.app.store.project_storage.load_project(project.project_id)
            if full_project and architect_id in full_project.architect_ids:
                full_project.architect_ids.remove(architect_id)
                self.app.store.project_storage.save_project(full_project)
                self.app.notify(f"Unlinked architect from {project.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()


# ─── Architects view ─────────────────────────────────────────────────────────


class ArchitectsView(Container):
    """Architects list with drill-down into plans and tickets."""

    BINDINGS = [
        Binding("c", "create_architect", "Create", show=True),
        Binding("e", "edit_item", "Edit", show=True),
        Binding("d", "delete_architect", "Delete", show=True),
        Binding("a", "assign_next", "Assign next", show=True),
    ]

    depth: reactive[int] = reactive(0)  # 0=list, 1=plans, 2=tickets

    def __init__(self, **kw):
        super().__init__(**kw)
        self._architects = []
        self._selected_arch = None
        self._selected_plan = None
        self._current_shape = None  # track column layout to avoid rebuild
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Label("Architects", id="arch-breadcrumb")
        yield DataTable(id="arch-table")
        with Vertical(id="arch-detail"):
            yield Static("", id="arch-detail-content")

    def on_mount(self) -> None:
        table = self.query_one("#arch-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def _set_columns(self, table: DataTable, shape: str, columns: tuple) -> None:
        """Set table columns, only rebuilding if the shape changed."""
        if self._current_shape == shape:
            table.clear()
        else:
            table.clear(columns=True)
            table.add_columns(*columns)
            self._current_shape = shape

    def refresh_data(self, store: DataStore) -> None:
        self._loading = True
        try:
            self._architects = store.architects()
            if self.depth == 0:
                self._show_architects_list()
            elif self.depth == 1:
                self._show_plans()
            elif self.depth == 2:
                self._show_tickets()
        finally:
            self._loading = False

    def _show_architects_list(self) -> None:
        self.query_one("#arch-breadcrumb", Label).update("Architects")
        table = self.query_one("#arch-table", DataTable)
        self._set_columns(table, "architects", ("Id", "Name", "Repos", "Plans", "Latest plan"))
        for a in self._architects:
            latest = ""
            if a.plans:
                p = a.plans[-1]
                latest = p.directive[:35] + ("..." if len(p.directive) > 35 else "")
            repos = ", ".join(r.name for r in a.repos)
            table.add_row(a.architect_id[:8], a.name, repos, str(len(a.plans)), latest)
        self.query_one("#arch-detail-content", Static).update("")

    def _show_plans(self) -> None:
        if not self._selected_arch:
            return
        a = self._selected_arch
        self.query_one("#arch-breadcrumb", Label).update(
            f"Architects  \u203a  [bold #FFFFFF]{a.name}[/]  \u203a  Plans"
        )
        table = self.query_one("#arch-table", DataTable)
        self._set_columns(table, "plans", ("Id", "Directive", "Tickets", "Pending", "Done", "Failed"))
        for p in a.plans:
            pending = sum(1 for t in p.tickets if t.status in (TicketStatus.PENDING, "pending"))
            done = sum(1 for t in p.tickets if t.status in (TicketStatus.COMPLETED, "completed", TicketStatus.MERGED, "merged"))
            failed = sum(1 for t in p.tickets if t.status in (TicketStatus.FAILED, "failed"))
            directive = p.directive[:50] + ("..." if len(p.directive) > 50 else "")
            table.add_row(
                p.plan_id[:8], directive, str(len(p.tickets)),
                str(pending), str(done), str(failed),
            )

        detail = (
            f"[bold #FFFFFF]{a.name}[/]\n\n"
            f"[#888888]Id[/]          {a.architect_id}\n"
            f"[#888888]Repos[/]       {', '.join(r.name for r in a.repos)}\n\n"
            f"[#777777]Principles[/]\n[#999999]{a.principles[:200]}[/]"
        )
        self.query_one("#arch-detail-content", Static).update(detail)

    def _show_tickets(self) -> None:
        if not self._selected_plan:
            return
        p = self._selected_plan
        a = self._selected_arch
        self.query_one("#arch-breadcrumb", Label).update(
            f"Architects  \u203a  [bold #FFFFFF]{a.name}[/]  \u203a  Plans  \u203a  [bold #FFFFFF]{p.plan_id[:8]}[/]"
        )
        table = self.query_one("#arch-table", DataTable)
        self._set_columns(table, "tickets", ("#", "Id", "Title", "Repo", "Status", "Branch", "Session", "PR"))
        self._sorted_tickets = sorted(p.tickets, key=lambda t: t.order)
        for t in self._sorted_tickets:
            status_display = {
                "pending": "[#FEE100]pending[/]",
                "assigned": "[#5577bb]assigned[/]",
                "in_progress": "[#FEE100]in progress[/]",
                "completed": "[#5a8a5a]completed[/]",
                "failed": "[#b84040]failed[/]",
                "merged": "[#55bbbb]merged[/]",
            }.get(str(t.status), str(t.status))
            branch = t.branch_name or "—"
            if len(branch) > 25:
                branch = branch[:22] + "..."
            table.add_row(
                str(t.order) if t.order else "—",
                t.ticket_id[:8], t.title[:30], t.repo,
                status_display, branch, t.session_id or "—", t.pr_url or "—",
            )

        detail = (
            f"[bold #FFFFFF]Plan {p.plan_id[:8]}[/]\n\n"
            f'[#888888]Directive[/]    {p.directive[:120]}\n'
            f"[#888888]Created[/]      {p.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        if self._can_assign_next():
            detail += "\n\n[#FEE100]Ready to assign next ticket (a)[/]"
        self.query_one("#arch-detail-content", Static).update(detail)

    def _can_assign_next(self) -> bool:
        """Check if the next ticket can be assigned."""
        if self.depth != 2 or not self._selected_plan or not self._selected_arch:
            return False
        p = self._selected_plan
        if p.execution_mode != "sequential":
            return False
        in_flight = {"assigned", "in_progress"}
        has_in_flight = any(str(t.status) in in_flight for t in p.tickets)
        if has_in_flight:
            return False
        has_pending = any(str(t.status) in ("pending",) for t in p.tickets)
        return has_pending

    def action_assign_next(self) -> None:
        """Assign the next pending ticket via CLI subprocess."""
        if not self._can_assign_next():
            self.app.notify("Cannot assign next ticket now", severity="warning")
            return
        arch_id = self._selected_arch.architect_id
        subprocess.Popen(["beehive", "architect", "assign", arch_id])
        self.app.notify("Assigning next ticket...")
        self.set_timer(3, self.app._do_refresh)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._loading:
            return
        if self.depth == 0 and self._architects:
            idx = event.cursor_row
            if 0 <= idx < len(self._architects):
                self._selected_arch = self._architects[idx]
                self.depth = 1
                self._current_shape = None  # force column rebuild on drill-down
                self._show_plans()
        elif self.depth == 1 and self._selected_arch:
            idx = event.cursor_row
            if 0 <= idx < len(self._selected_arch.plans):
                self._selected_plan = self._selected_arch.plans[idx]
                self.depth = 2
                self._current_shape = None
                self._show_tickets()

    def go_back(self) -> None:
        self._current_shape = None  # force column rebuild on navigation
        if self.depth == 2:
            self.depth = 1
            self._show_plans()
        elif self.depth == 1:
            self.depth = 0
            self._selected_arch = None
            self._show_architects_list()

    def _get_selected_architect(self):
        """Return the currently highlighted architect (depth 0 only), or None."""
        if self.depth != 0:
            return None
        try:
            table = self.query_one("#arch-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._architects):
                return self._architects[idx]
        except Exception:
            pass
        return None

    def action_delete_architect(self) -> None:
        if self.depth != 0:
            self.app.notify("Navigate to architect list first", severity="warning")
            return
        architect = self._get_selected_architect()
        if not architect:
            self.app.notify("No architect selected", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Delete architect [bold]{architect.name}[/]?"),
            callback=lambda confirmed: self._do_delete_architect(architect) if confirmed else None,
        )

    def _do_delete_architect(self, architect) -> None:
        try:
            self.app.store.architect_storage.delete_architect(architect.architect_id)
            self.app.notify(f"Deleted architect {architect.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_create_architect(self) -> None:
        if self.depth != 0:
            self.app.notify("Navigate to architect list first", severity="warning")
            return
        self.app.push_screen(
            CreateArchitectModal(),
            callback=self._do_create_architect,
        )

    def _do_create_architect(self, result: dict | None) -> None:
        if not result:
            return
        try:
            repos = [
                ArchitectRepo(name=r["name"], path=r["path"], base_branch=r.get("base_branch", "main"))
                for r in result.get("repos", [])
            ]
            architect = Architect(
                name=result["name"],
                principles=result.get("principles", ""),
                repos=repos,
            )
            self.app.store.architect_storage.save_architect(architect)
            self.app.notify(f"Created architect {architect.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_edit_item(self) -> None:
        """Edit dispatches based on current depth: architect at 0, ticket at 2."""
        if self.depth == 0:
            self._action_edit_architect()
        elif self.depth == 2:
            self._action_edit_ticket()

    def _action_edit_architect(self) -> None:
        architect = self._get_selected_architect()
        if not architect:
            self.app.notify("No architect selected", severity="warning")
            return
        self.app.push_screen(
            EditArchitectModal(architect),
            callback=lambda result: self._do_edit_architect(architect, result) if result else None,
        )

    def _do_edit_architect(self, architect, result: dict) -> None:
        try:
            full_arch = self.app.store.architect_storage.load_architect(architect.architect_id)
            if full_arch:
                full_arch.name = result["name"]
                full_arch.principles = result.get("principles", "")
                self.app.store.architect_storage.save_architect(full_arch)
                self.app.notify(f"Updated architect {full_arch.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def _action_edit_ticket(self) -> None:
        if not self._selected_plan or not self._selected_arch:
            return
        try:
            table = self.query_one("#arch-table", DataTable)
            idx = table.cursor_row
            sorted_tickets = getattr(self, "_sorted_tickets", self._selected_plan.tickets)
            if 0 <= idx < len(sorted_tickets):
                ticket = sorted_tickets[idx]
                self.app.push_screen(
                    EditTicketModal(ticket),
                    callback=lambda result: self._do_edit_ticket(ticket, result) if result else None,
                )
        except Exception:
            pass

    def _do_edit_ticket(self, ticket, result: dict) -> None:
        try:
            from datetime import datetime

            ticket.title = result["title"]
            ticket.description = result.get("description", "")
            ticket.status = result["status"]
            ticket.updated_at = datetime.utcnow()
            self.app.store.architect_storage.save_plan(
                self._selected_arch.architect_id, self._selected_plan
            )
            self.app.notify(f"Updated ticket {ticket.title}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()


# ─── Researchers view ─────────────────────────────────────────────────────────


class ResearchersView(Container):
    """Researchers list with drill-down into studies and experiments."""

    BINDINGS = [
        Binding("c", "create_researcher", "Create", show=True),
        Binding("e", "edit_item", "Edit", show=True),
        Binding("d", "delete_researcher", "Delete", show=True),
        Binding("o", "open_output", "Open output", show=True),
    ]

    depth: reactive[int] = reactive(0)  # 0=list, 1=studies, 2=experiments

    def __init__(self, **kw):
        super().__init__(**kw)
        self._researchers = []
        self._selected_researcher = None
        self._selected_study = None
        self._current_shape = None
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Label("Researchers", id="researcher-breadcrumb")
        yield DataTable(id="researcher-table")
        with Vertical(id="researcher-detail"):
            yield Static("", id="researcher-detail-content")

    def on_mount(self) -> None:
        table = self.query_one("#researcher-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def _set_columns(self, table: DataTable, shape: str, columns: tuple) -> None:
        """Set table columns, only rebuilding if the shape changed."""
        if self._current_shape == shape:
            table.clear()
        else:
            table.clear(columns=True)
            table.add_columns(*columns)
            self._current_shape = shape

    def refresh_data(self, store: DataStore) -> None:
        self._loading = True
        try:
            self._researchers = store.researchers()
            if self.depth == 0:
                self._show_researchers_list()
            elif self.depth == 1:
                self._show_studies()
            elif self.depth == 2:
                self._show_experiments()
        finally:
            self._loading = False

    def _show_researchers_list(self) -> None:
        self.query_one("#researcher-breadcrumb", Label).update("Researchers")
        table = self.query_one("#researcher-table", DataTable)
        self._set_columns(table, "researchers", ("Id", "Name", "Repos", "Studies", "Latest study"))
        for r in self._researchers:
            latest = ""
            if r.studies:
                s = r.studies[-1]
                latest = s.directive[:35] + ("..." if len(s.directive) > 35 else "")
            repos = ", ".join(repo.name for repo in r.repos)
            table.add_row(r.researcher_id[:8], r.name, repos, str(len(r.studies)), latest)
        self.query_one("#researcher-detail-content", Static).update("")

    def _show_studies(self) -> None:
        if not self._selected_researcher:
            return
        r = self._selected_researcher
        self.query_one("#researcher-breadcrumb", Label).update(
            f"Researchers  \u203a  [bold #FFFFFF]{r.name}[/]  \u203a  Studies"
        )
        table = self.query_one("#researcher-table", DataTable)
        self._set_columns(table, "studies", ("Id", "Directive", "Experiments", "Pending", "Done", "Failed"))
        for s in r.studies:
            pending = sum(1 for e in s.experiments if e.status in (ExperimentStatus.PENDING, "pending"))
            done = sum(1 for e in s.experiments if e.status in (ExperimentStatus.COMPLETED, "completed"))
            failed = sum(1 for e in s.experiments if e.status in (ExperimentStatus.FAILED, "failed"))
            directive = s.directive[:50] + ("..." if len(s.directive) > 50 else "")
            table.add_row(
                s.study_id[:8], directive, str(len(s.experiments)),
                str(pending), str(done), str(failed),
            )

        detail = (
            f"[bold #FFFFFF]{r.name}[/]\n\n"
            f"[#888888]Id[/]          {r.researcher_id}\n"
            f"[#888888]Repos[/]       {', '.join(repo.name for repo in r.repos)}\n\n"
            f"[#777777]Principles[/]\n[#999999]{r.principles[:200]}[/]"
        )
        self.query_one("#researcher-detail-content", Static).update(detail)

    def _show_experiments(self) -> None:
        if not self._selected_study:
            return
        s = self._selected_study
        r = self._selected_researcher
        self.query_one("#researcher-breadcrumb", Label).update(
            f"Researchers  \u203a  [bold #FFFFFF]{r.name}[/]  \u203a  Studies  \u203a  [bold #FFFFFF]{s.study_id[:8]}[/]"
        )
        table = self.query_one("#researcher-table", DataTable)
        self._set_columns(table, "experiments", ("Id", "Title", "Repo", "Status", "Session", "Output"))
        for e in s.experiments:
            status_display = {
                "pending": "[#FEE100]pending[/]",
                "assigned": "[#5577bb]assigned[/]",
                "in_progress": "[#FEE100]in progress[/]",
                "completed": "[#5a8a5a]completed[/]",
                "failed": "[#b84040]failed[/]",
            }.get(str(e.status), str(e.status))
            output = e.output_dir or "\u2014"
            if e.output_dir and len(e.output_dir) > 30:
                output = "..." + e.output_dir[-27:]
            table.add_row(
                e.experiment_id[:8], e.title[:30], e.repo,
                status_display, e.session_id or "\u2014", output,
            )

        detail = (
            f"[bold #FFFFFF]Study {s.study_id[:8]}[/]\n\n"
            f'[#888888]Directive[/]    {s.directive[:120]}\n'
            f"[#888888]Created[/]      {s.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        self.query_one("#researcher-detail-content", Static).update(detail)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._loading:
            return
        if self.depth == 0 and self._researchers:
            idx = event.cursor_row
            if 0 <= idx < len(self._researchers):
                self._selected_researcher = self._researchers[idx]
                self.depth = 1
                self._current_shape = None
                self._show_studies()
        elif self.depth == 1 and self._selected_researcher:
            idx = event.cursor_row
            if 0 <= idx < len(self._selected_researcher.studies):
                self._selected_study = self._selected_researcher.studies[idx]
                self.depth = 2
                self._current_shape = None
                self._show_experiments()

    def go_back(self) -> None:
        self._current_shape = None
        if self.depth == 2:
            self.depth = 1
            self._show_studies()
        elif self.depth == 1:
            self.depth = 0
            self._selected_researcher = None
            self._show_researchers_list()

    def _get_selected_researcher(self):
        """Return the currently highlighted researcher (depth 0 only), or None."""
        if self.depth != 0:
            return None
        try:
            table = self.query_one("#researcher-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._researchers):
                return self._researchers[idx]
        except Exception:
            pass
        return None

    def action_delete_researcher(self) -> None:
        if self.depth != 0:
            self.app.notify("Navigate to researcher list first", severity="warning")
            return
        researcher = self._get_selected_researcher()
        if not researcher:
            self.app.notify("No researcher selected", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Delete researcher [bold]{researcher.name}[/]?"),
            callback=lambda confirmed: self._do_delete_researcher(researcher) if confirmed else None,
        )

    def _do_delete_researcher(self, researcher) -> None:
        try:
            self.app.store.researcher_storage.delete_researcher(researcher.researcher_id)
            self.app.notify(f"Deleted researcher {researcher.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_create_researcher(self) -> None:
        if self.depth != 0:
            self.app.notify("Navigate to researcher list first", severity="warning")
            return
        self.app.push_screen(
            CreateResearcherModal(),
            callback=self._do_create_researcher,
        )

    def _do_create_researcher(self, result: dict | None) -> None:
        if not result:
            return
        try:
            repos = [
                ArchitectRepo(name=r["name"], path=r["path"], base_branch=r.get("base_branch", "main"))
                for r in result.get("repos", [])
            ]
            researcher = Researcher(
                name=result["name"],
                principles=result.get("principles", ""),
                repos=repos,
            )
            self.app.store.researcher_storage.save_researcher(researcher)
            self.app.notify(f"Created researcher {researcher.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_edit_item(self) -> None:
        """Edit dispatches based on current depth: researcher at 0, experiment at 2."""
        if self.depth == 0:
            self._action_edit_researcher()
        elif self.depth == 2:
            self._action_edit_experiment()

    def _action_edit_researcher(self) -> None:
        researcher = self._get_selected_researcher()
        if not researcher:
            self.app.notify("No researcher selected", severity="warning")
            return
        self.app.push_screen(
            EditResearcherModal(researcher),
            callback=lambda result: self._do_edit_researcher(researcher, result) if result else None,
        )

    def _do_edit_researcher(self, researcher, result: dict) -> None:
        try:
            full_res = self.app.store.researcher_storage.load_researcher(researcher.researcher_id)
            if full_res:
                full_res.name = result["name"]
                full_res.principles = result.get("principles", "")
                self.app.store.researcher_storage.save_researcher(full_res)
                self.app.notify(f"Updated researcher {full_res.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def _action_edit_experiment(self) -> None:
        if not self._selected_study or not self._selected_researcher:
            return
        try:
            table = self.query_one("#researcher-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._selected_study.experiments):
                experiment = self._selected_study.experiments[idx]
                self.app.push_screen(
                    EditExperimentModal(experiment),
                    callback=lambda result: self._do_edit_experiment(experiment, result) if result else None,
                )
        except Exception:
            pass

    def _do_edit_experiment(self, experiment, result: dict) -> None:
        try:
            from datetime import datetime

            experiment.title = result["title"]
            experiment.description = result.get("description", "")
            experiment.status = result["status"]
            experiment.updated_at = datetime.utcnow()
            self.app.store.researcher_storage.save_study(
                self._selected_researcher.researcher_id, self._selected_study
            )
            self.app.notify(f"Updated experiment {experiment.title}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_open_output(self) -> None:
        """Open the output directory in Finder (macOS)."""
        if self.depth != 2:
            self.app.notify("Navigate to experiments first", severity="warning")
            return
        if not self._selected_study:
            return
        try:
            table = self.query_one("#researcher-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._selected_study.experiments):
                experiment = self._selected_study.experiments[idx]
                if experiment.output_dir:
                    import subprocess
                    subprocess.Popen(["open", experiment.output_dir])
                    self.app.notify(f"Opening {experiment.output_dir}")
                else:
                    self.app.notify("No output directory set", severity="warning")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")


# ─── Agents view ──────────────────────────────────────────────────────────────


class AgentsView(Container):
    """Agent session list with detail panel."""

    BINDINGS = [
        Binding("s", "stop_agent", "Stop", show=True),
        Binding("d", "delete_agent", "Delete", show=True),
        Binding("p", "send_prompt", "Prompt", show=True),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._sessions = []
        self._columns_added = False
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Label("Agents", id="agents-title")
        with Horizontal(id="agents-body"):
            yield DataTable(id="agents-table")
            with Vertical(id="agent-detail-panel"):
                yield Static("", id="agent-detail-content")

    def on_mount(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def refresh_data(self, store: DataStore) -> None:
        self._loading = True
        try:
            self._sessions = store.sessions()
            table = self.query_one("#agents-table", DataTable)
            if not self._columns_added:
                table.add_columns("Id", "Name", "Status", "Runtime", "Branch", "Created")
                self._columns_added = True
            else:
                table.clear()
            for s in self._sessions:
                status_display = {
                    "running": "[#FEE100]running[/]",
                    "completed": "[#5a8a5a]completed[/]",
                    "failed": "[#b84040]failed[/]",
                    "stopped": "[#888888]stopped[/]",
                }.get(s.status, s.status)
                runtime = "[#8a6dbf]docker[/]" if s.runtime == "docker" else "[#888888]host[/]"
                branch = s.branch_name
                if len(branch) > 30:
                    branch = branch[:27] + "..."
                table.add_row(
                    s.session_id,
                    s.name[:20],
                    status_display,
                    runtime,
                    branch,
                    s.created_at.strftime("%m/%d %H:%M"),
                )
            if not self._sessions:
                self.query_one("#agent-detail-content", Static).update(
                    "[#666666]No agent sessions found.[/]"
                )
        finally:
            self._loading = False

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not self._loading:
            self._show_detail(event.cursor_row)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._loading:
            self._show_detail(event.cursor_row)

    def _show_detail(self, idx: int) -> None:
        if not (0 <= idx < len(self._sessions)):
            return
        s = self._sessions[idx]
        status_color = {
            "running": "#FEE100",
            "completed": "#5a8a5a",
            "failed": "#b84040",
            "stopped": "#888888",
        }.get(s.status, "#CCCCCC")

        lines = [
            f"[bold #FFFFFF]{s.name}[/]",
            "",
            f"[#888888]Id[/]          {s.session_id}",
            f"[#888888]Status[/]      [{status_color}]{s.status}[/{status_color}]",
            f"[#888888]Runtime[/]     {s.runtime}",
            f"[#888888]Branch[/]      {s.branch_name}",
            f"[#888888]Repo[/]        {s.original_repo}",
            f"[#888888]Worktree[/]    {s.working_directory}",
            f"[#888888]Created[/]     {s.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if s.completed_at:
            lines.append(
                f"[#888888]Completed[/]   {s.completed_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        if s.pr_url:
            lines.append(f"[#888888]PR[/]         [#CCCCCC]{s.pr_url}[/]")
        if s.preview_url:
            lines.append(f"[#888888]Preview[/]    [#CCCCCC]{s.preview_url}[/]")

        instr = s.instructions[:150].replace("\n", " ")
        lines.append(f"\n[#888888]Task[/]  {instr}...")

        log_path = Path(s.log_file)
        if log_path.exists():
            lines.append("")
            lines.append("[#777777]Recent log[/]")
            try:
                size = log_path.stat().st_size
                read_bytes = min(size, 2048)
                with open(log_path, "rb") as f:
                    if size > read_bytes:
                        f.seek(size - read_bytes)
                    raw = f.read().decode("utf-8", errors="replace")
                tail = raw.strip().split("\n")[-8:]
                for log_line in tail:
                    clean = log_line[:80].replace("[", "\\[")
                    lines.append(f"  [#777777]{clean}[/]")
            except Exception:
                lines.append("  [#666666]Could not read log.[/]")

        self.query_one("#agent-detail-content", Static).update("\n".join(lines))

    def _get_selected_session(self):
        """Return the currently highlighted session, or None."""
        try:
            table = self.query_one("#agents-table", DataTable)
            idx = table.cursor_row
            if 0 <= idx < len(self._sessions):
                return self._sessions[idx]
        except Exception:
            pass
        return None

    def action_stop_agent(self) -> None:
        session = self._get_selected_session()
        if not session:
            self.app.notify("No agent selected", severity="warning")
            return
        if session.status != "running":
            self.app.notify("Agent is not running", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Stop agent [bold]{session.name}[/]?"),
            callback=lambda confirmed: self._do_stop_agent(session) if confirmed else None,
        )

    def _do_stop_agent(self, session) -> None:
        try:
            store = self.app.store
            if session.runtime == "docker":
                if store.docker.container_running(session.session_id):
                    store.docker.stop_container(session.session_id)
            if store.tmux.session_exists(session.tmux_session_name):
                store.tmux.kill_session(session.tmux_session_name)
            store.session_mgr.update_session(
                session.session_id, status=SessionStatus.STOPPED
            )
            self.app.notify(f"Stopped agent {session.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_delete_agent(self) -> None:
        session = self._get_selected_session()
        if not session:
            self.app.notify("No agent selected", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Delete agent [bold]{session.name}[/]?\nThis will remove the workspace."),
            callback=lambda confirmed: self._do_delete_agent(session) if confirmed else None,
        )

    def _do_delete_agent(self, session) -> None:
        try:
            store = self.app.store
            if session.runtime == "docker":
                if store.docker.container_running(session.session_id):
                    store.docker.stop_container(session.session_id)
            if store.tmux.session_exists(session.tmux_session_name):
                store.tmux.kill_session(session.tmux_session_name)
            worktree_path = Path(session.working_directory)
            if session.runtime == "docker":
                if worktree_path.exists():
                    shutil.rmtree(worktree_path)
            else:
                try:
                    git = GitOperations(Path(session.original_repo))
                    if git.worktree_exists(worktree_path):
                        git.remove_worktree(worktree_path, force=True)
                except Exception:
                    pass
            store.session_mgr.delete_session(session.session_id)
            self.app.notify(f"Deleted agent {session.name}")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")
        self.app._do_refresh()

    def action_send_prompt(self) -> None:
        session = self._get_selected_session()
        if not session:
            self.app.notify("No agent selected", severity="warning")
            return
        if session.status != "running":
            self.app.notify("Agent is not running", severity="warning")
            return
        self.app.push_screen(
            SendPromptModal(session.name),
            callback=lambda text: self._do_send_prompt(session, text) if text else None,
        )

    def _do_send_prompt(self, session, text: str) -> None:
        try:
            store = self.app.store
            if store.tmux.session_exists(session.tmux_session_name):
                store.tmux.send_keys(session.tmux_session_name, text)
                self.app.notify(f"Sent prompt to {session.name}")
            else:
                self.app.notify("tmux session not found", severity="error")
        except Exception as e:
            self.app.notify(f"Error: {e}", severity="error")


# ─── Main application ────────────────────────────────────────────────────────


class BeehiveApp(App):
    """Beehive TUI — terminal dashboard for managing agents and architects."""

    CSS_PATH = "styles.tcss"
    TITLE = "Beehive"

    BINDINGS = [
        Binding("1", "switch_view('home')", "Home", show=True),
        Binding("2", "switch_view('projects')", "Projects", show=True),
        Binding("3", "switch_view('architects')", "Architects", show=True),
        Binding("4", "switch_view('researchers')", "Researchers", show=True),
        Binding("5", "switch_view('agents')", "Agents", show=True),
        Binding("left", "focus_sidebar", "\u2190 Sidebar", show=True, priority=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("r", "force_refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    VIEW_ORDER = ["home", "projects", "architects", "researchers", "agents"]

    current_view: reactive[str] = reactive("home")

    def __init__(self, data_dir: Path | None = None):
        super().__init__()
        self.data_dir = data_dir or Path.home() / ".beehive"
        self.store = DataStore(self.data_dir)
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield BeehiveHeader(id="header")
        with Horizontal(id="body"):
            yield Sidebar(id="sidebar")
            with Container(id="main"):
                yield HomeView(id="home-view")
                yield ProjectsView(id="projects-view")
                yield ArchitectsView(id="architects-view")
                yield ResearchersView(id="researchers-view")
                yield AgentsView(id="agents-view")
        yield Footer()

    def on_mount(self) -> None:
        self.set_view("home")
        self._do_refresh()
        self._refresh_timer = self.set_interval(8, self._do_refresh)
        self.query_one("#sidebar", Sidebar).focus()

    def set_view(self, view_name: str) -> None:
        self.current_view = view_name
        self.query_one("#sidebar", Sidebar).active_view = view_name
        for name in ("home", "projects", "architects", "researchers", "agents"):
            widget = self.query_one(f"#{name}-view")
            widget.set_class(name == view_name, "visible")
            widget.set_class(name != view_name, "hidden")
        self._do_refresh()

    def _focus_table(self) -> None:
        """Focus the DataTable in the current view."""
        table_id = {
            "projects": "#projects-table",
            "architects": "#arch-table",
            "researchers": "#researcher-table",
            "agents": "#agents-table",
        }.get(self.current_view)
        if table_id:
            try:
                self.query_one(table_id, DataTable).focus()
            except Exception:
                pass

    def action_switch_view(self, view_name: str) -> None:
        self.set_view(view_name)

    def action_focus_sidebar(self) -> None:
        self.query_one("#sidebar", Sidebar).focus()

    def action_go_back(self) -> None:
        if self.current_view == "architects":
            arch_view = self.query_one("#architects-view", ArchitectsView)
            if arch_view.depth > 0:
                arch_view.go_back()
                self._focus_table()
                return
        if self.current_view == "researchers":
            res_view = self.query_one("#researchers-view", ResearchersView)
            if res_view.depth > 0:
                res_view.go_back()
                self._focus_table()
                return
        self.set_view("home")

    def action_force_refresh(self) -> None:
        self._do_refresh()

    def _do_refresh(self) -> None:
        try:
            if self.current_view == "home":
                self.query_one("#home-view", HomeView).refresh_data(self.store)
            elif self.current_view == "projects":
                self.query_one("#projects-view", ProjectsView).refresh_data(self.store)
            elif self.current_view == "architects":
                self.query_one("#architects-view", ArchitectsView).refresh_data(self.store)
            elif self.current_view == "researchers":
                self.query_one("#researchers-view", ResearchersView).refresh_data(self.store)
            elif self.current_view == "agents":
                self.query_one("#agents-view", AgentsView).refresh_data(self.store)
        except Exception:
            pass


def run_tui(data_dir: Path | None = None) -> None:
    """Entry point for the TUI."""
    app = BeehiveApp(data_dir=data_dir)
    app.run()
