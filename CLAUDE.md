# Simple Saga - Development Guide

This document provides technical context and development guidelines for the Simple Saga library, optimized for AI assistants like Claude Code.

## Architecture Overview

### Core Components

1. **`SimpleSaga`** (`saga.py`) - Main orchestrator
   - Manages step execution and compensation
   - Handles both sync and async callables uniformly
   - Uses Python's `asyncio.iscoroutinefunction()` for runtime type detection

2. **`SagaStep`** (`schema.py`) - Step definition
   - Immutable dataclass with `field(default_factory=dict)` for mutable defaults
   - Stores action/compensation functions and their arguments

3. **`StepResult`** (`schema.py`) - Execution result
   - Records step index, name, and return value
   - Used for compensation tracking

### Design Patterns

- **Builder Pattern**: Fluent `add_step()` interface
- **Command Pattern**: Steps encapsulate actions and compensations
- **Template Method**: `execute()` defines the saga algorithm
- **Memento Pattern**: `executed` list tracks state for rollback

## Implementation Details

### Type System

```python
# Type alias for clarity
SagaCallable: TypeAlias = Callable[..., Any]
```

- Uses modern Python type hints (`|` instead of `Optional`, `list[]` instead of `List[]`)
- Strict mypy configuration in `pyproject.toml`
- All functions have complete type annotations

### Async/Sync Handling

The library handles mixed sync/async execution:

```python
if asyncio.iscoroutinefunction(step.action):
    result = await step.action(*step.action_args, **step.action_kwargs)
else:
    result = step.action(*step.action_args, **step.action_kwargs)
```

**Why `execute()` is always async:**
- Uniform API regardless of step types
- Avoids runtime complexity of dynamic async/sync detection
- Enables future async-first features

### Compensation Logic

Compensations execute in reverse order (LIFO):

```python
for step_result in reversed(self.executed):
    step = self.steps[step_result.step_index]
    # Execute compensation...
```

**Default behavior:**
- Compensation receives action result: `compensation(action_result)`
- Can be overridden with explicit `compensation_args`/`compensation_kwargs`

**Error handling:**
- Compensation failures are logged but don't interrupt the chain
- All errors collected in `errors: list[Exception]`
- Allows partial rollback rather than complete failure

### Logging Strategy

Uses standard library `logging` module:

```python
logger = logging.getLogger(__name__)
```

**No enable_logging flag** - users control via logging configuration:
```python
logging.getLogger("simple_saga").setLevel(logging.WARNING)
```

## Code Quality Standards

### Type Checking (mypy)

```toml
[tool.mypy]
python_version = "3.10"
strict = true
```

Run: `poetry run mypy simple_saga`

### Linting (ruff)

```toml
[tool.ruff]
line-length = 120
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
```

Run: `poetry run ruff check simple_saga`

### Code Style

- Line length: 120 characters
- Python 3.10+ features (modern syntax)
- Comprehensive docstrings (Google style)
- Type hints on all public APIs

## Testing Strategy

### Test Structure (Future)

```
tests/
├── test_saga.py           # Core saga functionality
├── test_sync_async.py     # Mixed sync/async scenarios
├── test_compensation.py   # Compensation behavior
├── test_error_handling.py # Error scenarios
└── test_edge_cases.py     # Edge cases and corner cases
```

### Key Test Scenarios

1. **Happy path**: All steps succeed
2. **Early failure**: First step fails (no compensation needed)
3. **Mid-failure**: Compensation for partial execution
4. **Compensation failure**: Continue compensating despite errors
5. **Mixed sync/async**: Various combinations
6. **Argument passing**: args, kwargs, and defaults
7. **Reusability**: Multiple executions of same saga

### Test Fixtures Example

```python
@pytest.fixture
def mock_steps():
    """Create mock steps for testing."""
    action = Mock(return_value="result")
    compensation = Mock()
    return action, compensation

@pytest.mark.asyncio
async def test_saga_success(mock_steps):
    action, compensation = mock_steps
    saga = SimpleSaga()
    saga.add_step(action=action, compensation=compensation)

    results = await saga.execute()

    assert len(results) == 1
    action.assert_called_once()
    compensation.assert_not_called()
```

## Performance Considerations

### Memory

- `self.steps`: O(n) where n = number of steps
- `self.executed`: O(m) where m = executed steps (≤ n)
- Each `StepResult` stores the action's return value

