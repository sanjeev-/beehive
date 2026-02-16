#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Beehive Universal Installer
# Works on macOS and Linux (Debian/Ubuntu, Fedora, Arch)
# Usage:
#   curl -fsSL https://openclaw.ai/install.sh | bash
#   bash install.sh
#   bash install.sh --ci
# ─────────────────────────────────────────────────────────────────────────────

BEEHIVE_VERSION="latest"
BEEHIVE_REPO="https://github.com/sanjeev-/beehive.git"
BEEHIVE_HOME="$HOME/.beehive"
BEEHIVE_VENV="$BEEHIVE_HOME/venv"
BEEHIVE_BIN="$HOME/.local/bin"
TOTAL_STEPS=10

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────
WHITE='\033[1;37m'
GRAY='\033[0;37m'
YELLOW='\033[38;2;255;239;112m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Piped stdin handling
# When run via `curl | bash`, stdin is the pipe (containing the script), not
# the terminal. Detect this and re-execute from a temp file so interactive
# prompts work. We distinguish `curl | bash` (BASH_SOURCE is empty/"bash")
# from `bash install.sh` in a non-tty env (BASH_SOURCE is a real file).
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -t 0 ]; then
    _SCRIPT_PATH="${BASH_SOURCE[0]:-}"
    if [ -z "$_SCRIPT_PATH" ] || [ ! -f "$_SCRIPT_PATH" ]; then
        TMPSCRIPT=$(mktemp)
        cat > "$TMPSCRIPT"
        exec bash "$TMPSCRIPT" "$@"
    fi
    unset _SCRIPT_PATH
fi

# ─────────────────────────────────────────────────────────────────────────────
# CI / Non-interactive mode
# ─────────────────────────────────────────────────────────────────────────────
CI_MODE=0
if [[ "${1:-}" == "--ci" ]] || [[ "${BEEHIVE_INSTALL_CI:-0}" == "1" ]]; then
    CI_MODE=1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────
info() {
    printf "${WHITE}%s${RESET}\n" "$*"
}

detail() {
    printf "${GRAY}  %s${RESET}\n" "$*"
}

emphasis() {
    printf "${YELLOW}%s${RESET}\n" "$*"
}

success() {
    printf "${GREEN}  ✓ %s${RESET}\n" "$*"
}

fail() {
    printf "${RED}  ✗ %s${RESET}\n" "$*"
}

step_header() {
    local step_num="$1"
    local label="$2"
    printf "\n${YELLOW}[%s/%s]${RESET}  ${WHITE}%s${RESET}\n" "$step_num" "$TOTAL_STEPS" "$label"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"

    if [[ "$CI_MODE" == "1" ]]; then
        [[ "$default" == "y" ]] && return 0 || return 1
    fi

    local yn_hint="[Y/n]"
    [[ "$default" == "n" ]] && yn_hint="[y/N]"

    while true; do
        printf "${WHITE}  %s %s ${RESET}" "$prompt" "$yn_hint"
        read -r answer
        answer="${answer:-$default}"
        case "$answer" in
            [Yy]*) return 0 ;;
            [Nn]*) return 1 ;;
            *) detail "Please answer y or n." ;;
        esac
    done
}

ask_input() {
    local prompt="$1"
    local var_name="$2"

    if [[ "$CI_MODE" == "1" ]]; then
        return 0
    fi

    printf "${WHITE}  %s: ${RESET}" "$prompt"
    read -r "$var_name"
}

