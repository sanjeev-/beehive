"""CLI commands for the Architect feature."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.table import Table

from beehive.core.architect import Architect, ArchitectRepo, TicketStatus
from beehive.core.architect_storage import ArchitectStorage
from beehive.core.project_storage import ProjectStorage

console = Console()


@click.group()
@click.pass_context
def architect(ctx):
    """Manage architects, plans, and tickets."""
    ctx.ensure_object(dict)
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    ctx.obj["architect_storage"] = ArchitectStorage(data_dir)


@architect.command("list")
@click.pass_context
def list_architects(ctx):
    """List all architects."""
    storage = ctx.obj["architect_storage"]
    architects = storage.load_all_architects()

    if not architects:
        console.print("[dim]No architects found.[/dim]")
        return

    table = Table(title="Architects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Repos")
    table.add_column("Plans")
    table.add_column("Created")

    for a in architects:
        repo_names = ", ".join(r.name for r in a.repos)
        table.add_row(
            a.architect_id,
            a.name,
            repo_names,
            str(len(a.plans)),
            a.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@architect.command("create")
@click.argument("name")
@click.option(
    "--config",
    "-c",
    "config_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="YAML config file for the architect",
)
@click.pass_context
def create_architect(ctx, name: str, config_file: Path):
    """Create a new architect from a YAML config file."""
    storage = ctx.obj["architect_storage"]

    # Parse YAML
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Build repos
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

    if not repos:
        console.print("[red]Error: No repos defined in config.[/red]")
        sys.exit(1)

    # Use name from CLI arg, but allow YAML to provide principles
    arch = Architect(
        name=name,
        principles=config.get("principles", ""),
        repos=repos,
    )

    storage.save_architect(arch)

    console.print(f"[green]✓[/green] Created architect: [bold]{arch.name}[/bold]")
    console.print(f"  ID: [cyan]{arch.architect_id}[/cyan]")
    console.print(f"  Repos: {', '.join(r.name for r in repos)}")


@architect.command("show")
@click.argument("architect_id")
@click.pass_context
def show_architect(ctx, architect_id: str):
    """Show architect details."""
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Architect: {arch.name}[/bold]")
    console.print(f"  ID: [cyan]{arch.architect_id}[/cyan]")
    console.print(f"  Created: {arch.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"\n[bold]Principles:[/bold]")
    console.print(f"  {arch.principles}")
    console.print(f"\n[bold]Repos:[/bold]")
    for r in arch.repos:
        desc = f" - {r.description}" if r.description else ""
        console.print(f"  [cyan]{r.name}[/cyan]: {r.path} (base: {r.base_branch}){desc}")
    console.print(f"\n[bold]Plans:[/bold] {len(arch.plans)}")
    for p in arch.plans:
        console.print(
            f"  [cyan]{p.plan_id}[/cyan]: {p.directive[:60]} "
            f"({len(p.tickets)} tickets)"
        )


@architect.command("plan")
@click.argument("architect_id")
@click.option("--directive", "-d", required=True, help="High-level directive to plan")
@click.pass_context
def create_plan(ctx, architect_id: str, directive: str):
    """Generate a plan from a directive using Claude."""
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    from beehive.core.planner import Planner

    planner = Planner(arch)

    try:
        with console.status("[bold green]Generating plan..."):
            plan = planner.generate_plan(directive)
    except Exception as e:
        console.print(f"[red]Error generating plan: {e}[/red]")
        sys.exit(1)

    # Save plan
    storage.save_plan(arch.architect_id, plan)

    # Display tickets
    console.print(f"\n[green]✓[/green] Plan created: [cyan]{plan.plan_id}[/cyan]")
    console.print(f"  Directive: {plan.directive}")
    console.print(f"  Tickets: {len(plan.tickets)}\n")

    _print_tickets_table(plan.tickets)


@architect.command("tickets")
@click.argument("architect_id")
@click.argument("plan_id", required=False)
@click.pass_context
def list_tickets(ctx, architect_id: str, plan_id: Optional[str]):
    """List tickets for an architect's plan."""
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if plan_id:
        plan = storage.load_plan(arch.architect_id, plan_id)
        if not plan:
            console.print(f"[red]Plan {plan_id} not found[/red]")
            sys.exit(1)
    else:
        # Use latest plan
        plans = arch.plans
        if not plans:
            console.print("[dim]No plans found for this architect.[/dim]")
            return
        plan = plans[-1]

    console.print(f"[bold]Plan {plan.plan_id}[/bold]: {plan.directive}\n")
    _print_tickets_table(plan.tickets)


