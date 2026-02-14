"""CLI commands for the Project and CTO features."""

import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from beehive.core.architect import ArchitectRepo
from beehive.core.architect_storage import ArchitectStorage
from beehive.core.preview import PreviewManager
from beehive.core.project import PreviewConfig, Project
from beehive.core.project_storage import ProjectStorage
from beehive.core.session import SessionManager

console = Console()


def _get_storage(ctx) -> tuple[ProjectStorage, ArchitectStorage, SessionManager]:
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    project_storage = ProjectStorage(data_dir)
    architect_storage = ArchitectStorage(data_dir)
    session_manager = ctx.obj.get("session_manager", SessionManager(data_dir))
    return project_storage, architect_storage, session_manager


# ─── Project commands ────────────────────────────────────────────────────────


@click.group()
@click.pass_context
def project(ctx):
    """Manage projects."""
    ctx.ensure_object(dict)


@project.command("create")
@click.argument("name")
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    help="YAML config file for the project",
)
@click.option("--description", "-d", default="", help="Project description")
@click.pass_context
def project_create(ctx, name: str, config_file: Optional[Path], description: str):
    """Create a new project."""
    project_storage, _, _ = _get_storage(ctx)

    proj_data = {
        "name": name,
        "description": description,
    }

    if config_file:
        with open(config_file) as f:
            config = yaml.safe_load(f)

        if config.get("description"):
            proj_data["description"] = config["description"]
        if config.get("design_principles"):
            proj_data["design_principles"] = config["design_principles"]
        if config.get("engineering_principles"):
            proj_data["engineering_principles"] = config["engineering_principles"]

        repos = []
        for repo_data in config.get("repos", []):
            repo_path = Path(repo_data["path"])
            if not repo_path.exists():
                console.print(f"[yellow]Warning: repo path does not exist: {repo_path}[/yellow]")
            repos.append(
                ArchitectRepo(
                    name=repo_data["name"],
                    path=str(repo_path),
                    base_branch=repo_data.get("base_branch", "main"),
                    description=repo_data.get("description", ""),
                )
            )
        proj_data["repos"] = repos

        if config.get("preview"):
            proj_data["preview"] = PreviewConfig(**config["preview"])

    proj = Project(**proj_data)
    project_storage.save_project(proj)

    console.print(f"[green]✓[/green] Created project: [bold]{proj.name}[/bold]")
    console.print(f"  ID: [cyan]{proj.project_id}[/cyan]")
    if proj.repos:
        console.print(f"  Repos: {', '.join(r.name for r in proj.repos)}")