# ─────────────────────────────────────────────────────────────────────────────
# Platform detection
# ─────────────────────────────────────────────────────────────────────────────
detect_platform() {
    OS_RAW=$(uname -s)
    ARCH_RAW=$(uname -m)

    case "$OS_RAW" in
        Darwin) OS="macos" ;;
        Linux)  OS="linux" ;;
        *)      fail "Unsupported OS: $OS_RAW"; exit 1 ;;
    esac

    case "$ARCH_RAW" in
        x86_64)  ARCH="x86_64" ;;
        aarch64) ARCH="arm64" ;;
        arm64)   ARCH="arm64" ;;
        *)       fail "Unsupported architecture: $ARCH_RAW"; exit 1 ;;
    esac

    DISTRO="unknown"
    PKG_MGR="unknown"

    if [[ "$OS" == "macos" ]]; then
        DISTRO="macos"
        if command -v brew &>/dev/null; then
            PKG_MGR="brew"
        else
            PKG_MGR="none"
        fi
    elif [[ "$OS" == "linux" ]]; then
        if [[ -f /etc/os-release ]]; then
            # shellcheck disable=SC1091
            source /etc/os-release
            case "${ID:-}" in
                ubuntu|debian|pop|linuxmint|elementary)
                    DISTRO="debian"
                    PKG_MGR="apt"
                    ;;
                fedora|rhel|centos|rocky|alma)
                    DISTRO="fedora"
                    PKG_MGR="dnf"
                    # Fall back to yum if dnf isn't available
                    command -v dnf &>/dev/null || PKG_MGR="yum"
                    ;;
                arch|manjaro|endeavouros)
                    DISTRO="arch"
                    PKG_MGR="pacman"
                    ;;
                *)
                    # Try to detect package manager directly
                    if command -v apt-get &>/dev/null; then
                        DISTRO="debian"
                        PKG_MGR="apt"
                    elif command -v dnf &>/dev/null; then
                        DISTRO="fedora"
                        PKG_MGR="dnf"
                    elif command -v pacman &>/dev/null; then
                        DISTRO="arch"
                        PKG_MGR="pacman"
                    else
                        fail "Could not detect Linux package manager"
                        exit 1
                    fi
                    ;;
            esac
        fi
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Package install helper
# ─────────────────────────────────────────────────────────────────────────────
pkg_install() {
    local pkg="$1"
    case "$PKG_MGR" in
        brew)   brew install "$pkg" ;;
        apt)    sudo apt-get update -qq && sudo apt-get install -y -qq "$pkg" ;;
        dnf)    sudo dnf install -y -q "$pkg" ;;
        yum)    sudo yum install -y -q "$pkg" ;;
        pacman) sudo pacman -S --noconfirm "$pkg" ;;
        *)      fail "No package manager available to install $pkg"; return 1 ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────────
# Shell profile detection
# ─────────────────────────────────────────────────────────────────────────────
detect_shell_profile() {
    SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
    case "$SHELL_NAME" in
        zsh)  SHELL_PROFILE="$HOME/.zshrc" ;;
        bash) SHELL_PROFILE="$HOME/.bashrc" ;;
        fish) SHELL_PROFILE="$HOME/.config/fish/config.fish" ;;
        *)    SHELL_PROFILE="$HOME/.bashrc" ;;
    esac

    # Ensure the profile file exists
    touch "$SHELL_PROFILE"
}

