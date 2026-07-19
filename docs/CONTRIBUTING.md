# Contributing

Contributions, issues, and feedback are welcome.

## Development setup

```bash
git clone https://github.com/JerushaGray/TagScope.git
cd TagScope
pip install -e ".[dev]"
playwright install chromium
```

## Project principles

- **Keep it simple.** One clear way to do each thing.
- **No external services for core detection.** All tag and technology patterns are built-in.
- **Optimize for clarity.** Code should be readable without extensive comments.
- **Version intentionally.** Each release should be a meaningful improvement.

## Running tests

```bash
pytest
```

## Code style

- Follow existing patterns in the codebase.
- Use type hints for function signatures.
- Keep dependencies minimal.

## Author

Maintained by Jerusha Gray.
