"""Click-based CLI interface for Beehive."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from beehive.core.git_ops import GitOperations
from beehive.core.pr_creator import PRCreator
from beehive.core.session import SessionManager, SessionStatus
from beehive.core.tmux_manager import TmuxManager
from beehive.core.config import BeehiveConfig
from beehive.core.docker_manager import DockerManager

console = Console()


@click.group()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=Path.home() / ".beehive",
    help="Data directory for Beehive sessions",
)
@click.pass_context
def cli(ctx, data_dir: Path):
    """Beehive - Manage multiple Claude Code agent sessions."""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["session_manager"] = SessionManager(data_dir)
    ctx.obj["tmux"] = TmuxManager()
    ctx.obj["config"] = BeehiveConfig(data_dir)
    ctx.obj["docker"] = DockerManager()


@cli.command()
@click.argument("name")
@click.option(
    "--instructions",
    "-i",
    required=True,
    help="Instructions for agent (string or @file)",
)
@click.option(
    "--working-dir",
    "-w",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Working directory (default: current directory)",
)
@click.option("--base-branch", "-b", default="main", help="Base branch (default: main)")
@click.option("--prompt", "-p", help="Initial prompt to send to agent")
@click.option(
    "--auto-approve",
    "-y",
    is_flag=True,
    help="Auto-approve all agent actions (skip permission prompts)",
)
@click.option(
    "--claude-md",
    type=click.Path(exists=True, path_type=Path),
    help="Project-specific CLAUDE.md file (merged with global template)",
)
@click.option(
    "--no-docker",
    is_flag=True,
    help="Force host execution even when Docker is available",
)
@click.pass_context
def create(
    ctx,
    name: str,
    instructions: str,
    working_dir: Path,
    base_branch: str,
    prompt: Optional[str],
    auto_approve: bool,
    claude_md: Optional[Path],
    no_docker: bool,
):
    """Create a new agent session."""
    # Check tmux
    if not ctx.obj["tmux"].check_tmux_installed():
        console.print(
            "[red]Error: tmux not found. Please install tmux first.[/red]"
        )
        console.print("  macOS: brew install tmux")
        console.print("  Ubuntu: sudo apt-get install tmux")
        sys.exit(1)

    # Check if git repo
    git = GitOperations(working_dir)
    if not git.is_git_repo():
        console.print(f"[red]Error: {working_dir} is not a git repository.[/red]")
        sys.exit(1)

    # Parse instructions (file or string)
    if instructions.startswith("@"):
        instruction_file = Path(instructions[1:])
        if not instruction_file.exists():
            console.print(f"[red]Error: Instruction file not found: {instruction_file}[/red]")
            sys.exit(1)
        instructions = instruction_file.read_text()

    # Determine whether to use Docker
    docker_mgr = ctx.obj["docker"]
    use_docker = auto_approve and not no_docker and docker_mgr.is_available()

    # Combine with global system prompt (include deliverable instructions for auto-approve)
    config = ctx.obj["config"]
    instructions = config.combine_prompts(
        instructions,
        base_branch=base_branch,
        include_deliverable=auto_approve,
    )

    # Parse prompt (file or string)
    if prompt and prompt.startswith("@"):
        prompt_file = Path(prompt[1:])
        if not prompt_file.exists():
            console.print(f"[red]Error: Prompt file not found: {prompt_file}[/red]")
            sys.exit(1)
        prompt = prompt_file.read_text()

    # Create session
    session_mgr = ctx.obj["session_manager"]

    try:
        with console.status("[bold green]Creating session..."):
            session = session_mgr.create_session(
                name, instructions, working_dir, base_branch,
                use_docker=use_docker,
            )

            # Create isolated workspace
            worktree_path = Path(session.working_directory)
            if use_docker:
                # Docker: clone repo (worktrees use host paths that break in containers)
                git.clone_for_docker(session.branch_name, worktree_path, base_branch)
            else:
                # Host: use git worktree (faster, shares .git)
                git.create_worktree(session.branch_name, worktree_path, base_branch)

            # Copy project-specific CLAUDE.md into worktree, then
            # prepend global template on top (merge)
            if claude_md:
                import shutil
                shutil.copy2(claude_md, worktree_path / "CLAUDE.md")
            config.inject_claude_md(worktree_path)

            # Write prompt files to worktree (avoids command-line quoting issues)
            (worktree_path / ".beehive-system-prompt.txt").write_text(instructions)
            if auto_approve and prompt:
                (worktree_path / ".beehive-prompt.txt").write_text(prompt)

            # Prepare Docker-specific gitconfig (writable, with user identity)
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
                    console.print("[yellow]Warning: Failed to build Docker image, falling back to host.[/yellow]")
                    use_docker = False
                    session_mgr.update_session(
                        session.session_id,
                        container_name=None,
                        runtime="host",
                    )
                else:
                    claude_cmd = TmuxManager._build_claude_command(
                        "/workspace",
                        has_initial_prompt=bool(prompt),
                        auto_approve=auto_approve,
                    )
                    docker_command = docker_mgr.build_run_command(
                        session.session_id, worktree_path, claude_cmd
                    )

            # Start tmux session in the worktree directory
            ctx.obj["tmux"].create_session(
                session.tmux_session_name,
                worktree_path,
                Path(session.log_file),
                str(worktree_path),
                prompt,
                auto_approve=auto_approve,
                docker_command=docker_command,
            )

        runtime_label = "[magenta]Docker[/magenta]" if use_docker else "[dim]Host[/dim]"
        console.print(f"[green]✓[/green] Created session: [bold]{session.name}[/bold]")
        console.print(f"  ID: [cyan]{session.session_id}[/cyan]")
        console.print(f"  Branch: [yellow]{session.branch_name}[/yellow]")
        console.print(f"  Runtime: {runtime_label}")
        console.print(f"  Worktree: [dim]{session.working_directory}[/dim]")
        console.print(f"  Logs: [dim]{session.log_file}[/dim]")
        console.print(
            f"\nAttach: [cyan]beehive attach {session.session_id}[/cyan]"
        )
        console.print(f"View logs: [cyan]beehive logs {session.session_id} -f[/cyan]")

    except Exception as e:
        console.print(f"[red]Error creating session: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--status",
    "-s",
    type=click.Choice(["running", "completed", "failed", "stopped"]),
    help="Filter by status",
)
@click.pass_context
def list(ctx, status: Optional[str]):
    """List all agent sessions."""
    session_mgr = ctx.obj["session_manager"]
    status_filter = SessionStatus(status) if status else None
    sessions = session_mgr.list_sessions(status_filter)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Beehive Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Runtime")
    table.add_column("Branch", style="dim")
    table.add_column("Created")

    for s in sessions:
        status_color = {
            "running": "green",
            "completed": "blue",
            "failed": "red",
            "stopped": "yellow",
        }.get(s.status, "white")

        runtime_display = (
            f"[magenta]docker[/magenta]" if s.runtime == "docker"
            else f"[dim]host[/dim]"
        )

        table.add_row(
            s.session_id,
            s.name,
            f"[{status_color}]{s.status}[/{status_color}]",
            runtime_display,
            s.branch_name,
            s.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@cli.command()
@click.argument("session_id")
@click.pass_context
def attach(ctx, session_id: str):
    """Attach to agent's tmux session (interactive)."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    if not ctx.obj["tmux"].session_exists(session.tmux_session_name):
        console.print(f"[red]tmux session {session.tmux_session_name} not found[/red]")
        console.print("[dim]The session may have been stopped.[/dim]")
        sys.exit(1)

    console.print(f"Attaching to [bold]{session.name}[/bold]...")
    console.print("[dim]Press Ctrl+B then D to detach[/dim]\n")
    ctx.obj["tmux"].attach_session(session.tmux_session_name)