# Add a line to shell profile idempotently using a marker comment
add_to_profile() {
    local line="$1"
    local marker="${2:-# Added by beehive installer}"
    local full_line="$line $marker"

    if grep -qF "$marker" "$SHELL_PROFILE" 2>/dev/null; then
        # Update existing line
        local escaped_line
        escaped_line=$(printf '%s\n' "$full_line" | sed 's/[&/\]/\\&/g')
        sed -i.bak "/$marker/c\\
$escaped_line" "$SHELL_PROFILE"
        rm -f "${SHELL_PROFILE}.bak"
    else
        echo "$full_line" >> "$SHELL_PROFILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Version comparison: returns 0 if $1 >= $2
# ─────────────────────────────────────────────────────────────────────────────
version_gte() {
    local v1="$1" v2="$2"
    # Use sort -V if available, otherwise do simple numeric comparison
    if printf '%s\n%s' "$v2" "$v1" | sort -V -C 2>/dev/null; then
        return 0
    fi
    # Fallback: compare major.minor
    local v1_major v1_minor v2_major v2_minor
    v1_major=$(echo "$v1" | cut -d. -f1)
    v1_minor=$(echo "$v1" | cut -d. -f2)
    v2_major=$(echo "$v2" | cut -d. -f1)
    v2_minor=$(echo "$v2" | cut -d. -f2)
    if [[ "$v1_major" -gt "$v2_major" ]]; then return 0; fi
    if [[ "$v1_major" -eq "$v2_major" && "$v1_minor" -ge "$v2_minor" ]]; then return 0; fi
    return 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────
print_banner() {
    printf "\n"
    printf "${YELLOW}"
    cat << 'BANNER'
    ____             __    _
   / __ )___  ___  / /_  (_)   _____
  / __  / _ \/ _ \/ __ \/ / | / / _ \
 / /_/ /  __/  __/ / / / /| |/ /  __/
/_____/\___/\___/_/ /_/_/ |___/\___/

BANNER
    printf "${RESET}"
    emphasis "    Universal Installer"
    printf "\n"
    detail "OS: $OS ($ARCH) | Distro: $DISTRO | Pkg: $PKG_MGR"
    printf "\n"
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 1: Python 3.9+
# ═════════════════════════════════════════════════════════════════════════════
step_python() {
    step_header 1 "Python 3.9+"

    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            if [[ -n "$ver" ]] && version_gte "$ver" "3.9"; then
                python_cmd="$cmd"
                success "Found $cmd $ver"
                break
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        info "  Python 3.9+ not found. Installing..."
        case "$PKG_MGR" in
            brew)   pkg_install python@3 ;;
            apt)
                sudo apt-get update -qq
                sudo apt-get install -y -qq python3 python3-pip python3-venv
                ;;
            dnf|yum) pkg_install python3 ;;
            pacman)  pkg_install python ;;
        esac

        for cmd in python3 python; do
            if command -v "$cmd" &>/dev/null; then
                local ver
                ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
                if [[ -n "$ver" ]] && version_gte "$ver" "3.9"; then
                    python_cmd="$cmd"
                    break
                fi
            fi
        done

        if [[ -z "$python_cmd" ]]; then
            fail "Could not install Python 3.9+."
            exit 1
        fi
        success "Installed $python_cmd $("$python_cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
    fi

    PYTHON_CMD="$python_cmd"

    # Ensure pip and venv are available on Debian-based systems
    if [[ "$DISTRO" == "debian" ]]; then
        if ! "$PYTHON_CMD" -m pip --version &>/dev/null || ! "$PYTHON_CMD" -m venv --help &>/dev/null; then
            detail "Installing python3-pip and python3-venv..."
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3-pip python3-venv
            success "pip and venv installed"
        fi
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 2: git
# ═════════════════════════════════════════════════════════════════════════════
step_git() {
    step_header 2 "git"

    if command -v git &>/dev/null; then
        local ver
        ver=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        success "Found git $ver"
        return
    fi

    info "  git not found. Installing..."
    case "$PKG_MGR" in
        brew)   pkg_install git ;;
        apt)    pkg_install git ;;
        dnf|yum) pkg_install git ;;
        pacman) pkg_install git ;;
    esac

    if command -v git &>/dev/null; then
        success "Installed git $(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    else
        fail "Could not install git."
        exit 1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 3: tmux
# ═════════════════════════════════════════════════════════════════════════════
step_tmux() {
    step_header 3 "tmux"

    if command -v tmux &>/dev/null; then
        local ver
        ver=$(tmux -V 2>&1 | grep -oE '[0-9]+\.[0-9a-z]+' | head -1)
        success "Found tmux $ver"
        return
    fi

    info "  tmux not found. Installing..."
    case "$PKG_MGR" in
        brew)   pkg_install tmux ;;
        apt)    pkg_install tmux ;;
        dnf|yum) pkg_install tmux ;;
        pacman) pkg_install tmux ;;
    esac

    if command -v tmux &>/dev/null; then
        success "Installed tmux $(tmux -V 2>&1 | grep -oE '[0-9]+\.[0-9a-z]+' | head -1)"
    else
        fail "Could not install tmux."
        exit 1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 4: Node.js 18+
