"""CLI commands for the Architect feature."""

import json
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


def _build_plan_context(current_ticket, plan) -> Optional[str]:
    """Build plan context string showing previous and future tickets.

    Returns None for single-ticket plans or parallel plans where
    ordering doesn't matter.
    """
    sorted_tickets = sorted(plan.tickets, key=lambda t: t.order)
    if len(sorted_tickets) <= 1:
        return None

    lines = []
    lines.append(f"Plan: {plan.directive}")
    lines.append(f"Execution mode: {plan.execution_mode}")
    lines.append(f"Total tickets: {len(sorted_tickets)}")
    lines.append("")

    current_order = current_ticket.order

    # Previous tickets (completed/merged work)
    previous = [t for t in sorted_tickets if t.order < current_order]
    if previous:
        lines.append("COMPLETED BEFORE YOUR TASK:")
        for t in previous:
            status = str(t.status)
            lines.append(f"  #{t.order}. [{status}] {t.title}")
            lines.append(f"     {t.description}")
            lines.append("")

    # Current ticket marker
    lines.append(f">>> YOUR TASK (#{current_order}): {current_ticket.title}")
    lines.append("")

    # Future tickets (not yet started)
    future = [t for t in sorted_tickets if t.order > current_order]
    if future:
        lines.append("PLANNED AFTER YOUR TASK:")
        for t in future:
            lines.append(f"  #{t.order}. {t.title}")
            lines.append(f"     {t.description}")
            lines.append("")

    lines.append(
        "IMPORTANT: Focus ONLY on your task. Do not implement work "
        "that belongs to previous or future tickets. Keep your scope "
        "limited to exactly what your task describes."
    )

    return "\n".join(lines)


def _assign_single_ticket(ticket, plan, arch, storage, data_dir,
                          session_mgr, tmux, config, docker_mgr,
                          auto_approve, no_docker) -> Optional[str]:
    """Assign a single ticket: create session, worktree, tmux. Returns session_id or None."""
    from beehive.core.git_ops import GitOperations
    from beehive.core.tmux_manager import TmuxManager

    repo_config = next((r for r in arch.repos if r.name == ticket.repo), None)
    if not repo_config:
        console.print(f"[red]Repo '{ticket.repo}' not found in architect config[/red]")
        return None

    repo_path = Path(repo_config.path)
    git = GitOperations(repo_path)
    if not git.is_git_repo():
        console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
        return None

    try:
        use_docker = auto_approve and not no_docker and docker_mgr.is_available()

        # Build plan context for sequential plans so the agent knows
        # what was done before and what comes after its task.
        plan_context = _build_plan_context(ticket, plan)

        instructions = config.combine_prompts(
            ticket.description,
            base_branch=repo_config.base_branch,
            include_deliverable=auto_approve,
            plan_context=plan_context,
        )

        session = session_mgr.create_session(
            name=ticket.title,
            instructions=instructions,
            working_dir=repo_path,
            base_branch=repo_config.base_branch,
            use_docker=use_docker,
        )

        worktree_path = Path(session.working_directory)
        if use_docker:
            git.clone_for_docker(session.branch_name, worktree_path, repo_config.base_branch)
        else:
            git.create_worktree(session.branch_name, worktree_path, repo_config.base_branch)

        project_claude_md = None
        try:
            project = _find_project_for_architect(arch.architect_id, data_dir)
            if project:
                project_storage = ProjectStorage(data_dir)
                project_claude_md = project_storage.get_project_claude_md(
                    project.project_id
                )
        except Exception:
            pass
        config.inject_claude_md(worktree_path, project_claude_md=project_claude_md)

        (worktree_path / ".beehive-system-prompt.txt").write_text(instructions)

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

        tmux.create_session(
            session.tmux_session_name,
            worktree_path,
            Path(session.log_file),
            str(worktree_path),
            None,
            auto_approve=auto_approve,
            docker_command=docker_command,
        )

        ticket.status = TicketStatus.ASSIGNED
        ticket.session_id = session.session_id
        ticket.branch_name = session.branch_name
        ticket.updated_at = datetime.utcnow()
        plan.updated_at = datetime.utcnow()
        storage.save_plan(arch.architect_id, plan)

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
        return session.session_id

    except Exception as e:
        console.print(f"[red]Error assigning '{ticket.title}': {e}[/red]")
        return None