@project.command("list")
@click.pass_context
def project_list(ctx):
    """List all projects."""
    project_storage, _, _ = _get_storage(ctx)
    projects = project_storage.load_all_projects()

    if not projects:
        console.print("[dim]No projects found.[/dim]")
        return

    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Repos")
    table.add_column("Architects")
    table.add_column("Created")

    for p in projects:
        repo_names = ", ".join(r.name for r in p.repos) if p.repos else "—"
        table.add_row(
            p.project_id,
            p.name,
            (p.description[:40] + "...") if len(p.description) > 40 else p.description or "—",
            repo_names,
            str(len(p.architect_ids)),
            p.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@project.command("show")
@click.argument("project_id")
@click.pass_context
def project_show(ctx, project_id: str):
    """Show project details."""
    project_storage, architect_storage, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Project: {proj.name}[/bold]")
    console.print(f"  ID: [cyan]{proj.project_id}[/cyan]")
    console.print(f"  Created: {proj.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if proj.description:
        console.print(f"  Description: {proj.description}")

    if proj.design_principles:
        console.print(f"\n[bold]Design Principles:[/bold]")
        console.print(f"  {proj.design_principles.strip()}")

    if proj.engineering_principles:
        console.print(f"\n[bold]Engineering Principles:[/bold]")
        console.print(f"  {proj.engineering_principles.strip()}")

    console.print(f"\n[bold]Repos:[/bold]")
    if proj.repos:
        for r in proj.repos:
            desc = f" — {r.description}" if r.description else ""
            console.print(f"  [cyan]{r.name}[/cyan]: {r.path} (base: {r.base_branch}){desc}")
    else:
        console.print("  [dim]No repos configured.[/dim]")

    if proj.preview:
        console.print(f"\n[bold]Preview Config:[/bold]")
        console.print(f"  Command: {proj.preview.setup_command}")
        if proj.preview.teardown_command:
            console.print(f"  Teardown: {proj.preview.teardown_command}")
        console.print(f"  URL Template: {proj.preview.url_template}")
        console.print(f"  Startup Timeout: {proj.preview.startup_timeout}s")

    console.print(f"\n[bold]Linked Architects:[/bold]")
    if proj.architect_ids:
        for arch_id in proj.architect_ids:
            arch = architect_storage.load_architect(arch_id)
            if arch:
                console.print(f"  [cyan]{arch.architect_id}[/cyan]: {arch.name}")
            else:
                console.print(f"  [dim]{arch_id} (not found)[/dim]")
    else:
        console.print("  [dim]No architects linked.[/dim]")


@project.command("delete")
@click.argument("project_id")
@click.option("--force", "-f", is_flag=True, help="Force delete without confirmation")
@click.pass_context
def project_delete(ctx, project_id: str, force: bool):
    """Delete a project."""
    project_storage, _, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    if not force:
        confirm = click.confirm(f"Delete project '{proj.name}' ({proj.project_id})?")
        if not confirm:
            console.print("Aborted.")
            return

    project_storage.delete_project(proj.project_id)
    console.print(f"[green]✓[/green] Deleted project [bold]{proj.name}[/bold]")


@project.command("link")
@click.argument("project_id")
@click.argument("architect_id")
@click.pass_context
def project_link(ctx, project_id: str, architect_id: str):
    """Link an architect to a project."""
    project_storage, architect_storage, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    arch = architect_storage.load_architect(architect_id)
    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if arch.architect_id in proj.architect_ids:
        console.print(f"[yellow]Architect {arch.name} is already linked.[/yellow]")
        return

    proj.architect_ids.append(arch.architect_id)
    project_storage.save_project(proj)
    console.print(
        f"[green]✓[/green] Linked architect [bold]{arch.name}[/bold] "
        f"to project [bold]{proj.name}[/bold]"
    )


@project.command("unlink")
@click.argument("project_id")
@click.argument("architect_id")
@click.pass_context
def project_unlink(ctx, project_id: str, architect_id: str):
    """Unlink an architect from a project."""
    project_storage, architect_storage, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    # Find the full ID (support partial match)
    arch = architect_storage.load_architect(architect_id)
    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if arch.architect_id not in proj.architect_ids:
        console.print(f"[yellow]Architect {arch.name} is not linked to this project.[/yellow]")
        return

    proj.architect_ids.remove(arch.architect_id)
    project_storage.save_project(proj)
    console.print(
        f"[green]✓[/green] Unlinked architect [bold]{arch.name}[/bold] "
        f"from project [bold]{proj.name}[/bold]"
    )


# ─── Preview commands ─────────────────────────────────────────────────────────


@project.group("preview")
@click.pass_context
def preview_group(ctx):
    """Manage preview environments."""
    ctx.ensure_object(dict)


@preview_group.command("list")
@click.pass_context
def preview_list(ctx):
    """List active preview environments."""
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    preview_mgr = PreviewManager(data_dir)

    # Clean up dead previews first
    cleaned = preview_mgr.cleanup_dead_previews()
    if cleaned:
        console.print(f"[dim]Cleaned up {cleaned} dead preview(s).[/dim]")

    previews = preview_mgr.list_previews()
    if not previews:
        console.print("[dim]No active previews.[/dim]")
        return

    table = Table(title="Active Previews")
    table.add_column("Session", style="cyan")
    table.add_column("Port")
    table.add_column("URL")
    table.add_column("PID")
    table.add_column("Alive")

    for p in previews:
        alive = PreviewManager._is_process_alive(p.pid)
        alive_display = "[green]yes[/green]" if alive else "[red]no[/red]"
        table.add_row(
            p.session_id,
            str(p.port),
            p.url,
            str(p.pid),
            alive_display,
        )

    console.print(table)


@preview_group.command("stop")
@click.argument("session_id")
@click.pass_context
def preview_stop(ctx, session_id: str):
    """Stop a specific preview environment."""
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    preview_mgr = PreviewManager(data_dir)

    if preview_mgr.stop_preview(session_id):
        console.print(f"[green]✓[/green] Stopped preview for session [cyan]{session_id}[/cyan]")
    else:
        console.print(f"[yellow]No preview found for session {session_id}[/yellow]")


@preview_group.command("stop-all")
@click.pass_context
def preview_stop_all(ctx):
    """Stop all active preview environments."""
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    preview_mgr = PreviewManager(data_dir)

    previews = preview_mgr.list_previews()
    if not previews:
        console.print("[dim]No active previews.[/dim]")
        return

    stopped = 0
    for p in previews:
        if preview_mgr.stop_preview(p.session_id):
            stopped += 1
            console.print(f"  Stopped preview for session [cyan]{p.session_id}[/cyan]")

    console.print(f"[green]✓[/green] Stopped {stopped} preview(s)")


# ─── CTO commands ────────────────────────────────────────────────────────────


@click.group()
@click.pass_context
def cto(ctx):
    """CTO — AI-powered project advisor."""
    ctx.ensure_object(dict)


@cto.command("chat")
@click.argument("project_id")
@click.option("--clear", is_flag=True, help="Clear conversation history before starting")
@click.pass_context
def cto_chat(ctx, project_id: str, clear: bool):
    """Interactive CTO chat for a project."""
    project_storage, architect_storage, session_manager = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    if clear:
        project_storage.clear_conversation(proj.project_id)
        console.print("[dim]Conversation cleared.[/dim]")

    from beehive.core.cto import CTO

    cto_ai = CTO(proj, project_storage, architect_storage, session_manager)

    console.print(f"[bold]CTO Chat — {proj.name}[/bold]")
    console.print("[dim]Type 'exit' or 'quit' to end. Ctrl+C to abort.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold #FFD700]You:[/bold #FFD700] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Chat ended.[/dim]")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            console.print("[dim]Chat ended.[/dim]")
            break

        if not user_input.strip():
            continue

        try:
            with console.status("[bold green]Thinking..."):
                response = cto_ai.chat(user_input)
            console.print()
            console.print(Markdown(response))
            console.print()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cto.command("brief")
@click.argument("project_id")
@click.option("--raw-only", is_flag=True, help="Show only raw data without AI summary")
@click.pass_context
def cto_brief(ctx, project_id: str, raw_only: bool):
    """Get a project brief with status and AI summary."""
    project_storage, architect_storage, session_manager = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    from beehive.core.cto import CTO

    cto_ai = CTO(proj, project_storage, architect_storage, session_manager)

    if raw_only:
        raw_data = cto_ai._build_project_context()
        console.print(raw_data)
        return

    try:
        with console.status("[bold green]Generating brief..."):
            raw_data, ai_summary = cto_ai.brief()

        console.print("[bold]── Raw Status ──[/bold]\n")
        console.print(raw_data)
        console.print("\n[bold]── Strategic Summary ──[/bold]\n")
        console.print(Markdown(ai_summary))
    except Exception as e:
        console.print(f"[red]Error generating brief: {e}[/red]")
        sys.exit(1)


@cto.command("history")
@click.argument("project_id")
@click.option("--last", "-n", default=20, help="Number of messages to show")
@click.pass_context
def cto_history(ctx, project_id: str, last: int):
    """Show CTO conversation history."""
    project_storage, _, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    conv = project_storage.load_conversation(proj.project_id)

    if not conv.messages:
        console.print("[dim]No conversation history.[/dim]")
        return

    messages = conv.messages[-last:]
    console.print(f"[bold]CTO Conversation — {proj.name}[/bold]")
    console.print(f"[dim]Showing last {len(messages)} of {len(conv.messages)} messages[/dim]\n")

    for msg in messages:
        ts = msg.timestamp.strftime("%m/%d %H:%M")
        if msg.role == "user":
            console.print(f"[dim]{ts}[/dim] [bold #FFD700]You:[/bold #FFD700] {msg.content}")
        else:
            console.print(f"[dim]{ts}[/dim] [bold cyan]CTO:[/bold cyan]")
            console.print(Markdown(msg.content))
        console.print()


@cto.command("clear")
@click.argument("project_id")
@click.pass_context
def cto_clear(ctx, project_id: str):
    """Clear CTO conversation history."""
    project_storage, _, _ = _get_storage(ctx)
    proj = project_storage.load_project(project_id)

    if not proj:
        console.print(f"[red]Project {project_id} not found[/red]")
        sys.exit(1)

    project_storage.clear_conversation(proj.project_id)
    console.print(f"[green]✓[/green] Cleared conversation for [bold]{proj.name}[/bold]")