# ═════════════════════════════════════════════════════════════════════════════
step_node() {
    step_header 4 "Node.js 18+"

    if command -v node &>/dev/null; then
        local ver
        ver=$(node --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if version_gte "$ver" "18.0"; then
            success "Found Node.js $ver"
            return
        else
            detail "Found Node.js $ver (need 18+), upgrading..."
        fi
    fi

    info "  Node.js 18+ not found. Installing..."
    case "$PKG_MGR" in
        brew)
            pkg_install node
            ;;
        apt)
            # Use NodeSource for a recent Node.js version
            if ! command -v node &>/dev/null || ! version_gte "$(node --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')" "18.0"; then
                detail "Adding NodeSource repository for Node.js 20.x..."
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
                sudo apt-get install -y -qq nodejs
            fi
            ;;
        dnf|yum)
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo dnf install -y -q nodejs || sudo yum install -y -q nodejs
            ;;
        pacman)
            pkg_install nodejs npm
            ;;
    esac

    if command -v node &>/dev/null; then
        local ver
        ver=$(node --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if version_gte "$ver" "18.0"; then
            success "Installed Node.js $ver"
        else
            fail "Installed Node.js $ver but need 18+."
            exit 1
        fi
    else
        fail "Could not install Node.js."
        exit 1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 5: GitHub CLI (gh)
# ═════════════════════════════════════════════════════════════════════════════
step_gh() {
    step_header 5 "GitHub CLI (gh)"

    if command -v gh &>/dev/null; then
        local ver
        ver=$(gh --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        success "Found gh $ver"
        return
    fi

    info "  GitHub CLI not found. Installing..."
    case "$PKG_MGR" in
        brew)
            pkg_install gh
            ;;
        apt)
            detail "Adding GitHub CLI repository..."
            sudo mkdir -p -m 755 /etc/apt/keyrings
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
            sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli-stable.list > /dev/null
            sudo apt-get update -qq
            sudo apt-get install -y -qq gh
            ;;
        dnf|yum)
            sudo dnf install -y -q 'dnf-command(config-manager)' 2>/dev/null || true
            sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo 2>/dev/null || true
            sudo dnf install -y -q gh || sudo yum install -y -q gh
            ;;
        pacman)
            pkg_install github-cli
            ;;
    esac

    if command -v gh &>/dev/null; then
        success "Installed gh $(gh --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    else
        fail "Could not install GitHub CLI."
        exit 1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 6: Claude Code
