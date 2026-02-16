#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Beehive Installer — Docker Test Runner
#
# Builds an Ubuntu 22.04 container with only curl/sudo, runs install.sh --ci,
# and verifies that beehive is installed and working.
#
# Usage:
#   bash tests/docker/test_install.sh
#
# Environment variables (optional):
#   ANTHROPIC_API_KEY  — passed into container for API key validation step
#   GH_TOKEN           — passed into container for GitHub auth step
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="beehive-install-test"
CONTAINER_NAME="beehive-install-test-$$"
TIMESTAMP=$(date +%s)

GREEN='\033[0;32m'
RED='\033[0;31m'
WHITE='\033[1;37m'
RESET='\033[0m'

pass() { printf "${GREEN}  ✓ PASS: %s${RESET}\n" "$*"; }
fail() { printf "${RED}  ✗ FAIL: %s${RESET}\n" "$*"; }
info() { printf "${WHITE}%s${RESET}\n" "$*"; }

cleanup() {
    docker rm -f "$CONTAINER_NAME" &>/dev/null || true
}
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────
info "Building test image..."
cp "$REPO_ROOT/install.sh" "$SCRIPT_DIR/install.sh"
docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile.install-test" "$SCRIPT_DIR"
rm -f "$SCRIPT_DIR/install.sh"
pass "Image built: $IMAGE_NAME"

# ─────────────────────────────────────────────────────────────────────────────
# Run installer
# ─────────────────────────────────────────────────────────────────────────────
info "Running installer in container..."

DOCKER_ENV_ARGS=()
[[ -n "${ANTHROPIC_API_KEY:-}" ]] && DOCKER_ENV_ARGS+=(-e "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
[[ -n "${GH_TOKEN:-}" ]]         && DOCKER_ENV_ARGS+=(-e "GH_TOKEN=$GH_TOKEN")

docker run \
    --name "$CONTAINER_NAME" \
    "${DOCKER_ENV_ARGS[@]+"${DOCKER_ENV_ARGS[@]}"}" \
    "$IMAGE_NAME"

EXIT_CODE=$(docker inspect "$CONTAINER_NAME" --format='{{.State.ExitCode}}')

if [[ "$EXIT_CODE" != "0" ]]; then
    fail "Installer exited with code $EXIT_CODE"
    info "Container logs:"
    docker logs "$CONTAINER_NAME"
    exit 1
fi
pass "Installer completed successfully"

# ─────────────────────────────────────────────────────────────────────────────
# Verify beehive works
# ─────────────────────────────────────────────────────────────────────────────
info "Verifying beehive --help..."

HELP_OUTPUT=$(docker run --rm \
    --entrypoint bash \
    "$IMAGE_NAME" \
    -c 'export PATH="$HOME/.local/bin:$PATH" && beehive --help' 2>&1) || true

if echo "$HELP_OUTPUT" | grep -qi "beehive\|usage\|commands"; then
    pass "beehive --help works"
else
    fail "beehive --help did not produce expected output"
    echo "$HELP_OUTPUT"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test branch creation (optional — requires GH_TOKEN)
# ─────────────────────────────────────────────────────────────────────────────
if [[ -n "${GH_TOKEN:-}" ]]; then
    BRANCH_NAME="test/installer-verify-${TIMESTAMP}"
    info "Creating test branch: $BRANCH_NAME"

    docker run --rm \
        -e "GH_TOKEN=$GH_TOKEN" \
        --entrypoint bash \
        "$IMAGE_NAME" \
        -c "
            export PATH=\"\$HOME/.local/bin:\$PATH\"
            echo \"\$GH_TOKEN\" | gh auth login --with-token
            git clone https://github.com/sanjeev-/beehive.git /tmp/beehive-test
            cd /tmp/beehive-test
            git checkout -b $BRANCH_NAME
            git commit --allow-empty -m 'test: installer verification $TIMESTAMP'
            git push origin $BRANCH_NAME
        " && pass "Test branch $BRANCH_NAME pushed (clean up manually)" \
          || fail "Test branch creation failed (non-critical)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
printf "\n"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pass "All Docker tests passed"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
