"""CLI commands for the Researcher feature."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.table import Table

from beehive.core.architect import ArchitectRepo
from beehive.core.project_storage import ProjectStorage
from beehive.core.researcher import ExperimentStatus, Researcher
from beehive.core.researcher_storage import ResearcherStorage

console = Console()


@click.group()
@click.pass_context
def researcher(ctx):
    """Manage researchers, studies, and experiments."""
    ctx.ensure_object(dict)
    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    ctx.obj["researcher_storage"] = ResearcherStorage(data_dir)


@researcher.command("list")
@click.pass_context
def list_researchers(ctx):
    """List all researchers."""
    storage = ctx.obj["researcher_storage"]
    researchers = storage.load_all_researchers()

    if not researchers:
        console.print("[dim]No researchers found.[/dim]")
        return

    table = Table(title="Researchers")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Repos")
    table.add_column("Studies")
    table.add_column("Created")

    for r in researchers:
        repo_names = ", ".join(repo.name for repo in r.repos)
        table.add_row(
            r.researcher_id,
            r.name,
            repo_names,
            str(len(r.studies)),
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@researcher.command("create")
@click.argument("name")
@click.option(
    "--config",
    "-c",
    "config_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="YAML config file for the researcher",
)
@click.pass_context
def create_researcher(ctx, name: str, config_file: Path):
    """Create a new researcher from a YAML config file."""
    storage = ctx.obj["researcher_storage"]

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

    res = Researcher(
        name=name,
        principles=config.get("principles", ""),
        repos=repos,
    )

    storage.save_researcher(res)

    console.print(f"[green]\u2713[/green] Created researcher: [bold]{res.name}[/bold]")
    console.print(f"  ID: [cyan]{res.researcher_id}[/cyan]")
    console.print(f"  Repos: {', '.join(r.name for r in repos)}")


@researcher.command("show")
@click.argument("researcher_id")
@click.pass_context
def show_researcher(ctx, researcher_id: str):
    """Show researcher details."""
    storage = ctx.obj["researcher_storage"]
    res = storage.load_researcher(researcher_id)

    if not res:
        console.print(f"[red]Researcher {researcher_id} not found[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Researcher: {res.name}[/bold]")
    console.print(f"  ID: [cyan]{res.researcher_id}[/cyan]")
    console.print(f"  Created: {res.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"\n[bold]Principles:[/bold]")
    console.print(f"  {res.principles}")
    console.print(f"\n[bold]Repos:[/bold]")
    for r in res.repos:
        desc = f" - {r.description}" if r.description else ""
        console.print(f"  [cyan]{r.name}[/cyan]: {r.path} (base: {r.base_branch}){desc}")
    console.print(f"\n[bold]Studies:[/bold] {len(res.studies)}")
    for s in res.studies:
        console.print(
            f"  [cyan]{s.study_id}[/cyan]: {s.directive[:60]} "
            f"({len(s.experiments)} experiments)"
        )


@researcher.command("study")
@click.argument("researcher_id")
@click.option("--directive", "-d", required=True, help="High-level research directive")
@click.pass_context
def create_study(ctx, researcher_id: str, directive: str):
    """Generate a study from a directive using Claude."""
    storage = ctx.obj["researcher_storage"]
    res = storage.load_researcher(researcher_id)

    if not res:
        console.print(f"[red]Researcher {researcher_id} not found[/red]")
        sys.exit(1)

    from beehive.core.research_planner import ResearchPlanner

    planner = ResearchPlanner(res)

    try:
        with console.status("[bold green]Generating study..."):
            study = planner.generate_study(directive)
    except Exception as e:
        console.print(f"[red]Error generating study: {e}[/red]")
        sys.exit(1)

    # Save study
    storage.save_study(res.researcher_id, study)

    # Display experiments
    console.print(f"\n[green]\u2713[/green] Study created: [cyan]{study.study_id}[/cyan]")
    console.print(f"  Directive: {study.directive}")
    console.print(f"  Experiments: {len(study.experiments)}\n")

    _print_experiments_table(study.experiments)


@researcher.command("experiments")
@click.argument("researcher_id")
@click.argument("study_id", required=False)
@click.pass_context
def list_experiments(ctx, researcher_id: str, study_id: Optional[str]):
    """List experiments for a researcher's study."""
    storage = ctx.obj["researcher_storage"]
    res = storage.load_researcher(researcher_id)

    if not res:
        console.print(f"[red]Researcher {researcher_id} not found[/red]")
        sys.exit(1)

    if study_id:
        study = storage.load_study(res.researcher_id, study_id)
        if not study:
            console.print(f"[red]Study {study_id} not found[/red]")
            sys.exit(1)
    else:
        # Use latest study
        studies = res.studies
        if not studies:
            console.print("[dim]No studies found for this researcher.[/dim]")
            return
        study = studies[-1]

    console.print(f"[bold]Study {study.study_id}[/bold]: {study.directive}\n")
    _print_experiments_table(study.experiments)