# ═════════════════════════════════════════════════════════════════════════════
step_claude_code() {
    step_header 6 "Claude Code"

    if command -v claude &>/dev/null; then
        local ver
        ver=$(claude --version 2>/dev/null || echo "unknown")
        success "Found Claude Code ($ver)"
        return
    fi

    info "  Claude Code not found. Installing via npm..."

    # Try global npm install
    if npm install -g @anthropic-ai/claude-code 2>/dev/null; then
        success "Installed Claude Code"
        return
    fi

    # If it failed (permissions), try with sudo on Linux
    if [[ "$OS" == "linux" ]]; then
        detail "Retrying with sudo..."
        if sudo npm install -g @anthropic-ai/claude-code 2>/dev/null; then
            success "Installed Claude Code (via sudo)"
            return
        fi
    fi

    # Last resort: suggest npm prefix fix
    fail "Could not install Claude Code globally."
    detail "Try: mkdir -p ~/.npm-global && npm config set prefix '~/.npm-global'"
    detail "Then add ~/.npm-global/bin to your PATH and re-run this installer."
    exit 1
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 7: Docker (optional)
# ═════════════════════════════════════════════════════════════════════════════
step_docker() {
    step_header 7 "Docker (optional)"

    if command -v docker &>/dev/null; then
        local ver
        ver=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        success "Found Docker $ver"
        return
    fi

    if [[ "$CI_MODE" == "1" ]]; then
        detail "Skipping Docker in CI mode"
        return
    fi

    if ! ask_yes_no "Docker is not installed. Install it?" "n"; then
        detail "Skipping Docker installation"
        return
    fi

    case "$OS" in
        macos)
            if [[ "$PKG_MGR" == "brew" ]]; then
                detail "Installing Docker Desktop via Homebrew..."
                brew install --cask docker
                success "Docker Desktop installed. Please open it from Applications to finish setup."
            else
                detail "Please install Docker Desktop from https://docker.com/products/docker-desktop"
            fi
            ;;
        linux)
            detail "Installing Docker via official script..."
            curl -fsSL https://get.docker.com | sudo sh
            sudo usermod -aG docker "$USER" 2>/dev/null || true
            if command -v docker &>/dev/null; then
                success "Installed Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
                detail "Note: You may need to log out and back in for group changes to take effect."
            else
                fail "Docker installation may require a restart."
            fi
            ;;
    esac
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 8: Anthropic API Key
# ═════════════════════════════════════════════════════════════════════════════
step_api_key() {
    step_header 8 "Anthropic API Key"

    # Check if already set in current environment
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        local masked="${ANTHROPIC_API_KEY:0:10}...${ANTHROPIC_API_KEY: -4}"
        detail "Found in environment: $masked"

        # Validate the key
        if validate_api_key "$ANTHROPIC_API_KEY"; then
            success "API key is valid"
            # Ensure it's in shell profile
            add_to_profile "export ANTHROPIC_API_KEY=\"$ANTHROPIC_API_KEY\""
            return
        else
            fail "API key validation failed"
            if [[ "$CI_MODE" == "1" ]]; then
                fail "Invalid ANTHROPIC_API_KEY in CI mode. Exiting."
                exit 1
            fi
        fi
    fi

    if [[ "$CI_MODE" == "1" ]]; then
        if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
            fail "ANTHROPIC_API_KEY not set in CI mode. Exiting."
            exit 1
        fi
        return
    fi

    # Interactive: prompt for key
    while true; do
        printf "${WHITE}  Enter your Anthropic API key: ${RESET}"
        read -rs api_key
        printf "\n"

        if [[ -z "$api_key" ]]; then
            detail "No key entered. You can set it later with:"
            detail "  export ANTHROPIC_API_KEY=\"sk-ant-...\""
            return
        fi

        if validate_api_key "$api_key"; then
            success "API key is valid"
            export ANTHROPIC_API_KEY="$api_key"
            add_to_profile "export ANTHROPIC_API_KEY=\"$api_key\""
            success "Saved to $SHELL_PROFILE"
            return
        else
            fail "API key validation failed. Please try again."
        fi
    done
}