@architect.command("edit-ticket")
@click.argument("ticket_id")
@click.option("--title", "-t", help="New title")
@click.option("--description", "-d", help="New description")
@click.option("--repo", "-r", help="New repo")
@click.pass_context
def edit_ticket(ctx, ticket_id: str, title: Optional[str], description: Optional[str], repo: Optional[str]):
    """Edit a ticket's fields."""
    storage = ctx.obj["architect_storage"]

    result = storage.find_ticket_globally(ticket_id)
    if not result:
        console.print(f"[red]Ticket {ticket_id} not found[/red]")
        sys.exit(1)

    arch, plan, ticket = result

    if title:
        ticket.title = title
    if description:
        ticket.description = description
    if repo:
        # Validate repo name
        valid_repos = {r.name for r in arch.repos}
        if repo not in valid_repos:
            console.print(f"[red]Invalid repo '{repo}'. Valid: {', '.join(valid_repos)}[/red]")
            sys.exit(1)
        ticket.repo = repo

    ticket.updated_at = datetime.utcnow()
    plan.updated_at = datetime.utcnow()
    storage.save_plan(arch.architect_id, plan)

    console.print(f"[green]✓[/green] Updated ticket [cyan]{ticket.ticket_id}[/cyan]")


@architect.command("assign")
@click.argument("architect_id")
@click.option("--ticket", "-t", "ticket_id", help="Assign specific ticket by ID")
@click.option("--all", "-a", "assign_all", is_flag=True, default=True, help="Assign all pending tickets (default)")
@click.option("--no-auto-approve", is_flag=True, help="Disable auto-approve (-y)")
@click.option("--no-docker", is_flag=True, help="Force host execution")
@click.pass_context
def assign_tickets(ctx, architect_id: str, ticket_id: Optional[str], assign_all: bool, no_auto_approve: bool, no_docker: bool):
    """Assign tickets to beehive agent sessions."""
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if not arch.plans:
        console.print("[red]No plans found. Run 'architect plan' first.[/red]")
        sys.exit(1)

    # Get the latest plan
    plan = arch.plans[-1]

    # Determine which tickets to assign
    if ticket_id:
        result = storage.find_ticket(arch.architect_id, ticket_id)
        if not result:
            console.print(f"[red]Ticket {ticket_id} not found[/red]")
            sys.exit(1)
        plan, ticket = result
        tickets_to_assign = [ticket]
    else:
        # Assign all pending tickets
        tickets_to_assign = [t for t in plan.tickets if t.status == TicketStatus.PENDING]

    if not tickets_to_assign:
        console.print("[dim]No pending tickets to assign.[/dim]")
        return

    auto_approve = not no_auto_approve

    # Import session management
    from beehive.core.session import SessionManager
    from beehive.core.git_ops import GitOperations
    from beehive.core.tmux_manager import TmuxManager
    from beehive.core.config import BeehiveConfig
    from beehive.core.docker_manager import DockerManager

    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    session_mgr = ctx.obj.get("session_manager", SessionManager(data_dir))
    tmux = ctx.obj.get("tmux", TmuxManager())
    config = ctx.obj.get("config", BeehiveConfig(data_dir))
    docker_mgr = ctx.obj.get("docker", DockerManager())

    if not tmux.check_tmux_installed():
        console.print("[red]Error: tmux not found.[/red]")
        sys.exit(1)

    for ticket in tickets_to_assign:
        # Find repo config
        repo_config = next((r for r in arch.repos if r.name == ticket.repo), None)
        if not repo_config:
            console.print(f"[red]Repo '{ticket.repo}' not found in architect config[/red]")
            continue

        repo_path = Path(repo_config.path)
        git = GitOperations(repo_path)
        if not git.is_git_repo():
            console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
            continue

        try:
            # Determine whether to use Docker
            use_docker = auto_approve and not no_docker and docker_mgr.is_available()

            # Combine instructions with global prompt
            instructions = config.combine_prompts(
                ticket.description,
                base_branch=repo_config.base_branch,
                include_deliverable=auto_approve,
            )

            # Create session
            session = session_mgr.create_session(
                name=ticket.title,
                instructions=instructions,
                working_dir=repo_path,
                base_branch=repo_config.base_branch,
                use_docker=use_docker,
            )

            # Create isolated workspace
            worktree_path = Path(session.working_directory)
            if use_docker:
                git.clone_for_docker(session.branch_name, worktree_path, repo_config.base_branch)
            else:
                git.create_worktree(session.branch_name, worktree_path, repo_config.base_branch)

            # Inject CLAUDE.md
            config.inject_claude_md(worktree_path)

            # Write prompt files
            (worktree_path / ".beehive-system-prompt.txt").write_text(instructions)

            # Prepare Docker gitconfig
            if use_docker:
                git_name = subprocess.run(
                    ["git", "config", "user.name"],
                    capture_output=True, text=True,
                ).stdout.strip() or "Beehive Agent"
                git_email = subprocess.run(
                    ["git", "config", "user.email"],
                    capture_output=True, text=True,
                ).stdout.strip() or "agent@beehive"
                (worktree_path / ".beehive-gitconfig").write_text(
                    f"[user]\n\tname = {git_name}\n\temail = {git_email}\n"
                )

            # Build docker command if using Docker
            docker_command = None
            if use_docker:
                if not docker_mgr.ensure_image():
                    console.print(f"[yellow]Warning: Docker image build failed, falling back to host for {ticket.title}[/yellow]")
                    use_docker = False
                    session_mgr.update_session(
                        session.session_id,
                        container_name=None,
                        runtime="host",
                    )
                else:
                    claude_cmd = TmuxManager._build_claude_command(
                        "/workspace",
                        has_initial_prompt=False,
                        auto_approve=auto_approve,
                    )
                    docker_command = docker_mgr.build_run_command(
                        session.session_id, worktree_path, claude_cmd
                    )

            # Start tmux session
            tmux.create_session(
                session.tmux_session_name,
                worktree_path,
                Path(session.log_file),
                str(worktree_path),
                None,  # no initial prompt
                auto_approve=auto_approve,
                docker_command=docker_command,
            )

            # Update ticket
            ticket.status = TicketStatus.ASSIGNED
            ticket.session_id = session.session_id
            ticket.updated_at = datetime.utcnow()
            plan.updated_at = datetime.utcnow()
            storage.save_plan(arch.architect_id, plan)

            # Auto-start preview if project has preview config
            try:
                project = _find_project_for_architect(arch.architect_id, data_dir)
                if project and project.preview:
                    from beehive.core.preview import PreviewManager

                    preview_mgr = PreviewManager(data_dir)
                    preview_url = preview_mgr.start_preview(
                        session_id=session.session_id,
                        task_name=ticket.title,
                        working_directory=str(worktree_path),
                        setup_command=project.preview.setup_command,
                        teardown_command=project.preview.teardown_command,
                        url_template=project.preview.url_template,
                        startup_timeout=project.preview.startup_timeout,
                    )
                    session_mgr.update_session(session.session_id, preview_url=preview_url)
                    console.print(f"  Preview: [cyan]{preview_url}[/cyan]")
            except Exception as e:
                console.print(f"  [yellow]Warning: Preview failed: {e}[/yellow]")

            runtime_label = "docker" if use_docker else "host"
            console.print(
                f"[green]✓[/green] Assigned [bold]{ticket.title}[/bold] "
                f"-> session [cyan]{session.session_id}[/cyan] ({runtime_label})"
            )

        except Exception as e:
            console.print(f"[red]Error assigning '{ticket.title}': {e}[/red]")
            continue


