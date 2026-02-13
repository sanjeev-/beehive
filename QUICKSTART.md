# Beehive Quick Start

Get started with Beehive in 5 minutes.

## Prerequisites Check

```bash
# Check you have everything
python3 --version    # Should be 3.9+
tmux -V             # Should be installed
gh --version        # Should be installed
claude --version    # Should be installed
gh auth status      # Should be authenticated
```

If anything is missing, see [INSTALL.md](INSTALL.md).

## Installation (1 minute)

```bash
# Navigate to the beehive directory
cd /Users/sanjeev/Documents/beehive

# Install dependencies (if not already done)
pip install click pydantic rich --user
```

## First Session (2 minutes)

```bash
# Navigate to a git repository
cd ~/code/your-project

# Create your first agent session
python3 -m beehive create hello-world \
  -i "Create a hello_world.py file that prints 'Hello from Beehive!'" \
  -w .

# You'll see output like:
# ✓ Created session: hello-world
#   ID: a1b2c3d4
#   Branch: beehive/hello-world-a1b2c3d4
#   Logs: ~/.beehive/logs/a1b2c3d4.log
#
# Attach: beehive attach a1b2c3d4
# View logs: beehive logs a1b2c3d4 -f
```

## Monitor Your Agent (30 seconds)

```bash
# Watch the logs in real-time
python3 -m beehive logs a1b2 -f

# Or attach to interact directly
python3 -m beehive attach a1b2
# Press Ctrl+B then D to detach
```

## List Sessions (10 seconds)

```bash
# See all your sessions
python3 -m beehive list

# See only running sessions
python3 -m beehive list --status running
```

## Get Detailed Status (10 seconds)

```bash
# Check what the agent is doing
python3 -m beehive status a1b2
```

## Send Additional Instructions (30 seconds)

```bash
# Give the agent more work
python3 -m beehive send a1b2 "Now add a docstring to the function"

# Watch the logs to see it working
python3 -m beehive logs a1b2 -f
```

## Create a Pull Request (30 seconds)

```bash
# When the agent is done, create a PR
python3 -m beehive pr a1b2 \
  -t "Add hello world script" \
  --draft

# You'll get a PR URL:
# ✓ PR created: https://github.com/user/repo/pull/123
```

## Clean Up (10 seconds)

```bash
# Stop the session
python3 -m beehive stop a1b2

# Delete the session
python3 -m beehive delete a1b2
```

## Next: Run Multiple Agents in Parallel

```bash
cd ~/code/your-project

# Start 3 agents working on different tasks
python3 -m beehive create fix-bug-1 \
  -i "Fix the login timeout bug" -w .

python3 -m beehive create add-feature-2 \
  -i "Add password reset functionality" -w .

python3 -m beehive create refactor-3 \
  -i "Refactor the authentication module" -w .

# Monitor all of them
python3 -m beehive list

# Check logs for any of them
python3 -m beehive logs fix-bug-1 -f
```

## Common Workflows

### Review Before PR

```bash
# 1. Create session
python3 -m beehive create my-task -i "Do something" -w ~/project

# 2. Let it run, check logs occasionally
python3 -m beehive logs my-task -f

# 3. Attach to review the work
python3 -m beehive attach my-task

# 4. If good, create PR
python3 -m beehive pr my-task
```

### Iterative Development

```bash
# 1. Create session
python3 -m beehive create feature -i "Build feature X" -w ~/project

# 2. Send follow-up instructions
python3 -m beehive send feature "Add error handling"
python3 -m beehive send feature "Add unit tests"
python3 -m beehive send feature "Update documentation"

# 3. Create PR when done
python3 -m beehive pr feature
```

### File-Based Instructions

```bash
# Create detailed instructions file
cat > task.txt << 'EOF'
Create a new API endpoint for user profile management:

1. Add GET /api/users/:id/profile
2. Add PUT /api/users/:id/profile
3. Include validation for all fields
4. Add comprehensive error handling
5. Write unit tests
6. Update API documentation

Follow RESTful conventions and existing code style.
EOF

# Create session with file-based instructions
python3 -m beehive create api-endpoint -i @task.txt -w ~/project
```

## Tips

1. **Partial IDs**: You can use partial session IDs like git
   ```bash
   python3 -m beehive logs a1b2  # Matches a1b2c3d4
   ```

2. **@file Syntax**: Use `@filename` for instructions or prompts
   ```bash
   python3 -m beehive create task -i @instructions.txt -p @prompt.txt
   ```

3. **Follow Logs**: Use `-f` to follow logs in real-time
   ```bash
   python3 -m beehive logs a1b2 -f
   ```

4. **Draft PRs**: Create draft PRs for review
   ```bash
   python3 -m beehive pr a1b2 --draft
   ```

5. **Custom Data Dir**: Use custom data directory
   ```bash
   python3 -m beehive --data-dir /custom/path list
   ```

## Getting Help

```bash
# General help
python3 -m beehive --help

# Command-specific help
python3 -m beehive create --help
python3 -m beehive pr --help
```

## What's Next?

- Read the full [README.md](README.md) for detailed documentation
- Check out [examples/](examples/) for more complex workflows
- See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute

## Troubleshooting

**Problem**: "tmux session not found"
```bash
# Check if tmux session exists
tmux ls

# View logs to see what happened
python3 -m beehive logs <session-id>
```

**Problem**: "Session not found"
```bash
# List all sessions to find the right ID
python3 -m beehive list
```

**Problem**: PR creation fails
```bash
# Make sure you're authenticated with gh
gh auth status
gh auth login
```

## Data Location

Beehive stores data in `~/.beehive/`:
```
~/.beehive/
├── sessions.json    # Session metadata
└── logs/
    └── a1b2c3d4.log # Session logs
```

View or edit directly if needed:
```bash
cat ~/.beehive/sessions.json | python3 -m json.tool
tail -f ~/.beehive/logs/a1b2c3d4.log
```

---

**You're ready!** Start orchestrating multiple AI agents on your codebase. 🐝
