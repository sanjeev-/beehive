# Git Worktrees in Beehive

## What are Git Worktrees?

Git worktrees allow you to have multiple working directories for the same repository, each checked out to a different branch. This is perfect for Beehive's parallel agent execution model.

## How Beehive Uses Worktrees

When you create a Beehive session, here's what happens:

```
Your Repository:
  ~/code/myproject/              # Main repository

Beehive Creates:
  ~/.beehive/worktrees/
    ├── beehive-a1b2c3d4/        # Agent 1's isolated workspace
    │   └── (branch: beehive/feature-a-a1b2)
    └── beehive-e5f6g7h8/        # Agent 2's isolated workspace
        └── (branch: beehive/feature-b-e5f6)
```

Each agent works in its own worktree, completely isolated from:
- Your main repository
- Other agents' worktrees

## Benefits

### 1. True Parallel Execution ✓

**Without worktrees** (the problem):
```bash
cd ~/code/myproject
beehive create agent1 -i "Task 1"  # Checks out beehive/task1-a1b2
beehive create agent2 -i "Task 2"  # Checks out beehive/task2-e5f6
# ❌ Both agents fighting over the same directory!
```

**With worktrees** (the solution):
```bash
cd ~/code/myproject
beehive create agent1 -i "Task 1"  # Creates ~/.beehive/worktrees/beehive-a1b2/
beehive create agent2 -i "Task 2"  # Creates ~/.beehive/worktrees/beehive-e5f6/
# ✓ Each agent has its own workspace!
```

### 2. No Interference

Your main repository stays untouched:
```bash
# Your work continues normally
cd ~/code/myproject
git status                    # Clean!
git branch --show-current     # Still on main

# Agents work in isolation
ls ~/.beehive/worktrees/
# beehive-a1b2/  beehive-e5f6/  beehive-f9g0/
```

### 3. Shared Git History

All worktrees share the same `.git` directory:
- Commits from any worktree are immediately visible to all
- Branches created in worktrees exist in the main repo
- Fetch/pull operations benefit all worktrees

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Main Repository: ~/code/myproject                          │
│  Branch: main                                               │
│  .git/ (shared by all worktrees)                            │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┬──────────────┐
                │                       │              │
    ┌───────────▼────────────┐ ┌───────▼──────────┐  │
    │ Worktree 1             │ │ Worktree 2       │  │
    │ ~/.beehive/worktrees/  │ │ ~/.beehive/      │  │
    │   beehive-a1b2/        │ │   worktrees/     │  │
    │                        │ │   beehive-e5f6/  │  │
    │ Branch:                │ │                  │  │
    │   beehive/ui-a1b2      │ │ Branch:          │  │
    │                        │ │   beehive/api-   │  │
    │ Agent:                 │ │     e5f6         │  │
    │   Claude Code          │ │                  │  │
    │   (tmux: beehive-a1b2) │ │ Agent:           │  │
    │                        │ │   Claude Code    │  │
    │ Task:                  │ │   (tmux:         │  │
    │   "Modernize UI"       │ │    beehive-e5f6) │  │
    │                        │ │                  │  │
    │ ✓ Isolated             │ │ Task:            │  │
    │ ✓ No conflicts         │ │   "Optimize API" │  │
    └────────────────────────┘ │                  │  │
                               │ ✓ Isolated       │  │
                               │ ✓ No conflicts   │ ...
                               └──────────────────┘
```

## Example Workflow

### Create Multiple Sessions

```bash
cd ~/code/myproject

# Create 3 agents working on different features
beehive create ui-modernize -i "Update UI components" -w .
beehive create api-optimize -i "Optimize database queries" -w .
beehive create add-tests -i "Improve test coverage" -w .

# Each gets its own worktree
ls ~/.beehive/worktrees/
# beehive-a1b2c3d4/
# beehive-e5f6g7h8/
# beehive-i9j0k1l2/
```

### Monitor Sessions

```bash
# List all running sessions
beehive list

# View logs for any session
beehive logs a1b2 -f

# Check status
beehive status e5f6
```

### Verify Isolation

```bash
# Your main repo is untouched
cd ~/code/myproject
git status
# On branch main, nothing to commit, working tree clean

# Check what branches exist
git branch
# * main
#   beehive/ui-modernize-a1b2
#   beehive/api-optimize-e5f6
#   beehive/add-tests-i9j0