@researcher.command("edit-experiment")
@click.argument("experiment_id")
@click.option("--title", "-t", help="New title")
@click.option("--description", "-d", help="New description")
@click.option("--repo", "-r", help="New repo")
@click.pass_context
def edit_experiment(ctx, experiment_id: str, title: Optional[str], description: Optional[str], repo: Optional[str]):
    """Edit an experiment's fields."""
    storage = ctx.obj["researcher_storage"]

    result = storage.find_experiment_globally(experiment_id)
    if not result:
        console.print(f"[red]Experiment {experiment_id} not found[/red]")
        sys.exit(1)

    res, study, experiment = result

    if title:
        experiment.title = title
    if description:
        experiment.description = description
    if repo:
        # Validate repo name
        valid_repos = {r.name for r in res.repos}
        if repo not in valid_repos:
            console.print(f"[red]Invalid repo '{repo}'. Valid: {', '.join(valid_repos)}[/red]")
            sys.exit(1)
        experiment.repo = repo

    experiment.updated_at = datetime.utcnow()
    study.updated_at = datetime.utcnow()
    storage.save_study(res.researcher_id, study)

    console.print(f"[green]\u2713[/green] Updated experiment [cyan]{experiment.experiment_id}[/cyan]")


@researcher.command("assign")
@click.argument("researcher_id")
@click.option("--experiment", "-e", "experiment_id", help="Assign specific experiment by ID")
@click.option("--all", "-a", "assign_all", is_flag=True, default=True, help="Assign all pending experiments (default)")
@click.option("--no-auto-approve", is_flag=True, help="Disable auto-approve (-y)")
@click.option("--no-docker", is_flag=True, help="Force host execution")
@click.pass_context
def assign_experiments(ctx, researcher_id: str, experiment_id: Optional[str], assign_all: bool, no_auto_approve: bool, no_docker: bool):
    """Assign experiments to beehive agent sessions."""
    storage = ctx.obj["researcher_storage"]
    res = storage.load_researcher(researcher_id)

    if not res:
        console.print(f"[red]Researcher {researcher_id} not found[/red]")
        sys.exit(1)

    if not res.studies:
        console.print("[red]No studies found. Run 'researcher study' first.[/red]")
        sys.exit(1)

    # Get the latest study
    study = res.studies[-1]

    # Determine which experiments to assign
    if experiment_id:
        result = storage.find_experiment(res.researcher_id, experiment_id)
        if not result:
            console.print(f"[red]Experiment {experiment_id} not found[/red]")
            sys.exit(1)
        study, experiment = result
        experiments_to_assign = [experiment]
    else:
        # Assign all pending experiments
        experiments_to_assign = [e for e in study.experiments if e.status == ExperimentStatus.PENDING]

    if not experiments_to_assign:
        console.print("[dim]No pending experiments to assign.[/dim]")
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

    for experiment in experiments_to_assign:
        # Find repo config
        repo_config = next((r for r in res.repos if r.name == experiment.repo), None)
        if not repo_config:
            console.print(f"[red]Repo '{experiment.repo}' not found in researcher config[/red]")
            continue

        repo_path = Path(repo_config.path)
        git = GitOperations(repo_path)
        if not git.is_git_repo():
            console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
            continue

        try:
            # Determine whether to use Docker
            use_docker = auto_approve and not no_docker and docker_mgr.is_available()

            # Combine instructions with global prompt (research deliverable)
            instructions = config.combine_research_prompts(
                experiment.description,
                include_deliverable=auto_approve,
            )

            # Create session
            session = session_mgr.create_session(
                name=experiment.title,
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
                    console.print(f"[yellow]Warning: Docker image build failed, falling back to host for {experiment.title}[/yellow]")
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

            # Update experiment
            experiment.status = ExperimentStatus.ASSIGNED
            experiment.session_id = session.session_id
            experiment.updated_at = datetime.utcnow()
            study.updated_at = datetime.utcnow()
            storage.save_study(res.researcher_id, study)

            # Auto-start preview if project has preview config
            try:
                project = _find_project_for_researcher(res, data_dir)
                if project and project.preview:
                    from beehive.core.preview import PreviewManager

                    preview_mgr = PreviewManager(data_dir)
                    preview_url = preview_mgr.start_preview(
                        session_id=session.session_id,
                        task_name=experiment.title,
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
                f"[green]\u2713[/green] Assigned [bold]{experiment.title}[/bold] "
                f"-> session [cyan]{session.session_id}[/cyan] ({runtime_label})"
            )

        except Exception as e:
            console.print(f"[red]Error assigning '{experiment.title}': {e}[/red]")
            continue


@researcher.command("status")
@click.argument("researcher_id")
@click.argument("study_id", required=False)
@click.pass_context
def study_status(ctx, researcher_id: str, study_id: Optional[str]):
    """Sync experiment statuses from sessions and show study progress."""
    storage = ctx.obj["researcher_storage"]
    res = storage.load_researcher(researcher_id)

    if not res:
        console.print(f"[red]Researcher {researcher_id} not found[/red]")
        sys.exit(1)

    if study_id:
        study = storage.load_study(res.researcher_id, study_id)
        if not study:
            console.print(f"[red]Study {study_id} not found[/red]")
            sys.exit(1)
    else:
        if not res.studies:
            console.print("[dim]No studies found.[/dim]")
            return
        study = res.studies[-1]

    # Sync experiment statuses from beehive sessions
    from beehive.core.session import SessionManager

    data_dir = ctx.obj.get("data_dir", Path.home() / ".beehive")
    session_mgr = ctx.obj.get("session_manager", SessionManager(data_dir))

    synced = False
    for experiment in study.experiments:
        if experiment.status in (ExperimentStatus.ASSIGNED, ExperimentStatus.IN_PROGRESS) and experiment.session_id:
            session = session_mgr.get_session(experiment.session_id)
            if not session:
                continue

            if session.status == "completed":
                experiment.status = ExperimentStatus.COMPLETED
                experiment.updated_at = datetime.utcnow()
                synced = True
            elif session.status in ("failed", "stopped"):
                experiment.status = ExperimentStatus.FAILED
                experiment.updated_at = datetime.utcnow()
                synced = True

            if not experiment.output_dir and session.working_directory:
                experiment.output_dir = session.working_directory
                experiment.updated_at = datetime.utcnow()
                synced = True

    if synced:
        study.updated_at = datetime.utcnow()
        storage.save_study(res.researcher_id, study)

    # Summary
    counts = {}
    for e in study.experiments:
        counts[e.status] = counts.get(e.status, 0) + 1

    summary_parts = []
    for status_val in ["pending", "assigned", "in_progress", "completed", "failed"]:
        count = counts.get(status_val, 0)
        if count > 0:
            summary_parts.append(f"{count} {status_val}")

    console.print(f"\n[bold]Study {study.study_id}[/bold]: {study.directive}")
    console.print(f"  Status: {', '.join(summary_parts)}\n")

    _print_experiments_table(study.experiments)


def _find_project_for_researcher(researcher, data_dir: Path):
    """Find a project whose repos overlap with this researcher's repos."""
    project_storage = ProjectStorage(data_dir)
    researcher_paths = {r.path for r in researcher.repos}
    for proj in project_storage.load_all_projects():
        proj_paths = {r.path for r in proj.repos}
        if researcher_paths & proj_paths:
            return proj
    return None


def _print_experiments_table(experiments):
    """Print a Rich table of experiments."""
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Repo")
    table.add_column("Status")
    table.add_column("Session", style="dim")
    table.add_column("Output", style="dim")

    status_colors = {
        "pending": "yellow",
        "assigned": "blue",
        "in_progress": "green",
        "completed": "green",
        "failed": "red",
    }

    for e in experiments:
        color = status_colors.get(e.status, "white")
        table.add_row(
            e.experiment_id,
            e.title,
            e.repo,
            f"[{color}]{e.status}[/{color}]",
            e.session_id or "",
            e.output_dir or "",
        )

    console.print(table)
