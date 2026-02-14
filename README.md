# Beehive

**Orchestrate multiple Claude Code agents across repositories with planning, isolation, and automation.**

Beehive is a CLI and TUI tool for running Claude Code agents in parallel. Each agent works in an isolated git workspace with its own branch, tmux session, and optional Docker container. A planning layer lets an AI architect break high-level directives into tickets that are auto-assigned to agents, tracked through completion, and watched until PRs merge.

```
                        Your Repos (untouched)
                     ~/projects/api   ~/projects/web
                              \           /
                    ┌──────────┴─────────┴──────────┐
                    │         Beehive CLI            │
                    │   architect · project · cto    │
                    └──────────────┬─────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────┴──────────┐ ┌──────┴───────┐ ┌─────────┴──────────┐
    │  Worktree/Clone 1  │ │ Worktree 2   │ │  Worktree/Clone 3  │
    │  ~/.beehive/wt/a1/ │ │ ~/.beehive/  │ │  ~/.beehive/wt/c3/ │
    │                    │ │  wt/b2/      │ │                    │
    │ ┌────────────────┐ │ │ ┌──────────┐ │ │ ┌────────────────┐ │
    │ │ tmux: beehive- │ │ │ │ tmux:    │ │ │ │ tmux: beehive- │ │
    │ │ a1b2 (docker)  │ │ │ │ beehive- │ │ │ │ c3d4 (host)    │ │
    │ │                │ │ │ │ b2c3     │ │ │ │                │ │
    │ │  Claude Code   │ │ │ │ Claude   │ │ │ │  Claude Code   │ │
    │ │  Agent 1       │ │ │ │ Agent 2  │ │ │ │  Agent 3       │ │
    │ └────────────────┘ │ │ └──────────┘ │ │ └────────────────┘ │
    └────────────────────┘ └──────────────┘ └────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
          PR #101              PR #102              PR #103
```

---

## Table of Contents