# View worktrees
git worktree list
# /Users/you/code/myproject              main
# /Users/you/.beehive/worktrees/...      beehive/ui-modernize-a1b2
# /Users/you/.beehive/worktrees/...      beehive/api-optimize-e5f6
# /Users/you/.beehive/worktrees/...      beehive/add-tests-i9j0
```

### Create PRs

```bash
# When agents are done, create PRs
beehive pr a1b2 -t "Modernize UI components"
beehive pr e5f6 -t "Optimize database queries"
beehive pr i9j0 -t "Improve test coverage"

# All 3 PRs created independently!
```

## Cleanup

When you delete a session, the worktree is automatically removed:

```bash
beehive delete a1b2

# Worktree removed:
# ~/.beehive/worktrees/beehive-a1b2/ (deleted)

# Branch still exists for PR:
git branch
# * main
#   beehive/ui-modernize-a1b2  (still here)
#   beehive/api-optimize-e5f6
```

## Advanced Usage

### Manually Inspect Worktrees

```bash
# Navigate to an agent's workspace
cd ~/.beehive/worktrees/beehive-a1b2/

# It's a fully functional git repository
git status
git log
git diff

# Make manual changes if needed
vim src/component.tsx

# The agent will see these changes in its tmux session
```

### Share Work Between Agents

Since all worktrees share the same git history:

```bash
# Agent 1 creates a commit
cd ~/.beehive/worktrees/beehive-a1b2/
git commit -m "Add utility function"

# Agent 2 can immediately use it
cd ~/.beehive/worktrees/beehive-e5f6/
git merge beehive/agent1-branch
# Or: git cherry-pick <commit>
```

### Storage Location

Worktrees are stored in:
```
~/.beehive/worktrees/
  └── beehive-<session-id>/
```

You can customize this location with:
```bash
beehive --data-dir /custom/path create session -i "Task"
# Worktrees will be in: /custom/path/worktrees/
```

## Troubleshooting

### "worktree already exists"

If you see this error, a previous session wasn't cleaned up properly:

```bash
# List existing worktrees
git worktree list

# Remove stale worktree manually
git worktree remove ~/.beehive/worktrees/beehive-a1b2/ --force

# Or use the helper command (if implemented)
beehive cleanup
```

### Disk Space

Each worktree is a full working directory, so multiple sessions use disk space:

```bash
# Check worktree sizes
du -sh ~/.beehive/worktrees/*

# Clean up completed sessions
beehive list --status completed | awk '{print $1}' | xargs -I {} beehive delete {}
```

### Worktree Path

To find where an agent is working:

```bash
beehive status a1b2
# Shows:
#   Worktree: /Users/you/.beehive/worktrees/beehive-a1b2
```

## Comparison: With vs Without Worktrees

### Without Worktrees (Other Tools)

```
~/code/myproject/
  ├── .git/
  └── src/
      └── file.ts

# Problem: Only one branch can be checked out at a time
# Agent 1: git checkout beehive/task1  ← Changes the whole repo
# Agent 2: git checkout beehive/task2  ← Conflicts with Agent 1!
```

### With Worktrees (Beehive)

```
~/code/myproject/        # Main repo (untouched)
  ├── .git/ (shared)
  └── src/

~/.beehive/worktrees/
  ├── beehive-a1b2/      # Agent 1's workspace
  │   └── src/
  └── beehive-e5f6/      # Agent 2's workspace
      └── src/

# Solution: Each agent has its own workspace
# ✓ No conflicts
# ✓ Parallel execution
# ✓ Main repo untouched
```

## Git Worktree Commands Reference

Beehive manages worktrees automatically, but here are the underlying commands:

```bash
# Create worktree
git worktree add -b branch-name path/to/worktree base-branch

# List worktrees
git worktree list

# Remove worktree
git worktree remove path/to/worktree

# Prune stale worktrees
git worktree prune
```

## Best Practices

1. **Let Beehive Manage Worktrees** - Don't manually create/remove worktrees that Beehive is using

2. **Clean Up Sessions** - Delete sessions when done to free up disk space

3. **Monitor Disk Usage** - Multiple worktrees can use significant space

4. **Don't Edit Main Repo** - Work through Beehive sessions, not the main repository

5. **Use `beehive status`** - To find where an agent is working

## Conclusion

Git worktrees are the key technology that enables Beehive's parallel agent execution. They provide:

- ✅ True isolation between agents
- ✅ No branch conflicts
- ✅ Shared git history
- ✅ Your main repo stays clean
- ✅ Multiple agents on the same repo

This is what makes Beehive powerful for managing multiple Claude Code agents simultaneously!
