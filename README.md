# Beehive 🐝

**Manage multiple Claude Code agent sessions in parallel**

Beehive is a CLI tool that enables you to orchestrate multiple Claude Code agents working on different tasks simultaneously. Each agent runs in its own git branch, has dedicated instructions, and produces a Pull Request as its deliverable.

## Features

- 🔀 **True Parallel Execution**: Run multiple Claude Code agents simultaneously using git worktrees
- 🌿 **Isolated Workspaces**: Each agent works in its own git worktree (isolated branch + directory)
- 📝 **Session Management**: Track and manage all your agent sessions
- 🖥️ **tmux-based**: Interactive sessions using tmux
- 📊 **Logging**: Capture all agent output for review
- 🔄 **PR Automation**: Automatically create pull requests from agent work
- 🚫 **Zero Conflicts**: Agents never interfere with each other or your main repository

## Architecture

Beehive uses two key technologies:

1. **Git Worktrees** - Each agent gets an isolated workspace (separate directory for the same repo)
2. **tmux** (terminal multiplexer) - Each agent runs in its own tmux session

This combination enables true parallel execution while preserving Claude Code's interactive nature.

```
Your Repository: ~/code/myproject (untouched!)
                        │
        ┌───────────────┴────────────────┐
        │      Beehive CLI (Click)       │
        │  create | list | attach | ...  │
        └───────────────┬────────────────┘
                        │
        ┌───────────────┴────────────────┐
        │   Git Worktrees (Isolation)    │
        │  ~/.beehive/worktrees/         │
        │    ├── beehive-a1b2/  (Agent 1)│
        │    ├── beehive-e5f6/  (Agent 2)│
        │    └── beehive-i9j0/  (Agent 3)│
        └───────────────┬────────────────┘
                        │
        ┌───────────────┴────────────────┐
        │   tmux Sessions (Control)      │
        │    ├── beehive-a1b2  (running) │
        │    ├── beehive-e5f6  (running) │
        │    └── beehive-i9j0  (running) │
        └───────────────┬────────────────┘
                        │
        ┌───────────────┴────────────────┐
        │   Claude Code Agents           │
        │    ├── Agent 1: "Modernize UI" │
        │    ├── Agent 2: "Optimize API" │
        │    └── Agent 3: "Add Tests"    │
        └────────────────────────────────┘

Result: 3 PRs created in parallel! ✓
```

**Key Benefit**: Each agent works in complete isolation. No conflicts, no interference.

## Prerequisites

1. **tmux** - Terminal multiplexer
   ```bash
   # macOS
   brew install tmux

   # Ubuntu/Debian
   sudo apt-get install tmux
   ```

2. **gh CLI** - GitHub CLI (for PR creation)
   ```bash
   # macOS
   brew install gh

   # Ubuntu/Debian
   sudo apt-get install gh

   # Then authenticate
   gh auth login
   ```

3. **Claude Code** - Must be installed and authenticated
   ```bash
   # Install Claude Code (if not already installed)
   # See: https://docs.anthropic.com/claude/docs/claude-code

   # Verify it's working
   claude --version
   ```

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/beehive.git
cd beehive

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### Using pip (when published)

```bash
pip install beehive-cli
```

## How It Works

When you create a Beehive session:

1. **Git Worktree Created** - A new isolated workspace at `~/.beehive/worktrees/beehive-<id>/`
2. **Branch Created** - A new branch `beehive/<name>-<id>` in the worktree
3. **tmux Session Started** - Claude Code runs in the worktree directory
4. **Agent Works** - Completely isolated from your main repo and other agents

Your main repository stays untouched! All agent work happens in isolated worktrees.

See [WORKTREES.md](WORKTREES.md) for detailed explanation.

## Quick Start

### 1. Create a session

```bash
# Create an agent session with inline instructions
beehive create fix-auth-bug \
  -i "Fix the authentication bug in the login flow" \
  -w ~/code/myproject

# Or use instructions from a file
beehive create add-feature \
  -i @instructions.txt \
  -w ~/code/myproject \
  -p "Start by reading the codebase structure"
```

This will:
- Create a new git worktree at `~/.beehive/worktrees/beehive-a1b2c3d4/`
- Create a new branch (`beehive/fix-auth-bug-a1b2c3d4`) in the worktree
- Start a tmux session with Claude Code in the worktree
- Begin capturing logs
- Send initial prompt if provided