@cli.command()
@click.argument("session_id")
@click.argument("text")
@click.pass_context
def send(ctx, session_id: str, text: str):
    """Send a prompt to the agent."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    if not ctx.obj["tmux"].session_exists(session.tmux_session_name):
        console.print(f"[red]tmux session {session.tmux_session_name} not found[/red]")
        sys.exit(1)

    # Parse @file syntax
    if text.startswith("@"):
        text_file = Path(text[1:])
        if not text_file.exists():
            console.print(f"[red]Error: File not found: {text_file}[/red]")
            sys.exit(1)
        text = text_file.read_text()

    ctx.obj["tmux"].send_keys(session.tmux_session_name, text)
    console.print(f"[green]✓[/green] Sent prompt to [bold]{session.name}[/bold]")


@cli.command()
@click.argument("session_id")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
@click.pass_context
def logs(ctx, session_id: str, follow: bool, lines: int):
    """View session logs."""
    import os

    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    log_file = Path(session.log_file)
    if not log_file.exists():
        console.print(f"[yellow]Log file not found yet: {log_file}[/yellow]")
        console.print("[dim]The session may not have started yet.[/dim]")
        sys.exit(1)

    # Use os.execvp to replace this process with tail
    # This prevents any subprocess weirdness and ensures clean output
    if follow:
        os.execvp("tail", ["tail", "-f", "-n", str(lines), str(log_file)])
    else:
        os.execvp("tail", ["tail", "-n", str(lines), str(log_file)])


@cli.command()
@click.argument("session_id")
@click.option("--title", "-t", help="PR title (default: generated from branch name)")
@click.option("--draft", "-d", is_flag=True, help="Create as draft PR")
@click.option("--base", "-b", default="main", help="Base branch (default: main)")
@click.pass_context
def pr(ctx, session_id: str, title: Optional[str], draft: bool, base: str):
    """Create PR from agent's work."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    # Check gh CLI
    if not PRCreator.check_gh_installed():
        console.print("[red]Error: gh CLI not found. Please install it first.[/red]")
        console.print("  macOS: brew install gh")
        console.print("  Ubuntu: sudo apt-get install gh")
        sys.exit(1)

    try:
        # Stop tmux session
        if ctx.obj["tmux"].session_exists(session.tmux_session_name):
            console.print("Stopping agent...")
            ctx.obj["tmux"].kill_session(session.tmux_session_name)

        # Create PR (use original repo for git operations, but worktree has the changes)
        with console.status("[bold green]Creating PR..."):
            pr_creator = PRCreator(Path(session.working_directory))
            pr_url = pr_creator.create_pr(session.branch_name, base, title, draft, session)

        # Update session
        ctx.obj["session_manager"].update_session(
            session_id, status=SessionStatus.COMPLETED, pr_url=pr_url
        )

        console.print(f"[green]✓[/green] PR created: [cyan]{pr_url}[/cyan]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error creating PR: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr}[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("session_id")
@click.pass_context
def stop(ctx, session_id: str):
    """Stop a running agent session."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    # Stop Docker container if applicable
    if session.runtime == "docker":
        docker_mgr = ctx.obj["docker"]
        if docker_mgr.container_running(session.session_id):
            docker_mgr.stop_container(session.session_id)
            console.print(f"[dim]Stopped container beehive-{session.session_id}[/dim]")

    if ctx.obj["tmux"].session_exists(session.tmux_session_name):
        ctx.obj["tmux"].kill_session(session.tmux_session_name)
        console.print(f"[green]✓[/green] Stopped [bold]{session.name}[/bold]")
    else:
        console.print(f"[yellow]tmux session already stopped[/yellow]")

    ctx.obj["session_manager"].update_session(session_id, status=SessionStatus.STOPPED)


@cli.command()
@click.argument("session_id")
@click.pass_context
def status(ctx, session_id: str):
    """Show detailed status of a session."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    # Check tmux status
    tmux_running = ctx.obj["tmux"].session_exists(session.tmux_session_name)

    console.print(f"\n[bold]Session: {session.name}[/bold]")
    console.print(f"  ID: [cyan]{session.session_id}[/cyan]")
    console.print(f"  Status: [{session.status}]{session.status}[/{session.status}]")
    console.print(f"  Runtime: {'[magenta]docker[/magenta]' if session.runtime == 'docker' else '[dim]host[/dim]'}")
    console.print(f"  Branch: [yellow]{session.branch_name}[/yellow]")
    console.print(f"  Original Repo: {session.original_repo}")
    console.print(f"  Worktree: {session.working_directory}")
    console.print(f"  Created: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if session.completed_at:
        console.print(
            f"  Completed: {session.completed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    console.print(
        f"  tmux Session: [{'green' if tmux_running else 'red'}]"
        f"{session.tmux_session_name} ({'running' if tmux_running else 'stopped'})"
        f"[/{'green' if tmux_running else 'red'}]"
    )
    if session.runtime == "docker":
        docker_mgr = ctx.obj["docker"]
        container_up = docker_mgr.container_running(session.session_id)
        console.print(
            f"  Container: [{'green' if container_up else 'red'}]"
            f"{session.container_name} ({'running' if container_up else 'stopped'})"
            f"[/{'green' if container_up else 'red'}]"
        )
    console.print(f"  Log File: [dim]{session.log_file}[/dim]")
    if session.pr_url:
        console.print(f"  PR: [cyan]{session.pr_url}[/cyan]")

    console.print(f"\n[bold]Instructions:[/bold]")
    console.print(f"  {session.instructions[:200]}...")

    # Show recent output if tmux is running
    if tmux_running:
        console.print(f"\n[bold]Recent Output:[/bold]")
        recent = ctx.obj["tmux"].capture_pane(session.tmux_session_name, 10)
        console.print(f"[dim]{recent}[/dim]")


@cli.command()
@click.argument("session_id")
@click.option("--force", "-f", is_flag=True, help="Force delete without confirmation")
@click.pass_context
def delete(ctx, session_id: str, force: bool):
    """Delete a session."""
    session = ctx.obj["session_manager"].get_session(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/red]")
        sys.exit(1)

    if not force:
        confirm = click.confirm(
            f"Delete session '{session.name}' ({session.session_id})?"
        )
        if not confirm:
            console.print("Aborted.")
            return

    # Stop Docker container if applicable
    if session.runtime == "docker":
        docker_mgr = ctx.obj["docker"]
        if docker_mgr.container_running(session.session_id):
            docker_mgr.stop_container(session.session_id)

    # Stop tmux session if running
    if ctx.obj["tmux"].session_exists(session.tmux_session_name):
        ctx.obj["tmux"].kill_session(session.tmux_session_name)

    # Remove workspace (worktree for host, cloned dir for docker)
    try:
        worktree_path = Path(session.working_directory)
        if session.runtime == "docker":
            # Docker sessions use a cloned repo — just remove the directory
            import shutil
            if worktree_path.exists():
                shutil.rmtree(worktree_path)
                console.print(f"[dim]Removed clone: {worktree_path}[/dim]")
        else:
            git = GitOperations(Path(session.original_repo))
            if git.worktree_exists(worktree_path):
                git.remove_worktree(worktree_path, force=True)
                console.print(f"[dim]Removed worktree: {worktree_path}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not remove workspace: {e}[/yellow]")

    # Delete from storage
    ctx.obj["session_manager"].delete_session(session_id)

    console.print(f"[green]✓[/green] Deleted session [bold]{session.name}[/bold]")
    console.print(
        f"[dim]Note: Branch {session.branch_name} still exists in git[/dim]"
    )


@cli.group("config")
@click.pass_context
def config_group(ctx):
    """Manage Beehive configuration."""
    pass


@config_group.group("claude-md")
@click.pass_context
def claude_md_group(ctx):
    """Manage the default CLAUDE.md template for all agents."""
    pass


@claude_md_group.command("show")
@click.pass_context
def claude_md_show(ctx):
    """Print the current CLAUDE.md template."""
    config = ctx.obj["config"]
    content = config.get_claude_md()
    if content:
        console.print(content)
    else:
        console.print("[dim]No CLAUDE.md template configured.[/dim]")
        console.print(f"[dim]Set one with: beehive config claude-md set \"# Rules\"[/dim]")


@claude_md_group.command("edit")
@click.pass_context
def claude_md_edit(ctx):
    """Open the CLAUDE.md template in $EDITOR."""
    import os

    config = ctx.obj["config"]
    path = config.get_claude_md_path()

    # Ensure file exists
    config.data_dir.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("")

    editor = os.environ.get("EDITOR", "vi")
    os.execvp(editor, [editor, str(path)])


@claude_md_group.command("set")
@click.argument("content")
@click.pass_context
def claude_md_set(ctx, content: str):
    """Set the CLAUDE.md template from a string or @file."""
    config = ctx.obj["config"]

    if content.startswith("@"):
        filepath = Path(content[1:])
        if not filepath.exists():
            console.print(f"[red]Error: File not found: {filepath}[/red]")
            sys.exit(1)
        content = filepath.read_text()

    config.set_claude_md(content)
    console.print(f"[green]✓[/green] CLAUDE.md template saved to {config.get_claude_md_path()}")


if __name__ == "__main__":
    cli()