validate_api_key() {
    local key="$1"
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST https://api.anthropic.com/v1/messages \
        -H "x-api-key: $key" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d '{"model":"claude-sonnet-4-20250514","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
        --max-time 10 2>/dev/null) || true

    # 200 = success, 400 = bad request (but key is valid), 429 = rate limited (key is valid)
    case "$http_code" in
        200|400|429) return 0 ;;
        *)           return 1 ;;
    esac
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 9: GitHub Auth
# ═════════════════════════════════════════════════════════════════════════════
step_gh_auth() {
    step_header 9 "GitHub Auth"

    if gh auth status &>/dev/null; then
        local user
        user=$(gh api user --jq '.login' 2>/dev/null || echo "authenticated")
        success "Logged in as $user"
        return
    fi

    if [[ "$CI_MODE" == "1" ]]; then
        if [[ -n "${GH_TOKEN:-}" ]]; then
            detail "Using GH_TOKEN for authentication"
            echo "$GH_TOKEN" | gh auth login --with-token 2>/dev/null
            if gh auth status &>/dev/null; then
                success "Authenticated via GH_TOKEN"
                return
            fi
        fi
        detail "Skipping GitHub auth in CI mode (no GH_TOKEN)"
        return
    fi

    info "  GitHub CLI is not authenticated."
    if ask_yes_no "Run 'gh auth login' now?" "y"; then
        gh auth login
        if gh auth status &>/dev/null; then
            success "GitHub authentication complete"
        else
            fail "GitHub authentication did not complete"
            detail "You can run 'gh auth login' later."
        fi
    else
        detail "Skipping. Run 'gh auth login' when you're ready."
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  STEP 10: Install Beehive
# ═════════════════════════════════════════════════════════════════════════════
step_install_beehive() {
    step_header 10 "Install Beehive"

    # Create beehive home directory
    mkdir -p "$BEEHIVE_HOME"
    mkdir -p "$BEEHIVE_BIN"

    # Create or update the dedicated venv
    if [[ -d "$BEEHIVE_VENV" ]]; then
        detail "Updating existing venv at $BEEHIVE_VENV..."
    else
        detail "Creating venv at $BEEHIVE_VENV..."
        "$PYTHON_CMD" -m venv "$BEEHIVE_VENV"
    fi

    # Upgrade pip in the venv
    "$BEEHIVE_VENV/bin/pip" install --upgrade pip --quiet 2>/dev/null || true

    # Install beehive from git
    detail "Installing beehive from $BEEHIVE_REPO..."
    "$BEEHIVE_VENV/bin/pip" install "git+${BEEHIVE_REPO}" --quiet

    # Verify the beehive command exists in the venv
    if [[ ! -f "$BEEHIVE_VENV/bin/beehive" ]]; then
        fail "beehive binary not found in venv after install."
        exit 1
    fi

    # Create symlink
    ln -sf "$BEEHIVE_VENV/bin/beehive" "$BEEHIVE_BIN/beehive"
    success "Symlinked beehive → $BEEHIVE_BIN/beehive"

    # Ensure ~/.local/bin is on PATH
    ensure_local_bin_on_path

    # Verify beehive works
    if "$BEEHIVE_BIN/beehive" --help &>/dev/null; then
        local ver
        ver=$("$BEEHIVE_BIN/beehive" --version 2>/dev/null || echo "installed")
        success "Beehive is ready ($ver)"
    else
        fail "beehive --help failed. Check the installation."
        exit 1
    fi
}

ensure_local_bin_on_path() {
    if echo "$PATH" | tr ':' '\n' | grep -qx "$BEEHIVE_BIN"; then
        return
    fi

    detail "Adding $BEEHIVE_BIN to PATH in $SHELL_PROFILE..."
    add_to_profile "export PATH=\"$BEEHIVE_BIN:\$PATH\"" "# Added by beehive installer (PATH)"
    export PATH="$BEEHIVE_BIN:$PATH"
    success "$BEEHIVE_BIN added to PATH"
}

# ═════════════════════════════════════════════════════════════════════════════
#  Homebrew bootstrap (macOS only)
# ═════════════════════════════════════════════════════════════════════════════
ensure_homebrew() {
    if [[ "$OS" != "macos" ]]; then
        return
    fi

    if command -v brew &>/dev/null; then
        return
    fi

    info "Homebrew is not installed."
    if [[ "$CI_MODE" == "1" ]] || ask_yes_no "Install Homebrew? (required for macOS packages)" "y"; then
        detail "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add Homebrew to PATH for Apple Silicon
        if [[ "$ARCH" == "arm64" && -f /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            add_to_profile 'eval "$(/opt/homebrew/bin/brew shellenv)"' "# Added by beehive installer (Homebrew)"
        elif [[ -f /usr/local/bin/brew ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi

        if command -v brew &>/dev/null; then
            PKG_MGR="brew"
            success "Homebrew installed"
        else
            fail "Homebrew installation failed."
            exit 1
        fi
    else
        fail "Homebrew is required on macOS. Cannot continue."
        exit 1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
#  Completion summary
# ═════════════════════════════════════════════════════════════════════════════
print_summary() {
    printf "\n"
    printf "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
    printf "${GREEN}  ✓ Beehive installation complete!${RESET}\n"
    printf "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
    printf "\n"
    detail "Get started:"
    printf "${WHITE}    beehive --help${RESET}\n"
    printf "\n"
    detail "If 'beehive' is not found, start a new terminal or run:"
    printf "${GRAY}    source $SHELL_PROFILE${RESET}\n"
    printf "\n"
}

# ═════════════════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════════════════
main() {
    detect_platform
    detect_shell_profile
    print_banner

    # macOS: ensure Homebrew is available before starting steps
    ensure_homebrew

    step_python
    step_git
    step_tmux
    step_node
    step_gh
    step_claude_code
    step_docker
    step_api_key
    step_gh_auth
    step_install_beehive

    print_summary
}

main "$@"