Your main repository (`~/code/myproject/`) is completely untouched!

### 2. Monitor the session

```bash
# List all sessions
beehive list

# View logs in real-time
beehive logs a1b2 -f

# Check detailed status
beehive status a1b2
```

### 3. Interact with the agent

```bash
# Attach to the interactive session
beehive attach a1b2
# Press Ctrl+B then D to detach

# Send a prompt non-interactively
beehive send a1b2 "Now add unit tests"

# Send prompt from file
beehive send a1b2 @next-task.txt
```

### 4. Create a Pull Request

```bash
# When the agent is done, create a PR
beehive pr a1b2 -t "Fix authentication bug"

# Create as draft PR
beehive pr a1b2 --draft

# Specify custom base branch
beehive pr a1b2 -b develop
```

### 5. Manage sessions

```bash
# Stop a running session
beehive stop a1b2

# Delete a session
beehive delete a1b2

# List only running sessions
beehive list --status running
```

## CLI Reference

### `beehive create <name>`

Create a new agent session.

**Options:**
- `-i, --instructions TEXT` - Instructions for the agent (required)
  - Can be inline: `-i "Do something"`
  - Or from file: `-i @instructions.txt`
- `-w, --working-dir PATH` - Working directory (default: current directory)
- `-b, --base-branch TEXT` - Base branch to branch from (default: main)
- `-p, --prompt TEXT` - Initial prompt to send
  - Can be inline: `-p "Start here"`
  - Or from file: `-p @prompt.txt`

**Example:**
```bash
beehive create refactor-api \
  -i "Refactor the API to use async/await" \
  -w ~/projects/myapp \
  -b develop \
  -p "First, analyze the current API structure"
```

### `beehive list`

List all agent sessions.

**Options:**
- `-s, --status [running|completed|failed|stopped]` - Filter by status

**Example:**
```bash
beehive list --status running
```

### `beehive attach <session-id>`

Attach to agent's tmux session (interactive mode).

Press `Ctrl+B` then `D` to detach and return to your shell.

**Example:**
```bash
beehive attach a1b2
```

### `beehive send <session-id> <text>`

Send a prompt to the agent non-interactively.

**Example:**
```bash
beehive send a1b2 "Add error handling"
beehive send a1b2 @next-instructions.txt
```

### `beehive logs <session-id>`

View session logs.

**Options:**
- `-f, --follow` - Follow log output (like `tail -f`)
- `-n, --lines INTEGER` - Number of lines to show (default: 50)

**Example:**
```bash
beehive logs a1b2 -f
beehive logs a1b2 -n 100
```

### `beehive status <session-id>`

Show detailed status of a session.

**Example:**
```bash
beehive status a1b2
```

### `beehive pr <session-id>`

Create a pull request from the agent's work.

**Options:**
- `-t, --title TEXT` - PR title (default: generated from branch name)
- `-d, --draft` - Create as draft PR
- `-b, --base TEXT` - Base branch (default: main)

**Example:**
```bash
beehive pr a1b2 -t "Refactor authentication flow" --draft
```

### `beehive stop <session-id>`

Stop a running agent session.

**Example:**
```bash
beehive stop a1b2
```

### `beehive delete <session-id>`

Delete a session (with confirmation).

**Options:**
- `-f, --force` - Skip confirmation

**Example:**
```bash
beehive delete a1b2 --force
```

## Usage Patterns

### Parallel Development (The Magic! ✨)

Run multiple agents on the **same repository** without any conflicts:

```bash
# Agent 1: Frontend work
beehive create ui-refresh \
  -i "Modernize the UI components" \
  -w ~/code/myapp

# Agent 2: Backend work
beehive create api-optimization \
  -i "Optimize database queries in the API" \
  -w ~/code/myapp

# Agent 3: Documentation
beehive create update-docs \
  -i "Update documentation for new features" \
  -w ~/code/myapp

# Monitor all sessions
beehive list

# Your main repo is untouched!
cd ~/code/myapp
git status  # Clean, still on main branch

# Each agent has its own workspace
ls ~/.beehive/worktrees/
# beehive-a1b2c3d4/  (UI work)
# beehive-e5f6g7h8/  (API work)
# beehive-i9j0k1l2/  (Tests)

# All agents working in parallel, zero conflicts! ✓
```