@architect.command("assign")
@click.argument("architect_id")
@click.option("--ticket", "-t", "ticket_id", help="Assign specific ticket by ID")
@click.option("--parallel", is_flag=True, default=False, help="Assign all pending tickets at once")
@click.option("--no-auto-approve", is_flag=True, help="Disable auto-approve (-y)")
@click.option("--no-docker", is_flag=True, help="Force host execution")
@click.pass_context
def assign_tickets(ctx, architect_id: str, ticket_id: Optional[str], parallel: bool, no_auto_approve: bool, no_docker: bool):
    """Assign tickets to beehive agent sessions.

    Default (sequential): assigns only the first pending ticket by order.
    --parallel: assigns all pending tickets at once.
    """
    storage = ctx.obj["architect_storage"]
    arch = storage.load_architect(architect_id)

    if not arch:
        console.print(f"[red]Architect {architect_id} not found[/red]")
        sys.exit(1)

    if not arch.plans:
        console.print("[red]No plans found. Run 'architect plan' first.[/red]")
        sys.exit(1)

    plan = arch.plans[-1]

    if ticket_id:
        result = storage.find_ticket(arch.architect_id, ticket_id)
        if not result:
            console.print(f"[red]Ticket {ticket_id} not found[/red]")
            sys.exit(1)
        plan, ticket = result
        tickets_to_assign = [ticket]
    else:
        pending = [t for t in plan.tickets if t.status == TicketStatus.PENDING]
        pending.sort(key=lambda t: t.order)
        if parallel:
            tickets_to_assign = pending
        else:
            # Sequential: only the first pending ticket by order
            tickets_to_assign = pending[:1]

    if not tickets_to_assign:
        console.print("[dim]No pending tickets to assign.[/dim]")
        return

    # Store execution mode on plan
    plan.execution_mode = "parallel" if parallel else "sequential"
    storage.save_plan(arch.architect_id, plan)

    auto_approve = not no_auto_approve

    from beehive.core.session import SessionManager
    from beehive.core.config import BeehiveConfig
    from beehive.core.docker_manager import DockerManager
    from beehive.core.tmux_manager import TmuxManager

    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    session_mgr = ctx.obj.get("session_manager", SessionManager(data_dir))
    tmux = ctx.obj.get("tmux", TmuxManager())
    config = ctx.obj.get("config", BeehiveConfig(data_dir))
    docker_mgr = ctx.obj.get("docker", DockerManager())

    if not tmux.check_tmux_installed():
        console.print("[red]Error: tmux not found.[/red]")
        sys.exit(1)

    for ticket in tickets_to_assign:
        _assign_single_ticket(
            ticket, plan, arch, storage, data_dir,
            session_mgr, tmux, config, docker_mgr,
            auto_approve, no_docker,
        )


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

    synced = _sync_tickets_from_sessions(plan, session_mgr)
    if synced:
        plan.updated_at = datetime.utcnow()
        storage.save_plan(arch.architect_id, plan)

    # Summary
    counts = {}
    for t in plan.tickets:
        counts[t.status] = counts.get(t.status, 0) + 1

    summary_parts = []
    for status_val in ["pending", "assigned", "in_progress", "completed", "merged", "failed"]:
        count = counts.get(status_val, 0)
        if count > 0:
            summary_parts.append(f"{count} {status_val}")

    console.print(f"\n[bold]Plan {plan.plan_id}[/bold]: {plan.directive}")
    console.print(f"  Status: {', '.join(summary_parts)}\n")

    _print_tickets_table(plan.tickets)


def _find_pr_for_branch(branch_name: str, repo_path: str):
    """Find a PR URL for a given branch via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch_name, "--json", "url", "--limit", "1"],
            capture_output=True, text=True, timeout=15,
            cwd=repo_path,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data:
                return data[0].get("url")
    except Exception:
        pass
    return None


def _check_pr_merged(pr_url: str) -> bool:
    """Check if a GitHub PR is merged via `gh pr view`."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_url, "--json", "state"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("state") == "MERGED"
    except Exception:
        pass
    return False


def _sync_tickets_from_sessions(plan, session_mgr) -> bool:
    """Sync ticket statuses and PR URLs from beehive sessions. Returns True if any changes."""
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
    return synced


