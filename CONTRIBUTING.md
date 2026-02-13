# Contributing to Beehive

Thank you for your interest in contributing to Beehive!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/beehive.git
   cd beehive
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Install system dependencies:
   ```bash
   # macOS
   brew install tmux gh

   # Ubuntu/Debian
   sudo apt-get install tmux gh
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=beehive --cov-report=html

# Run specific test file
pytest tests/test_session.py

# Run with verbose output
pytest -v
```

## Code Style

We use `black` for code formatting and `ruff` for linting.

```bash
# Format code
black beehive/ tests/

# Check formatting
black --check beehive/ tests/

# Lint
ruff check beehive/ tests/

# Fix auto-fixable issues
ruff check --fix beehive/ tests/
```

## Project Structure

```
beehive/
├── beehive/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # Click CLI interface
│   ├── core/
│   │   ├── session.py      # Session management
│   │   ├── storage.py      # Persistence layer
│   │   ├── tmux_manager.py # tmux operations
│   │   ├── git_ops.py      # Git operations
│   │   └── pr_creator.py   # PR creation
│   └── utils/
│       ├── logger.py       # Logging
│       └── config.py       # Configuration
└── tests/
    ├── test_session.py
    ├── test_storage.py
    └── test_git_ops.py
```

## Adding Features

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes

3. Add tests for new functionality

4. Run tests and ensure they pass:
   ```bash
   pytest
   black beehive/ tests/
   ruff check beehive/ tests/
   ```

5. Commit your changes:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

6. Push and create a pull request:
   ```bash
   git push origin feature/my-feature
   ```

## Coding Guidelines

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for public functions and classes
- Keep functions focused and small
- Add tests for new features
- Update documentation for user-facing changes

## Pull Request Process

1. Update the README.md if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md (if exists)
5. Request review from maintainers

## Bug Reports

When filing a bug report, please include:

- Beehive version (`beehive --version` when available)
- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Any error messages or logs

## Feature Requests

We welcome feature requests! Please:

- Check if the feature already exists
- Clearly describe the use case
- Explain why it would be useful
- Consider contributing an implementation

## Questions?

Feel free to open an issue for questions or discussions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