- [Why Beehive](#why-beehive)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Architects and Planning](#architects-and-planning)
- [Sequential vs Parallel Execution](#sequential-vs-parallel-execution)
- [Projects and CTO Advisor](#projects-and-cto-advisor)
- [Researchers](#researchers)
- [Docker Isolation](#docker-isolation)
- [Preview Environments](#preview-environments)
- [TUI Dashboard](#tui-dashboard)
- [Full Example: Building a Credits System](#full-example-building-a-credits-system)
- [CLI Reference](#cli-reference)
- [Data Storage](#data-storage)
- [Tips and Best Practices](#tips-and-best-practices)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Why Beehive

Claude Code is powerful but works in a single directory on a single branch. If you want three agents working simultaneously — one on the API, one on the frontend, one on tests — they will collide. Beehive solves this by giving every agent its own isolated workspace and managing the full lifecycle: create a branch, launch Claude Code, track progress, create a PR, clean up.

Beyond individual sessions, Beehive adds a **planning layer**. An "architect" uses Claude to decompose a high-level directive ("add a credits system") into ordered tickets targeting specific repos, then assigns each ticket to its own agent session. You can execute tickets sequentially (wait for each PR to merge before starting the next) or in parallel (launch all at once). A `watch` command monitors progress, detects PR merges, and auto-assigns the next ticket.

---

## How It Works

Beehive combines three technologies for agent isolation:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Isolation Model                            │
│                                                                 │
│  Git Worktrees (or Clones)                                      │
│  ─────────────────────────                                      │
│  Each agent gets its own directory and branch.                  │
│  Your main repo stays untouched on its current branch.          │
│  Worktrees share .git (fast). Docker clones get standalone      │
│  copies so container paths work correctly.                      │
│                                                                 │
│  tmux Sessions                                                  │
│  ─────────────                                                  │
│  Each agent runs Claude Code inside a detached tmux session.    │
│  You can attach/detach at any time, send prompts, and tail      │
│  logs — all without interrupting the agent.                     │
│                                                                 │
│  Docker Containers (optional)                                   │
│  ────────────────────────────                                   │
│  When auto-approve is on and Docker is available, each agent    │
│  runs inside a container with its own filesystem, network       │
│  namespace, and toolchain. True sandboxing.                     │
└─────────────────────────────────────────────────────────────────┘
```

### Session Lifecycle

```
beehive create "fix auth bug" -i "Fix the login flow" -w ~/code/api
    │
    │  1. Generate session ID (a1b2c3d4) and branch (beehive/fix-auth-bug-a1b2c3d4)
    │  2. Create worktree at ~/.beehive/worktrees/beehive-a1b2c3d4/
    │  3. Inject CLAUDE.md (global + project)
    │  4. Write system prompt to .beehive-system-prompt.txt
    │  5. Start tmux session with Claude Code
    │  6. Begin logging to ~/.beehive/logs/a1b2c3d4.log
    ▼
┌──────────────────────────────────────┐
│  Agent is RUNNING                    │
│                                      │
│  beehive attach a1b2   (interactive) │
│  beehive send a1b2 "add tests"       │
│  beehive logs a1b2 -f  (tail logs)   │
│  beehive status a1b2   (check state) │
└───────────────┬──────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│  Agent finishes work                 │
│                                      │
│  beehive pr a1b2    → Push + open PR │
│  beehive stop a1b2  → Stop session   │
│  beehive delete a1b2 → Cleanup all   │
└──────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **tmux** | Terminal multiplexer for agent sessions | `brew install tmux` (macOS) or `apt install tmux` |
| **git** | Worktree creation, branching, PRs | Usually pre-installed |
| **gh** | GitHub CLI for PR creation | `brew install gh` then `gh auth login` |
| **Claude Code** | The AI coding agent | `npm install -g @anthropic-ai/claude-code` |
| **Docker** | Optional sandboxing | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Installation

```bash
# Clone and install
git clone https://github.com/yourusername/beehive.git
cd beehive
pip install -e .

# With dev dependencies (for tests)
pip install -e ".[dev]"

# Verify
beehive --help
```

---

## Quick Start

### Run a single agent

```bash
# Create an agent session on a repo
beehive create fix-login-bug \
  -i "Fix the authentication bug where expired tokens aren't refreshed" \
  -w ~/projects/api

# Watch it work
beehive logs a1b2 -f

# When done, create a PR
beehive pr a1b2
```

### Run multiple agents in parallel

```bash
# Three agents on the same repo — no conflicts
beehive create modernize-ui     -i "Migrate components to React 18" -w ~/projects/app
beehive create optimize-queries -i "Add database indexes and optimize N+1 queries" -w ~/projects/app
beehive create add-e2e-tests    -i "Add Playwright end-to-end tests for auth flow" -w ~/projects/app

# All running simultaneously, each on its own branch
beehive list
```

### Use the architect for planned execution

```bash
# 1. Create an architect with repo config
beehive architect create my-arch -c architect.yaml

# 2. Generate a plan from a high-level directive
beehive architect plan my-arch -d "Add user authentication with JWT"

# 3. Assign tickets (sequential by default — one at a time)
beehive architect assign my-arch

# 4. Watch progress — auto-assigns next ticket when current PR merges
beehive architect watch my-arch
```

### Launch the TUI dashboard

```bash
beehive ui
```

---

## Core Concepts

### Sessions

A **session** is a single Claude Code agent running in an isolated workspace. Every session has:

- A unique 8-character ID (supports partial matching: `a1b2` matches `a1b2c3d4`)
- A git branch (`beehive/<name>-<id>`)
- A worktree directory (`~/.beehive/worktrees/beehive-<id>/`)
- A tmux session for interactive control
- A log file capturing all output
- A runtime: `host` (worktree) or `docker` (container)

### Architects

An **architect** is a named configuration that knows about one or more repositories and has guiding principles. You give it a high-level directive, and it calls Claude to break it into **tickets** — each targeting a specific repo with detailed instructions an agent can follow.

### Plans and Tickets

A **plan** is the output of an architect breaking down a directive. It contains ordered **tickets**. Each ticket has:

- An execution **order** (1, 2, 3...)
- A target **repo**
- A **status**: pending → assigned → in_progress → completed → merged (or failed)
- A linked **session** and **branch** once assigned

### Projects

A **project** groups repositories with design/engineering principles, links to architects, and optionally configures preview environments. The project's **CTO advisor** provides AI-powered strategic guidance with full context of plans, tickets, and sessions.

### Researchers

A **researcher** is like an architect but for research tasks. Instead of creating PRs, experiments produce local results (RESULTS.md, artifacts). Useful for benchmarking, analysis, or exploration.

---

## Architects and Planning

### 1. Create an architect config

Write a YAML file describing your repos and principles:

```yaml
# architect.yaml
principles: |
  - Follow existing patterns in the codebase
  - Each ticket should be independently mergeable
  - Write tests for all new functionality
  - Keep backward compatibility

repos:
  - name: api
    path: /Users/you/projects/api
    base_branch: main
    description: Django REST API backend

  - name: web
    path: /Users/you/projects/web
    base_branch: main
    description: React frontend application
```

```bash
beehive architect create my-project -c architect.yaml
# ✓ Created architect: my-project
#   ID: c8d63ee8
```

### 2. Generate a plan

```bash
beehive architect plan c8d6 -d "Add user profile pages with avatar upload"
```

Claude analyzes your repos and principles, then generates ordered tickets:

```
✓ Plan created: a2f1b3c4
  Directive: Add user profile pages with avatar upload
  Tickets: 4

  #  ID        Title                          Repo  Status
  1  t1a2b3c4  Add avatar storage model        api   pending
  2  t2d5e6f7  Create profile API endpoints    api   pending
  3  t3g8h9i0  Build profile page component    web   pending
  4  t4j1k2l3  Add avatar upload widget        web   pending
```

### 3. Edit tickets before executing

```bash
# Edit a ticket's title or description
beehive architect edit-ticket t1a2 -t "Add avatar storage with S3"

# Or edit in the TUI
beehive ui  # navigate to Architects → Plans → Tickets, press 'e'
```

### 4. Assign tickets to agents

```bash
# Sequential (default): assigns only ticket #1
beehive architect assign c8d6

# Parallel: assigns all pending tickets at once
beehive architect assign c8d6 --parallel
```

### 5. Monitor progress

```bash
# One-shot status check (syncs from sessions)
beehive architect status c8d6

# Continuous watch — auto-assigns next ticket when PR merges
beehive architect watch c8d6 --interval 30
```

---

## Sequential vs Parallel Execution

Beehive supports two execution modes for plan tickets:

```
Sequential (default)                    Parallel (--parallel)
─────────────────────                   ─────────────────────

  Ticket #1: assigned                     Ticket #1: assigned ──┐
       │                                  Ticket #2: assigned ──┤── all at once
       ▼                                  Ticket #3: assigned ──┤
  Ticket #1: PR merged                   Ticket #4: assigned ──┘
       │                                       │
       ▼                                       ▼
  Ticket #2: auto-assigned                All PRs independently
       │
       ▼
  Ticket #2: PR merged
       │
       ▼
  Ticket #3: auto-assigned
       │
      ...
```

### Sequential mode

Best when tickets build on each other (e.g., "create the model" before "build the API" before "build the UI"). The `watch` command drives the pipeline:

```bash
# Assign first ticket
beehive architect assign c8d6

# Watch loop: detects merges, assigns next ticket, exits when all done
beehive architect watch c8d6
```

The watch loop does the following every cycle:
1. Syncs session status to ticket status (running → assigned, completed → completed, failed → failed)
2. Syncs PR URLs from sessions to tickets
3. Checks if any ticket's PR has been merged via `gh pr view`
4. If merged, marks ticket as `merged`
5. If no ticket is in-flight (assigned/in_progress/completed), assigns the next pending ticket by order
6. Exits when all tickets are terminal (merged or failed)

### Parallel mode

Best when tickets are independent (e.g., "add feature A to repo X" and "add feature B to repo Y"):

```bash
beehive architect assign c8d6 --parallel
```

### Ticket statuses

```
pending ──→ assigned ──→ in_progress ──→ completed ──→ merged
                │              │              │
                └──────────────┴──────────────┘
                               │
                               ▼
                            failed
```

| Status | Meaning |
|--------|---------|
| `pending` | Not yet assigned to an agent |
| `assigned` | Agent session created, Claude Code running |
| `in_progress` | Agent is actively working (synced from session) |
| `completed` | Agent finished, PR may be open |
| `merged` | PR has been merged on GitHub |
| `failed` | Agent session failed or was stopped |

---

## Projects and CTO Advisor

Projects provide a higher-level grouping with design principles and an AI-powered advisor.

### Create a project

```yaml
# project.yaml
description: E-commerce platform with React frontend and Django backend
design_principles: |
  - Mobile-first responsive design
  - Consistent component library
engineering_principles: |
  - Type safety everywhere (TypeScript + Python type hints)
  - 80% test coverage minimum
repos:
  - name: api
    path: /Users/you/projects/api
    base_branch: main
  - name: web
    path: /Users/you/projects/web
    base_branch: main
preview:
  setup_command: "cd api && ./start.sh & cd ../web && PORT=$BEEHIVE_PORT npm start"
  teardown_command: "pkill -f start.sh || true"
  url_template: "http://{task_name}.localhost:{port}"
  startup_timeout: 30
```

```bash
beehive project create myshop -c project.yaml
beehive project link myshop c8d6  # link your architect
```

### Project-level CLAUDE.md

Layer instructions that every agent in the project receives:

```bash
# Set from a file
beehive project claude-md set myshop @project-claude.md

# Or edit interactively
beehive project claude-md edit myshop
```

CLAUDE.md files are layered: **global** (`~/.beehive/CLAUDE.md`) + **project** + **repo-level** `.claude/CLAUDE.md`.

### CTO Advisor

The CTO has full context of your project — repos, architects, plans, tickets, sessions, and conversation history:

```bash
# Interactive strategic chat
beehive cto chat myshop
> What's the riskiest part of the current plan?
> Should we split the auth tickets differently?
> exit

# One-shot project brief
beehive cto brief myshop

# View conversation history
beehive cto history myshop
```

---

## Researchers

Researchers are the research counterpart to architects. Instead of creating PRs, experiments produce local artifacts — analysis results, benchmarks, reports.

```yaml
# researcher.yaml
principles: |
  - Document all findings in RESULTS.md
  - Include reproducible steps
  - Compare against baselines
repos:
  - name: api
    path: /Users/you/projects/api
    base_branch: main
```

```bash
beehive researcher create perf-researcher -c researcher.yaml
beehive researcher study perf-r -d "Benchmark API response times and identify bottlenecks"
beehive researcher assign perf-r
beehive researcher status perf-r
```

---

## Docker Isolation

When auto-approve (`-y`) is enabled and Docker is available, agents run inside containers for true sandboxing.

```
┌─────────────────────────────────────────────────────────┐
│  Docker Container (beehive-agent image)                  │
│                                                         │
│  /workspace/  ← mounted from worktree clone             │
│                                                         │
│  Includes: Node 20, Python 3, tmux, gh CLI,             │
│            Claude Code, git, network isolation           │
│                                                         │
│  Auto-configured:                                       │
│    - Git user.name / user.email from host               │
│    - GitHub auth (gh CLI token forwarded)                │
│    - SSH keys for private repos                         │
│    - ANTHROPIC_API_KEY from host env                    │
└─────────────────────────────────────────────────────────┘
```

Docker mode uses `git clone` instead of worktrees (because host paths don't map inside containers). The image is built automatically from `.devcontainer/Dockerfile` on first use.

```bash
# Docker is used automatically when available + auto-approve
beehive create my-task -i "..." -w ~/project -y

# Force host mode even if Docker is available
beehive create my-task -i "..." -w ~/project -y --no-docker
```

---

## Preview Environments

When a project has preview config, each assigned ticket automatically gets its own dev server on a unique port (range 3100-3199).

```yaml
# In project.yaml
preview:
  setup_command: "PORT=$BEEHIVE_PORT npm start"
  teardown_command: "pkill -f 'npm start' || true"
  url_template: "http://{task_name}.localhost:{port}"
  startup_timeout: 30
```

The `$BEEHIVE_PORT` environment variable is auto-assigned. The `{task_name}` and `{port}` placeholders are filled in the URL template. Preview URLs are displayed in the CLI output and included in PR descriptions.

```bash
# Manage previews
beehive project preview list
beehive project preview stop <session_id>
beehive project preview stop-all
```

---

## TUI Dashboard

Launch the terminal UI for a visual overview of everything:

```bash
beehive ui
```

Navigate with number keys (1-5) or arrow keys. Press Enter to drill down, Escape to go back.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  bh 🐝                                                                  │
├────────────┬─────────────────────────────────────────────────────────────┤
│            │                                                             │
│  Views     │   3          12          2            1            5        │
│            │  Agents    Total      Architects   Researchers   Open PRs  │
│  ⌂  Home   │  running   agents                                          │
│  ☰ Projects│                                                             │
│  ⚒ Archit. │  ┌─ Quick stats ───────┐  ┌─ Recent activity ───────────┐ │
│  🔬 Resear.│  │ Sessions today   4   │  │ 02/14 09:15  fix-auth  ▸   │ │
│  ⚙ Agents  │  │ Completed        8   │  │ 02/14 09:10  Plan a2f1    │ │
│            │  │ Failed           1   │  │ 02/14 08:45  add-tests ▸  │ │
│            │  │ Success rate    89%   │  │ 02/14 08:30  refactor  ✓  │ │
│            │  │                       │  │                            │ │
│            │  │ Total tickets   16   │  └────────────────────────────┘ │
│            │  │ Tickets done    12   │                                   │
│            │  └───────────────────────┘                                  │
├────────────┴─────────────────────────────────────────────────────────────┤
│ 1 Home  2 Projects  3 Architects  4 Researchers  5 Agents  r Refresh    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Architects view** lets you drill from Architects → Plans → Tickets, with columns for order (`#`), branch, and status (including `merged` in cyan). Press `e` to edit, `c` to create, `d` to delete.

---

## Full Example: Building a Credits System

Here is a realistic end-to-end workflow for adding a credits system to a two-repo project (Django backend + React frontend).

### Step 1: Set up the project

```yaml
# bitbook-project.yaml
description: Bitbook — fabric (React) + braid (Django)
design_principles: |
  - Mobile-first responsive design
  - Consistent Chakra UI component usage
engineering_principles: |
  - Type safety (TypeScript + Python type hints)
  - Django service pattern for business logic
  - Tests for all new endpoints
repos:
  - name: fabric
    path: /Users/you/bitbook/fabric
    base_branch: main
  - name: braid
    path: /Users/you/bitbook/braid
    base_branch: main
preview:
  setup_command: "(cd braid && ./startup.sh --dev &) && cd fabric && PORT=$BEEHIVE_PORT npm start"
  teardown_command: "pkill -f 'startup.sh --dev' || true"
  url_template: "http://{task_name}.localhost:{port}"
  startup_timeout: 30
```

```bash
beehive project create bitbook -c bitbook-project.yaml
```

### Step 2: Create an architect with domain knowledge

```yaml
# credits-architect.yaml
principles: |
  Backend (braid) is Django + Django Ninja API.
  Models live in books/models.py. Services in books/services/.
  API endpoints in api/. UserProfile has stripe_customer_id.

  Frontend (fabric) is React + Chakra UI + TypeScript.
  API client at src/braidApiClient.tsx.
  Account page at src/AccountPage/AccountPage.tsx.

  Rules:
  - Credit costs as simple constants in the service.
  - CreditBalance model (user, balance, updated_at).
  - CreditTransaction model (user, amount, model_used, description, created_at).
  - Routers accept optional credits_service for backward compat.
  - Frontend shows credits in nav bar and account page.

repos:
  - name: braid
    path: /Users/you/bitbook/braid
    base_branch: main
    description: Django backend — models, services, API, generation routers

  - name: fabric
    path: /Users/you/bitbook/fabric
    base_branch: main
    description: React frontend — Chakra UI, account page, nav, API client
```

```bash
beehive architect create credits -c credits-architect.yaml
# ✓ Created architect: credits
#   ID: c8d63ee8

beehive project link bitbook c8d6
```

### Step 3: Generate the plan

```bash
beehive architect plan c8d6 \
  -d "Implement a credits system: models, service, API endpoint, \
      router integration, frontend display in nav and account page"
```

Claude generates ordered tickets:

```
✓ Plan created: f7e2a1b3

  #  ID        Title                              Repo    Status
  1  t1abc123  Add CreditBalance & Transaction    braid   pending
  2  t2def456  Create CreditService class         braid   pending
  3  t3ghi789  Add /api/credits endpoint           braid   pending
  4  t4jkl012  Integrate credits into routers     braid   pending
  5  t5mno345  Add credits API client methods     fabric  pending
  6  t6pqr678  Show credits in nav bar            fabric  pending
  7  t7stu901  Add credits to account page        fabric  pending
```

### Step 4: Execute sequentially

```bash
# Assign ticket #1 (sequential mode — only first pending)
beehive architect assign c8d6

# ✓ Assigned "Add CreditBalance & Transaction"
#   -> session a1b2c3d4 (docker)
#   Preview: http://add-creditbalance.localhost:3100
```

### Step 5: Watch the pipeline

```bash
beehive architect watch c8d6 --interval 30
```

Output as the pipeline progresses:

```
Watching plan f7e2a1b3 (mode: sequential, interval: 30s)
Press Ctrl+C to stop.

1 assigned, 6 pending
1 completed, 6 pending
✓ Ticket "Add CreditBalance & Transaction" PR merged!

Auto-assigning next ticket: #2 Create CreditService class
✓ Assigned "Create CreditService class" -> session e5f6g7h8 (docker)

1 merged, 1 assigned, 5 pending
1 merged, 1 completed, 5 pending
✓ Ticket "Create CreditService class" PR merged!

Auto-assigning next ticket: #3 Add /api/credits endpoint
...

All tickets are terminal (merged or failed). Done!
```

### Step 6: Review the result

```bash
beehive architect status c8d6
```

```
Plan f7e2a1b3: Implement a credits system...
  Status: 7 merged

  #  ID        Title                           Repo    Status   Branch
  1  t1abc123  Add CreditBalance & Transaction braid   merged   beehive/add-credit-a1b2
  2  t2def456  Create CreditService class      braid   merged   beehive/create-cred-e5f6
  3  t3ghi789  Add /api/credits endpoint        braid   merged   beehive/add-api-cre-g7h8
  4  t4jkl012  Integrate credits into routers  braid   merged   beehive/integrate-c-i9j0
  5  t5mno345  Add credits API client methods  fabric  merged   beehive/add-credits-k1l2
  6  t6pqr678  Show credits in nav bar         fabric  merged   beehive/show-credit-m3n4
  7  t7stu901  Add credits to account page     fabric  merged   beehive/add-credits-o5p6
```

### Step 7: Get strategic feedback

```bash
beehive cto chat bitbook
> The credits system is merged. What should we tackle next?
> Are there any risks with the current implementation we should address?
> exit
```

---

## CLI Reference

### Session commands

```
beehive create <name>                    Create an agent session
  -i, --instructions TEXT                  Instructions (or @file)
  -w, --working-dir PATH                  Repository path
  -b, --base-branch TEXT                   Base branch (default: main)
  -p, --prompt TEXT                        Initial prompt (or @file)
  -y, --auto-approve                       Auto-approve Claude actions
  --claude-md TEXT                          Extra CLAUDE.md content
  --no-docker                              Force host mode

beehive list [--status STATUS]           List sessions
beehive attach <id>                      Attach to tmux session (Ctrl+B D to detach)
beehive send <id> <text>                 Send prompt to agent (or @file)
beehive logs <id> [-f] [-n LINES]        View session logs
beehive status <id>                      Show detailed session info
beehive pr <id> [-t TITLE] [-d] [-b BR]  Create PR from agent work
beehive stop <id>                        Stop running session
beehive delete <id> [-f]                 Delete session and workspace
```

### Architect commands

```
beehive architect list                            List architects
beehive architect create <name> -c FILE           Create from YAML config
beehive architect show <id>                       Show architect details
beehive architect plan <id> -d "directive"        Generate plan with Claude
beehive architect tickets <id> [plan_id]          List tickets (sorted by order)
beehive architect edit-ticket <ticket_id>         Edit ticket fields
  -t, --title TEXT
  -d, --description TEXT
  -r, --repo TEXT

beehive architect assign <id>                     Assign tickets to agents
  --ticket, -t ID                                   Assign specific ticket
  --parallel                                        Assign all pending at once
  --no-auto-approve                                 Disable auto-approve
  --no-docker                                       Force host mode

beehive architect status <id> [plan_id]           Sync and show plan status
beehive architect watch <id>                      Watch plan, auto-assign on merge
  --plan, -p ID                                     Specific plan
  --interval, -i SECS                               Poll interval (default: 15)
```

### Project commands

```
beehive project create <name> [-c FILE] [-d DESC]   Create project
beehive project list                                 List projects
beehive project show <id>                            Show project details
beehive project delete <id> [-f]                     Delete project
beehive project link <project_id> <architect_id>     Link architect
beehive project unlink <project_id> <architect_id>   Unlink architect

beehive project claude-md show <id>                  Show project CLAUDE.md
beehive project claude-md set <id> <content>         Set (or @file)
beehive project claude-md edit <id>                  Edit in $EDITOR

beehive project preview list                         List active previews
beehive project preview stop <session_id>            Stop preview
beehive project preview stop-all                     Stop all previews
```

### CTO commands

```
beehive cto chat <project_id> [--clear]    Interactive AI strategy chat
beehive cto brief <project_id> [--raw]     Project status brief
beehive cto history <project_id>           Show conversation history
beehive cto clear <project_id>             Clear conversation history
```

### Researcher commands

```
beehive researcher list                              List researchers
beehive researcher create <name> -c FILE             Create from YAML
beehive researcher show <id>                         Show details
beehive researcher study <id> -d "directive"         Generate study
beehive researcher experiments <id> [study_id]       List experiments
beehive researcher edit-experiment <experiment_id>   Edit experiment
beehive researcher assign <id>                       Assign experiments
beehive researcher status <id>                       Show study status
beehive researcher watch <id>                        Watch study progress
```

### Config commands

```
beehive config claude-md show              Show global CLAUDE.md
beehive config claude-md edit              Edit in $EDITOR
beehive config claude-md set <content>     Set (or @file)
```

### TUI

```
beehive ui                                 Launch terminal dashboard
```

---

## Data Storage

All state lives in `~/.beehive/` (configurable with `--data-dir`):

```
~/.beehive/
├── sessions.json                          All agent sessions
├── system_prompt.txt                      Global system prompt for agents
├── CLAUDE.md                              Global CLAUDE.md injected into all worktrees
├── preview_state.json                     Active preview environments
│
├── logs/
│   ├── a1b2c3d4.log                      Session output log
│   └── preview-a1b2c3d4.log              Preview startup log
│
├── worktrees/
│   ├── beehive-a1b2c3d4/                 Agent workspace (worktree or clone)
│   └── beehive-e5f6g7h8/
│
├── architects/
│   ├── architects.json                    Architect metadata
│   └── c8d63ee8/
│       └── plans.json                     Plans and tickets for this architect
│
├── researchers/
│   ├── researchers.json                   Researcher metadata
│   └── r1a2b3c4/
│       └── studies.json                   Studies and experiments
│
└── projects/
    ├── projects.json                      Project metadata
    └── p1x2y3z4/
        ├── conversation.json              CTO chat history
        └── CLAUDE.md                      Project-level CLAUDE.md
```

All IDs support **partial matching** — `beehive attach a1b2` matches `a1b2c3d4`. Usually the first 4 characters are enough.

---

## Tips and Best Practices

**Naming**: Use descriptive session/ticket names. `fix-auth-token-refresh` is much better than `task1`.

**Instructions**: Be specific. "Add pagination to GET /users with limit/offset parameters, default limit 20, max 100" beats "improve the API."

**Sequential for dependencies**: If ticket B depends on ticket A's code, use sequential mode so B starts on a branch that includes A's merged changes.

**Parallel for independence**: If tickets target different repos or unrelated parts of the same repo, use `--parallel` to maximize throughput.

**CLAUDE.md layering**: Put universal rules in global CLAUDE.md, project-specific conventions in project CLAUDE.md, and repo-specific patterns in each repo's `.claude/CLAUDE.md`.

**Review before merge**: Even with auto-approve, review agent PRs before merging. The `watch` command only auto-assigns the *next* ticket — it does not auto-merge.

**Cleanup**: Delete completed sessions periodically to keep lists manageable.

```bash
# Delete all stopped sessions
beehive list --status stopped
beehive delete <id> -f
```

---

## Troubleshooting

### "tmux session not found"

The agent may have crashed. Check logs:

```bash
beehive logs <id> -n 200
tmux ls  # see what tmux sessions exist
```

### "claude: command not found"

Claude Code isn't in PATH inside the tmux session. Install globally:

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### PR creation fails

Ensure gh CLI is authenticated:

```bash
gh auth status
gh auth login  # if needed
```

### Docker build fails

Check that Docker Desktop is running, then rebuild:

```bash
docker build -t beehive-agent .devcontainer/
```

### Tickets stuck in "assigned"

The session may have finished but status hasn't synced. Run:

```bash
beehive architect status <id>  # forces sync
```

### Watch doesn't detect merge

The `watch` command uses `gh pr view <url> --json state`. Ensure `gh` is authenticated and the PR URL is correct:

```bash
gh pr view <pr_url> --json state
```

---

## Development

### Running tests

```bash
pip install -e ".[dev]"
pytest tests/
pytest tests/test_architect.py -v  # specific file
```

### Code style

```bash
black beehive/
ruff check beehive/
```

### Project structure

```
beehive/
├── cli.py                  Main CLI entry point (session commands)
├── cli_architect.py        Architect CLI commands
├── cli_project.py          Project + CTO CLI commands
├── cli_researcher.py       Researcher CLI commands
├── core/
│   ├── architect.py        Architect/Plan/Ticket models
│   ├── architect_storage.py  Architect persistence
│   ├── config.py           System prompt + CLAUDE.md management
│   ├── cto.py              AI CTO advisor
│   ├── docker_manager.py   Docker container lifecycle
│   ├── git_ops.py          Git worktree/branch operations
│   ├── planner.py          AI plan generation (Architect)
│   ├── pr_creator.py       GitHub PR creation via gh
│   ├── preview.py          Preview environment management
│   ├── project.py          Project models
│   ├── project_storage.py  Project persistence
│   ├── research_planner.py AI study generation (Researcher)
│   ├── researcher.py       Researcher/Study/Experiment models
│   ├── researcher_storage.py Researcher persistence
│   ├── session.py          Session models + manager
│   ├── storage.py          Session persistence
│   └── tmux_manager.py     tmux session control
├── tui/
│   ├── __init__.py
│   ├── app.py              Textual TUI application
│   ├── modals.py           TUI modal dialogs
│   └── styles.tcss         TUI stylesheet
└── tests/
    ├── test_architect.py
    ├── test_config.py
    └── test_project.py
```

---

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic
- Uses [tmux](https://github.com/tmux/tmux) for session management
- CLI built with [Click](https://click.palletsprojects.com/) and [Rich](https://rich.readthedocs.io/)
- TUI built with [Textual](https://textual.textualize.io/)
