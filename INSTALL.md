# Installation Guide

## Prerequisites

Before installing Beehive, ensure you have the following:

### 1. Python 3.9 or higher

```bash
python3 --version
```

### 2. System Dependencies

#### macOS

```bash
# Install tmux (terminal multiplexer)
brew install tmux

# Install gh (GitHub CLI)
brew install gh

# Authenticate with GitHub
gh auth login
```

#### Ubuntu/Debian

```bash
# Install tmux
sudo apt-get update
sudo apt-get install tmux

# Install gh CLI
# See: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt-get update
sudo apt-get install gh

# Authenticate with GitHub
gh auth login
```

### 3. Claude Code

Make sure Claude Code is installed and authenticated:

```bash
# Verify Claude Code is installed
claude --version

# If not installed, install Claude Code
# See: https://docs.anthropic.com/claude/docs/claude-code
```

## Installation

### Option 1: Homebrew (Recommended)

The easiest way to install Beehive on macOS or Linux is using Homebrew:

```bash
# Add the Beehive tap
brew tap sanjeev-/beehive https://github.com/sanjeev-/beehive

# Install Beehive
brew install beehive

# Verify installation
beehive --help
```

This will automatically install:
- Python 3.12 (if not already installed)
- All Python dependencies in an isolated environment
- The `beehive` command in your PATH

### Option 2: Install using pip

```bash
# Install from PyPI (when published)
pip install beehive-cli

# Or install the latest from GitHub
pip install git+https://github.com/sanjeev-/beehive.git
```

### Option 3: Install from source (Development)

```bash
# Clone the repository
git clone https://github.com/sanjeev-/beehive.git
cd beehive

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install click pydantic rich

# Run using python -m
python -m beehive --help

# Or install in development mode
pip install -e .
beehive --help
```

## Verify Installation

### Test the CLI

```bash
# If installed with Homebrew or pip
beehive --help

# Or using python -m (if installed from source)
python3 -m beehive --help
```

You should see:

```
Usage: beehive [OPTIONS] COMMAND [ARGS]...

  Beehive - Manage multiple Claude Code agent sessions.

Options:
  --data-dir PATH  Data directory for Beehive sessions
  --help           Show this message and exit.

Commands:
  attach  Attach to agent's tmux session (interactive).
  create  Create a new agent session.
  delete  Delete a session.
  list    List all agent sessions.
  logs    View session logs.
  pr      Create PR from agent's work.
  send    Send a prompt to the agent.
  status  Show detailed status of a session.
  stop    Stop a running agent session.
```

### Verify System Dependencies

```bash
# Check tmux
tmux -V
# Should output: tmux 3.x or higher

# Check gh CLI
gh --version
# Should output: gh version 2.x or higher

# Check gh authentication
gh auth status
# Should show you're logged in

# Check Claude Code
claude --version
# Should output the Claude Code version
```

## First Run

Try creating your first session:

```bash
# Navigate to a git repository
cd ~/code/your-project

# Create a test session
beehive create test-session \
  -i "Write a hello world function in Python" \
  -w .

# List sessions
beehive list

# View logs
beehive logs test-session -f

# Stop the session
beehive stop test-session

# Delete the session
beehive delete test-session
```

## Troubleshooting

### "tmux: command not found"

Install tmux using the commands above for your operating system.

### "gh: command not found"

Install the GitHub CLI using the commands above for your operating system.

### "claude: command not found"

Make sure Claude Code is installed and in your PATH:

```bash
which claude
```

If not found, install Claude Code from: https://docs.anthropic.com/claude/docs/claude-code

### "ModuleNotFoundError: No module named 'click'"

Install the required dependencies:

```bash
pip install click pydantic rich
```

### Permission errors

If you get permission errors when creating sessions:

```bash
# Check data directory permissions
ls -la ~/.beehive

# If needed, fix permissions
chmod 755 ~/.beehive
chmod 644 ~/.beehive/sessions.json
```

## Updating

### Homebrew

```bash
brew update
brew upgrade beehive
```

### From source

```bash
cd beehive
git pull
pip install -e . --upgrade
```

### Using pip

```bash
pip install --upgrade beehive-cli
```

## Uninstallation

```bash
# If installed with Homebrew
brew uninstall beehive
brew untap sanjeev-/beehive

# If installed with pip
pip uninstall beehive-cli

# Clean up data directory (optional)
rm -rf ~/.beehive
```

## Next Steps

- Read the [README.md](README.md) for usage examples
- Check out [examples/](examples/) for sample workflows
- See [CONTRIBUTING.md](CONTRIBUTING.md) if you want to contribute

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Search existing issues: https://github.com/sanjeev-/beehive/issues
3. Open a new issue with:
   - Your operating system and version
   - Python version
   - Error messages and logs
   - Steps to reproduce
