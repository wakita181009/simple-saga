# Simple Saga

Arrow-kt inspired saga pattern library for Python. Zero production dependencies.

## Development Commands

- **Test**: `poetry run pytest`
- **Type check**: `poetry run mypy simple_saga`
- **Lint**: `poetry run ruff check simple_saga`
- **Build**: `poetry build`

## Code Style

- Python 3.10+ (use `X | Y` not `Optional`, `list[X]` not `List[X]`)
- Line length: 120 characters
- Google style docstrings
- Type hints on all public APIs
- Strict mypy (`strict = true`)
- Ruff rules: `["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]`

## Key Design Decisions

- **Async/Sync separation**: `Saga` (async) and `SyncSaga` (sync) are separate classes sharing `_SagaBase` via generics. Do not mix async and sync in one class.
- **Immediate execution**: Steps execute immediately inside context manager (not deferred).
- **Compensation order**: LIFO. First arg to compensation is always the action's result, followed by `compensation_args`/`compensation_kwargs`.
- **Exception propagation**: Context manager always returns `False` (never swallows exceptions).
- **Zero dependencies**: Production code uses only Python stdlib.
