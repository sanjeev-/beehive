.PHONY: build clean formula release install-dev test lint help

help:
	@echo "Beehive - Makefile targets"
	@echo ""
	@echo "  build        Build distribution packages (sdist and wheel)"
	@echo "  clean        Remove build artifacts and caches"
	@echo "  formula      Generate Homebrew formula"
	@echo "  release      Build, tag, and push release (interactive)"
	@echo "  install-dev  Install package in development mode with dev dependencies"
	@echo "  test         Run test suite"
	@echo "  lint         Run code quality checks (black, ruff)"
	@echo "  help         Show this help message"

build:
	@echo "Building distribution packages..."
	python -m build

clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

formula:
	@echo "Generating Homebrew formula..."
	python scripts/generate_formula.py

release: build
	@echo "Creating release..."
	@echo ""
	@echo "Current version: $$(grep '^version = ' pyproject.toml | cut -d'"' -f2)"
	@echo ""
	@read -p "Enter version tag (e.g., v0.1.0): " TAG; \
	if [ -z "$$TAG" ]; then \
		echo "Error: Tag cannot be empty"; \
		exit 1; \
	fi; \
	echo "Creating and pushing tag $$TAG..."; \
	git tag -a $$TAG -m "Release $$TAG"; \
	git push origin $$TAG; \
	echo ""; \
	echo "✓ Tag $$TAG pushed. GitHub Actions will build and create the release."; \
	echo "  Check: https://github.com/$$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"

install-dev:
	@echo "Installing in development mode with dev dependencies..."
	pip install -e '.[dev]'

test:
	@echo "Running tests..."
	pytest tests/ -v

lint:
	@echo "Running code quality checks..."
	@echo "→ black"
	black --check beehive/
	@echo "→ ruff"
	ruff check beehive/
