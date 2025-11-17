# Simple Saga - Development Guide

This document provides technical context and development guidelines for the Simple Saga library, optimized for AI assistants like Claude Code.

## Architecture Overview

### Core Components

1. **`Saga`** (`saga.py`) - Main orchestrator with Arrow-kt style DSL
   - Implements async context manager protocol (`__aenter__`, `__aexit__`)
   - Executes steps immediately with `step()` method
   - Handles both sync and async callables uniformly
   - Uses Python's `asyncio.iscoroutinefunction()` for runtime type detection
   - Automatic compensation on context exit if exception occurs

2. **`SagaStep`** (`schema.py`) - Step definition
   - Immutable dataclass with `field(default_factory=dict)` for mutable defaults
   - Stores action/compensation functions and their arguments
   - Supports `compensation_args` and `compensation_kwargs` for passing additional data

3. **`StepResult`** (`schema.py`) - Execution result
   - Records step index, name, and return value
   - Used for compensation tracking

### Design Patterns

- **Context Manager Pattern**: `async with Saga()` for automatic resource management
- **Command Pattern**: Steps encapsulate actions and compensations
- **Memento Pattern**: `_executed` list tracks state for rollback
- **Functional Composition**: Results flow between steps as variables

### Arrow-kt Inspiration

Inspired by [Arrow-kt's Saga implementation](https://arrow-kt.io/learn/resilience/saga/):
- DSL-style API for defining transactional workflows
- Automatic compensation on failure
- Result chaining between steps
- Type-safe execution

## Implementation Details

### Type System

```python
# Uses modern Python type hints
async def step(
    self,
    action: Callable[..., Any],
    compensation: Callable[..., Any],
    *,
    action_args: tuple[Any, ...] = (),
    action_kwargs: dict[str, Any] | None = None,
    compensation_args: tuple[Any, ...] = (),
    compensation_kwargs: dict[str, Any] | None = None,
) -> Any:
```

- Uses modern Python type hints (`|` instead of `Optional`, `list[]` instead of `List[]`)
- Strict mypy configuration in `pyproject.toml`
- All public methods have complete type annotations

### Context Manager Protocol

```python
async def __aenter__(self) -> "Saga":
    """Enter saga context, reset state."""
    self._context_error = None
    self._executed.clear()
    self._steps.clear()
    return self

async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: Any,
) -> bool:
    """Exit saga context, run compensation if exception occurred."""
    if exc_val is not None:
        await self._compensate()
    return False  # Propagate exception
```

**Key design decisions:**
- Always returns `False` to propagate exceptions
- Compensation runs automatically on any exception
- State is reset on context entry for reusability

### Immediate Step Execution

Unlike traditional saga implementations where steps are defined then executed, this uses immediate execution:

```python
async def step(self, action, compensation, ...) -> Any:
    """Execute step immediately and return result."""
    # Execute action
    if asyncio.iscoroutinefunction(action):
        result = await action(*action_args, **action_kwargs)
    else:
        result = action(*action_args, **action_kwargs)

    # Record for potential compensation
    self._steps.append(step)
    self._executed.append(step_result)

    return result  # Return to user for chaining
```

This enables natural result chaining:
```python
async with Saga() as saga:
    order = await saga.step(...)      # Returns order
    inventory = await saga.step(...)  # Can use 'order' variable
```

### Async/Sync Handling

The library handles mixed sync/async execution:

```python
if asyncio.iscoroutinefunction(step.action):
    result = await step.action(*step.action_args, **step.action_kwargs)
else:
    result = step.action(*step.action_args, **step.action_kwargs)
```

**Why `step()` is always async:**
- Uniform API regardless of step types
- Enables await for sync functions (no-op but consistent)
- Simplifies type signatures and error handling

### Compensation Logic

Compensations execute in reverse order (LIFO):

```python
async def _compensate(self) -> list[Exception]:
    """Run compensation for all executed steps in reverse order."""
    for step_result in reversed(self._executed):
        step = self._steps[step_result.step_index]

        # Pass action result + additional args
        comp_args = (step_result.result,) + step.compensation_args
        comp_kwargs = step.compensation_kwargs

        # Execute compensation...
```

**Compensation argument passing:**
1. **First argument**: Always the action's result
2. **Additional args**: From `compensation_args` tuple
3. **Keyword args**: From `compensation_kwargs` dict

Example:
```python
order = await saga.step(action=create_order, compensation=cancel_order)
inventory = await saga.step(
    action=lambda: reserve_inventory(order["order_id"]),
    compensation=release_inventory,
    compensation_args=(order,)  # Pass order to compensation
)
# On failure: release_inventory(inventory_result, order)
```

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
- Private attributes use underscore prefix (`_steps`, `_executed`)

## Testing Strategy

### Test Structure

```
tests/
├── test_saga.py           # Core saga functionality with Arrow-kt style
├── test_compensation.py   # Compensation behavior and argument passing
├── test_sync_async.py     # Mixed sync/async scenarios
└── conftest.py           # Shared fixtures
```

### Key Test Scenarios

1. **Happy path**: All steps succeed, no compensation
2. **Early failure**: First step fails (no compensation needed)
3. **Mid-failure**: Compensation for partial execution
4. **Compensation failure**: Continue compensating despite errors
5. **Mixed sync/async**: Various combinations
6. **Result chaining**: Using previous step results in next steps
7. **Compensation arguments**: Passing additional args to compensations
8. **Context manager reuse**: Multiple uses of same saga instance

### Test Example (Arrow-kt Style)

```python
@pytest.mark.asyncio
async def test_compensation_with_previous_results():
    """Test passing previous step results to compensation."""
    compensation_calls = []

    def create_order() -> dict:
        return {"order_id": "ORDER-123"}

    def reserve_inventory(order: dict) -> dict:
        return {"order_id": order["order_id"], "inventory_id": "INV-456"}

    def cancel_order(order: dict) -> None:
        compensation_calls.append(("cancel_order", order["order_id"]))

    def release_inventory(inventory: dict, order: dict) -> None:
        # Receives both inventory (action result) and order (via compensation_args)
        compensation_calls.append(
            ("release_inventory", inventory["inventory_id"], order["order_id"])
        )

    def failing_action() -> None:
        raise ValueError("Fail")

    with pytest.raises(ValueError):
        async with Saga() as saga:
            order = await saga.step(action=create_order, compensation=cancel_order)
            inventory = await saga.step(
                action=lambda: reserve_inventory(order),
                compensation=release_inventory,
                compensation_args=(order,)  # Pass order to compensation
            )
            await saga.step(action=failing_action, compensation=lambda r: None)

    # Compensation should receive both action result and previous step data
    assert compensation_calls == [
        ("release_inventory", "INV-456", "ORDER-123"),
        ("cancel_order", "ORDER-123"),
    ]
```

## Performance Considerations

### Memory

- `self._steps`: O(n) where n = number of steps
- `self._executed`: O(m) where m = executed steps (≤ n)
- Each `StepResult` stores the action's return value
- Results kept in memory until context manager exits

**Optimization tip**: For large result objects, consider storing references or IDs rather than full objects.

### CPU

- Sequential execution (not parallel)
- Minimal overhead: direct function calls with argument unpacking
- No heavy serialization or reflection
- Context manager protocol has negligible overhead

### I/O

- Network/database operations should be in user's action functions
- Library itself has no I/O (except logging to stderr)

## Extension Points

### Custom Context Manager Behavior

The context manager design allows for extensions:

```python
class RetryableSaga(Saga):
    """Saga with automatic retry on failure."""

    def __init__(self, max_retries: int = 3):
        super().__init__()
        self.max_retries = max_retries
        self._retry_count = 0

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Retry on failure before compensating."""
        if exc_val and self._retry_count < self.max_retries:
            self._retry_count += 1
            logger.info(f"Retry {self._retry_count}/{self.max_retries}")
            # Reset and retry...
        else:
            return await super().__aexit__(exc_type, exc_val, exc_tb)
```

### Step Hooks (Future)

Potential extension points:
```python
class ObservableSaga(Saga):
    async def step(self, action, compensation, **kwargs):
        # Pre-step hook
        self._emit_event("step_start", action.__name__)

        try:
            result = await super().step(action, compensation, **kwargs)
            # Post-step hook
            self._emit_event("step_success", result)
            return result
        except Exception as e:
            self._emit_event("step_failure", e)
            raise
```

### Middleware Pattern (Future)

```python
class MiddlewareSaga(Saga):
    def __init__(self, middlewares: list[Callable]):
        super().__init__()
        self.middlewares = middlewares

    async def step(self, action, compensation, **kwargs):
        # Wrap action with middlewares
        wrapped_action = self._apply_middlewares(action)
        return await super().step(wrapped_action, compensation, **kwargs)
```

## Common Pitfalls

### 1. Forgetting `await`

```python
# ❌ Wrong
async with Saga() as saga:
    result = saga.step(action=..., compensation=...)  # Missing await!

# ✅ Correct
async with Saga() as saga:
    result = await saga.step(action=..., compensation=...)
```

### 2. Using Variables Outside Context

```python
# ❌ Wrong - steps outside context
async with Saga() as saga:
    order = await saga.step(...)

# saga has exited, but trying to use it again
inventory = await saga.step(...)  # Wrong! Context exited

# ✅ Correct - keep all steps in context
async with Saga() as saga:
    order = await saga.step(...)
    inventory = await saga.step(...)  # Both in same context
```

### 3. Mutable Default Arguments

Already handled with `field(default_factory=dict)` in `SagaStep`.

### 4. Compensation Side Effects

Compensations should be idempotent when possible:

```python
def cancel_order(order_result):
    # Check if already cancelled
    if order_result.get("status") != "cancelled":
        # Perform cancellation
        ...
```

### 5. Exception Swallowing

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

### 6. Compensation Argument Confusion

Remember the order of compensation arguments:

```python
# Compensation signature:
def my_compensation(action_result, *compensation_args, **compensation_kwargs):
    pass

# Called as:
await saga.step(
    action=my_action,
    compensation=my_compensation,
    compensation_args=(arg1, arg2),  # Come AFTER action_result
    compensation_kwargs={"key": "value"}
)
```

## Dependencies

### Production

- **None** - Uses only Python standard library

### Development

- `mypy ^1.5.0` - Static type checking
- `ruff ^0.1.0` - Fast Python linter
- `pytest ^7.0.0` - Testing framework
- `pytest-asyncio ^0.21.0` - Async test support

### Python Version

- **Minimum**: Python 3.10
- **Tested**: 3.10, 3.11, 3.12, 3.13
- **Reasoning**: Modern type hints (`X | Y`, `list[X]`), context manager protocol

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
## [1.0.0] - 2025-XX-XX

### Added
- Arrow-kt style DSL with async context manager
- Result chaining between steps
- compensation_args and compensation_kwargs support

### Changed
- **BREAKING**: Removed Builder pattern (add_step + execute)
- **BREAKING**: Replaced with Arrow-kt style (async with + step)

### Fixed
- Compensation now correctly receives action result as first argument
```

## Future Enhancements

### Potential Features

1. **Nested Sagas**
   ```python
   async with Saga() as saga:
       order = await saga.step(...)

       # Nested saga for complex operation
       async with Saga() as nested_saga:
           payment = await nested_saga.step(...)
           shipment = await nested_saga.step(...)
   ```

2. **Conditional Steps**
   ```python
   async with Saga() as saga:
       order = await saga.step(...)

       if order["requires_shipping"]:
           shipment = await saga.step(...)
   ```

3. **Parallel Steps (Challenging)**
   ```python
   async with Saga() as saga:
       # Execute multiple steps concurrently
       results = await saga.parallel_steps([
           (action1, compensation1),
           (action2, compensation2),
       ])
   ```

4. **Saga State Persistence**
   - Serialize saga state to disk/database
   - Resume after crash
   - Requires careful design with lambdas

5. **Distributed Saga**
   - Cross-service coordination
   - Event-based saga orchestration
   - Would require significant architectural changes

## Questions for Contributors

When adding features, consider:

1. **Does it maintain simplicity?** - This is a "simple" saga library
2. **Does it fit Arrow-kt style?** - Keep the DSL intuitive
3. **Is it zero-dependency?** - Avoid adding dependencies
4. **Is it type-safe?** - Full type hints required
5. **Is it well-tested?** - Comprehensive tests needed
6. **Is it documented?** - Update README and docstrings

## Resources

### Saga Pattern

- [Original Paper: Sagas (1987)](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf)
- [Microservices.io: Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [Martin Fowler: Sagas](https://martinfowler.com/articles/patterns-of-distributed-systems/saga.html)
- [Arrow-kt Saga](https://arrow-kt.io/learn/resilience/saga/)

### Python Best Practices

- [PEP 8: Style Guide](https://peps.python.org/pep-0008/)
- [PEP 343: The "with" Statement](https://peps.python.org/pep-0343/)
- [PEP 484: Type Hints](https://peps.python.org/pep-0484/)
- [PEP 561: Distributing Type Information](https://peps.python.org/pep-0561/)

### Related Projects

- [saga-python](https://github.com/livetheoogway/saga-python) - Alternative implementation
- [temporal.io](https://temporal.io/) - Workflow orchestration platform
- [apache/camel](https://camel.apache.org/) - Enterprise integration patterns
- [Arrow-kt](https://arrow-kt.io/) - Functional programming for Kotlin

## Contact

For questions or suggestions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/simple-saga/issues)
- Email: wakita181009@gmail.com

---

*This document is maintained for AI assistants and human developers to understand the codebase architecture and development practices.*