### Complex Instructions

Use instruction files for detailed tasks:

```bash
# Create instructions.txt
cat > instructions.txt << 'EOF'
Task: Implement user authentication system

Requirements:
1. Add JWT-based authentication
2. Create login/logout endpoints
3. Add middleware for protected routes
4. Include comprehensive error handling
5. Write unit tests for all endpoints
6. Update API documentation

Technical constraints:
- Use existing database schema
- Follow the repository's coding standards
- Ensure backward compatibility
EOF

beehive create auth-system -i @instructions.txt -w ~/code/api
```

### Incremental Prompts

Guide the agent through multiple steps:

```bash
# Create session
beehive create feature-x -i "Implement feature X" -w ~/code/app

# Send follow-up instructions
beehive send feature-x "First, add the data model"
# Wait and review...

beehive send feature-x "Now add the API endpoints"
# Wait and review...

beehive send feature-x "Finally, add frontend integration"
```

### Review Before PR

```bash
# Create session
beehive create bug-fix -i "Fix memory leak" -w ~/code/app

# Let it run...
# Attach to review the work
beehive attach bug-fix

# If satisfied, create PR
beehive pr bug-fix
```

## Data Storage

Beehive stores all data in `~/.beehive/`:

```
~/.beehive/
├── sessions.json        # Session metadata
├── logs/                # Agent output logs
│   ├── a1b2c3d4.log
│   └── e5f6g7h8.log
└── worktrees/           # Isolated agent workspaces
    ├── beehive-a1b2c3d4/    # Agent 1's workspace
    │   ├── .git -> (linked to original repo)
    │   ├── src/
    │   └── ...
    └── beehive-e5f6g7h8/    # Agent 2's workspace
        ├── .git -> (linked to original repo)
        ├── src/
        └── ...
```

You can customize the data directory:

```bash
beehive --data-dir /custom/path create my-session -i "..."
```

## Tips & Best Practices

1. **Session Naming**: Use descriptive names that indicate the task
   - ✅ `fix-login-bug`, `add-user-profile`, `refactor-api`
   - ❌ `task1`, `test`, `agent`

2. **Instructions**: Be specific and actionable
   - ✅ "Add pagination to the /users API endpoint with limit and offset parameters"
   - ❌ "Improve the API"

3. **Monitoring**: Use `logs -f` to watch progress in real-time
   ```bash
   beehive logs <id> -f
   ```

4. **Session IDs**: Partial matching works (like git)
   ```bash
   beehive attach a1b2  # Matches a1b2c3d4
   ```

5. **Review Work**: Always review agent work before creating PRs
   ```bash
   beehive attach <id>  # Interactive review
   ```

6. **Cleanup**: Delete completed sessions to keep your list clean
   ```bash
   beehive list --status completed | awk '{print $1}' | xargs -I {} beehive delete {} -f
   ```

## Troubleshooting

### tmux session not found

If you see "tmux session not found", the agent may have crashed or been killed:

```bash
# Check if tmux session exists
tmux ls

# View logs to see what happened
beehive logs <session-id>

# If needed, create a new session
beehive create <name> -i "..." -w <dir>
```

### "claude: command not found"

Ensure Claude Code is installed and in your PATH:

```bash
which claude
claude --version
```

### PR creation fails

Make sure gh CLI is authenticated:

```bash
gh auth status
gh auth login  # if needed
```

### Permission denied on logs

Check file permissions:

```bash
ls -la ~/.beehive/logs/
chmod 644 ~/.beehive/logs/*.log
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=beehive
```

### Code Style

```bash
# Format code
black beehive/

# Lint
ruff check beehive/
```

## Roadmap

- [ ] Session templates for common tasks
- [ ] Web dashboard for monitoring
- [ ] Agent collaboration (shared context)
- [ ] Cost tracking per session
- [ ] Session archival and export
- [ ] Integration with CI/CD pipelines
- [ ] Multi-repo support

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built for [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) by Anthropic
- Uses [tmux](https://github.com/tmux/tmux) for session management
- CLI built with [Click](https://click.palletsprojects.com/) and [Rich](https://rich.readthedocs.io/)