@architect.command("watch")
@click.argument("architect_id")
@click.option("--plan", "-p", "plan_id", help="Specific plan ID (defaults to latest)")
@click.option("--interval", "-i", default=15, help="Polling interval in seconds")
@click.pass_context
def watch_plan(ctx, architect_id: str, plan_id: Optional[str], interval: int):
    """Watch plan execution: sync statuses, detect merges, auto-assign next ticket."""
    import time

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

    from beehive.core.session import SessionManager
    from beehive.core.config import BeehiveConfig
    from beehive.core.docker_manager import DockerManager
    from beehive.core.tmux_manager import TmuxManager

    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    session_mgr = ctx.obj.get("session_manager", SessionManager(data_dir))
    tmux = ctx.obj.get("tmux", TmuxManager())
    config = ctx.obj.get("config", BeehiveConfig(data_dir))
    docker_mgr = ctx.obj.get("docker", DockerManager())

    console.print(f"[bold]Watching plan {plan.plan_id}[/bold] (mode: {plan.execution_mode}, interval: {interval}s)")
    console.print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # 0. Auto-complete sessions whose agent process has finished
            session_mgr.auto_complete_sessions()

            # 1. Sync session status → ticket status
            synced = _sync_tickets_from_sessions(plan, session_mgr)

            # 1b. Discover PR URLs for completed tickets missing them
            repo_paths = {r.name: r.path for r in arch.repos}
            for ticket in plan.tickets:
                if ticket.branch_name and not ticket.pr_url and ticket.status not in (
                    TicketStatus.PENDING, TicketStatus.FAILED
                ):
                    repo_path = repo_paths.get(ticket.repo)
                    if repo_path:
                        pr_url = _find_pr_for_branch(ticket.branch_name, repo_path)
                        if pr_url:
                            ticket.pr_url = pr_url
                            ticket.updated_at = datetime.utcnow()
                            synced = True
                            console.print(
                                f"[dim]Discovered PR for {ticket.title}: {pr_url}[/dim]"
                            )

            # 2. Check for merged PRs
            for ticket in plan.tickets:
                if ticket.pr_url and ticket.status in (
                    TicketStatus.COMPLETED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS
                ):
                    if _check_pr_merged(ticket.pr_url):
                        ticket.status = TicketStatus.MERGED
                        ticket.updated_at = datetime.utcnow()
                        synced = True
                        console.print(
                            f"[cyan]✓[/cyan] Ticket [bold]{ticket.title}[/bold] PR merged!"
                        )

            if synced:
                plan.updated_at = datetime.utcnow()
                storage.save_plan(arch.architect_id, plan)

            # 3. In sequential mode: auto-assign next ticket if none in-flight
            if plan.execution_mode == "sequential":
                in_flight = [
                    t for t in plan.tickets
                    if t.status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED)
                ]
                if not in_flight:
                    pending = sorted(
                        [t for t in plan.tickets if t.status == TicketStatus.PENDING],
                        key=lambda t: t.order,
                    )
                    if pending:
                        next_ticket = pending[0]
                        console.print(
                            f"\n[bold]Auto-assigning next ticket:[/bold] #{next_ticket.order} {next_ticket.title}"
                        )
                        _assign_single_ticket(
                            next_ticket, plan, arch, storage, data_dir,
                            session_mgr, tmux, config, docker_mgr,
                            True, False,
                        )

            # 4. Check if all tickets are terminal
            terminal_statuses = {TicketStatus.MERGED, TicketStatus.FAILED}
            all_terminal = all(t.status in terminal_statuses for t in plan.tickets)
            if all_terminal:
                console.print("\n[green bold]All tickets are terminal (merged or failed). Done![/green bold]")
                _print_tickets_table(plan.tickets)
                break

            # Show brief status
            counts = {}
            for t in plan.tickets:
                counts[t.status] = counts.get(t.status, 0) + 1
            parts = [f"{v} {k}" for k, v in counts.items()]
            console.print(f"[dim]{', '.join(parts)}[/dim]")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")
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
    table.add_column("#", style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Repo")
    table.add_column("Status")
    table.add_column("Branch", style="dim")
    table.add_column("Session", style="dim")
    table.add_column("PR", style="dim")

    status_colors = {
        "pending": "yellow",
        "assigned": "blue",
        "in_progress": "green",
        "completed": "green",
        "failed": "red",
        "merged": "cyan",
    }

    sorted_tickets = sorted(tickets, key=lambda t: t.order)
    for t in sorted_tickets:
        color = status_colors.get(t.status, "white")
        table.add_row(
            str(t.order) if t.order else "—",
            t.ticket_id,
            t.title,
            t.repo,
            f"[{color}]{t.status}[/{color}]",
            t.branch_name or "",
            t.session_id or "",
            t.pr_url or "",
        )

    console.print(table)