@architect.command("status")
@click.argument("architect_id")
@click.argument("plan_id", required=False)
@click.pass_context
def plan_status(ctx, architect_id: str, plan_id: Optional[str]):
    """Sync ticket statuses from sessions and show plan progress."""
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if plan_id:
        plan = storage.load_plan(arch.architect_id, plan_id)
        if not plan:
            console.print(f"[red]Plan {plan_id} not found[/red]")
            sys.exit(1)
    else:
        if not arch.plans:
            console.print("[dim]No plans found.[/dim]")
            return
        plan = arch.plans[-1]

    # Sync ticket statuses from beehive sessions
    from beehive.core.session import SessionManager

    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    session_mgr = ctx.obj.get("session_manager", SessionManager(data_dir))

    synced = False
    for ticket in plan.tickets:
        if ticket.status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS) and ticket.session_id:
            session = session_mgr.get_session(ticket.session_id)
            if not session:
                continue

            if session.status == "completed":
                ticket.status = TicketStatus.COMPLETED
                ticket.updated_at = datetime.utcnow()
                synced = True
            elif session.status in ("failed", "stopped"):
                ticket.status = TicketStatus.FAILED
                ticket.updated_at = datetime.utcnow()
                synced = True

            if session.pr_url and not ticket.pr_url:
                ticket.pr_url = session.pr_url
                ticket.updated_at = datetime.utcnow()
                synced = True

    if synced:
        plan.updated_at = datetime.utcnow()
        storage.save_plan(arch.architect_id, plan)

    # Summary
    counts = {}
    for t in plan.tickets:
        counts[t.status] = counts.get(t.status, 0) + 1

    summary_parts = []
    for status_val in ["pending", "assigned", "in_progress", "completed", "failed"]:
        count = counts.get(status_val, 0)
        if count > 0:
            summary_parts.append(f"{count} {status_val}")

    console.print(f"\n[bold]Plan {plan.plan_id}[/bold]: {plan.directive}")
    console.print(f"  Status: {', '.join(summary_parts)}\n")

    _print_tickets_table(plan.tickets)


def _find_project_for_architect(architect_id: str, data_dir: Path):
    """Scan all projects for one that has this architect linked."""
    project_storage = ProjectStorage(data_dir)
    for proj in project_storage.load_all_projects():
        if architect_id in proj.architect_ids:
            return proj
    return None


def _print_tickets_table(tickets):
    """Print a Rich table of tickets."""
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Repo")
    table.add_column("Status")
    table.add_column("Session", style="dim")
    table.add_column("PR", style="dim")

    status_colors = {
        "pending": "yellow",
        "assigned": "blue",
        "in_progress": "green",
        "completed": "green",
        "failed": "red",
    }

    for t in tickets:
        color = status_colors.get(t.status, "white")
        table.add_row(
            t.ticket_id,
            t.title,
            t.repo,
            f"[{color}]{t.status}[/{color}]",
            t.session_id or "",
            t.pr_url or "",
        )

    console.print(table)
