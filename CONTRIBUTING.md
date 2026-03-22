# Contributing

Thanks for your interest in contributing to claude-notion-sync!

## Getting Started

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt -r requirements-dev.txt`
3. Run tests: `python3 -m pytest tests/ -v`

## Running Tests

```bash
python3 -m pytest tests/ -v
```

All 118 tests should pass before submitting a PR.

## Code Style

- Follow existing patterns in the codebase
- Keep modules focused -- one responsibility per file
- Add tests for new functionality (TDD preferred)
- Use type hints where they add clarity

## Pull Requests

1. Fork the repo
2. Create a feature branch
3. Make your changes with tests
4. Run the full test suite
5. Submit a PR with a clear description of what and why

## Reporting Issues

Open an issue with:
- What you expected
- What actually happened
- Steps to reproduce
- Your environment (OS, Python version, notion-client version)