**Optimization tip**: For large result objects, consider storing references or IDs rather than full objects.

### CPU

- Sequential execution (not parallel)
- Minimal overhead: direct function calls with argument unpacking
- No heavy serialization or reflection

### I/O

- Network/database operations should be in user's action functions
- Library itself has no I/O (except logging to stderr)

## Extension Points

### Custom Saga Implementations

The design allows for subclassing:

```python
class RetryableSaga(SimpleSaga):
    async def execute(self, max_retries: int = 3):
        for attempt in range(max_retries):
            try:
                return await super().execute()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.info(f"Retry {attempt + 1}/{max_retries}")
```

### Middleware/Hooks (Future)

Potential extension points:
- Pre/post step hooks
- Compensation strategies (e.g., retry compensation)
- Metrics collection
- Distributed tracing integration

## Common Pitfalls

### 1. Forgetting `await`

```python
# ❌ Wrong
saga.execute()

# ✅ Correct
await saga.execute()
```

### 2. Mutable Default Arguments

Already handled with `field(default_factory=dict)` in `SagaStep`.

### 3. Compensation Side Effects

Compensations should be idempotent when possible:

```python
def cancel_order(order_result):
    # Check if already cancelled
    if order_result.get("status") != "cancelled":
        # Perform cancellation
        ...
```

### 4. Exception Swallowing

Don't catch exceptions in actions unless necessary - let saga handle them:

```python
# ❌ Bad
def my_action():
    try:
        risky_operation()
    except Exception:
        return None  # Saga thinks this succeeded!

# ✅ Good
def my_action():
    return risky_operation()  # Let exceptions propagate
```

## Dependencies

### Production

- **None** - Uses only Python standard library

### Development

- `mypy ^1.5.0` - Static type checking
- `ruff ^0.1.0` - Fast Python linter

### Python Version

- **Minimum**: Python 3.10
- **Tested**: 3.10, 3.11, 3.12, 3.13
- **Reasoning**: Modern type hints (`X | Y`, `list[X]`)

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` (when created)
3. Run tests: `poetry run pytest`
4. Type check: `poetry run mypy simple_saga`
5. Lint: `poetry run ruff check simple_saga`
6. Build: `poetry build`
7. Publish: `poetry publish`

## Changelog Guidelines

Follow [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [0.2.0] - 2024-XX-XX

### Added
- New feature X

### Changed
- Breaking change Y

### Fixed
- Bug Z
```

## Future Enhancements

### Potential Features

1. **Parallel Execution**
   ```python
   saga.add_parallel_steps([
       (action1, compensation1),
       (action2, compensation2),
   ])
   ```

2. **Conditional Steps**
   ```python
   saga.add_step(action, compensation, condition=lambda: check_condition())
   ```

3. **Timeout Support**
   ```python
   saga.add_step(action, compensation, timeout=30.0)
   ```

4. **Saga State Persistence**
   - Save/restore saga state
   - Resume after crash

5. **Distributed Saga**
   - Cross-service coordination
   - Event-based saga orchestration

## Questions for Contributors

When adding features, consider:

1. **Does it maintain simplicity?** - This is a "simple" saga library
2. **Is it zero-dependency?** - Avoid adding dependencies
3. **Is it type-safe?** - Full type hints required
4. **Is it well-tested?** - Comprehensive tests needed
5. **Is it documented?** - Update README and docstrings

## Resources

### Saga Pattern

- [Original Paper: Sagas (1987)](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf)
- [Microservices.io: Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [Martin Fowler: Sagas](https://martinfowler.com/articles/patterns-of-distributed-systems/saga.html)

### Python Best Practices

- [PEP 8: Style Guide](https://peps.python.org/pep-0008/)
- [PEP 484: Type Hints](https://peps.python.org/pep-0484/)
- [PEP 561: Distributing Type Information](https://peps.python.org/pep-0561/)

### Related Projects

- [saga-python](https://github.com/livetheoogway/saga-python) - Alternative implementation
- [temporal.io](https://temporal.io/) - Workflow orchestration platform
- [apache/camel](https://camel.apache.org/) - Enterprise integration patterns

## Contact

For questions or suggestions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/simple-saga/issues)
- Email: wakita181009@gmail.com

---

*This document is maintained for AI assistants and human developers to understand the codebase architecture and development practices.*
