# Simple Saga - Development Guide

This document provides technical context and development guidelines for the Simple Saga library, optimized for AI assistants like Claude Code.

## Architecture Overview

### Core Components

1. **`_SagaBase`** (`saga/base.py`) - Base class with common logic
   - Generic base class using `Generic[StepT]` for type safety
   - Implements shared state management (`_steps`, `_executed`, `_context_error`)
   - Provides `_reset_context()` and `_record_execution()` helper methods
   - Used by both `Saga` and `SyncSaga` to avoid code duplication

2. **`Saga`** (`saga/saga.py`) - Asynchronous saga orchestrator with Arrow-kt style DSL
   - Extends `_SagaBase[SagaStep]` for async operations
   - Implements async context manager protocol (`__aenter__`, `__aexit__`)
   - Executes async steps immediately with `step()` method
   - All actions and compensations must be async (`Awaitable`)
   - Automatic compensation on context exit if exception occurs

3. **`SyncSaga`** (`saga/sync_saga.py`) - Synchronous saga orchestrator
   - Extends `_SagaBase[SyncSagaStep]` for sync operations
   - Implements sync context manager protocol (`__enter__`, `__exit__`)
   - Executes sync steps immediately with `step()` method
   - All actions and compensations must be synchronous
   - Automatic compensation on context exit if exception occurs

4. **`SagaStep`** and **`SyncSagaStep`** (`schema.py`) - Step definitions
   - `SagaStep`: For async operations with `Callable[..., Awaitable[Any]]`
   - `SyncSagaStep`: For sync operations with `Callable[..., Any]`
   - Both are immutable dataclasses with `field(default_factory=dict)` for mutable defaults
   - Store action/compensation functions and their arguments
   - Support `compensation_args` and `compensation_kwargs` for passing additional data

5. **`StepResult`** (`schema.py`) - Execution result
   - Records step index, name, and return value
   - Used for compensation tracking
   - Shared by both async and sync implementations

### Design Patterns

- **Context Manager Pattern**: `async with Saga()` and `with SyncSaga()` for automatic resource management
- **Command Pattern**: Steps encapsulate actions and compensations
- **Memento Pattern**: `_executed` list tracks state for rollback
- **Functional Composition**: Results flow between steps as variables
- **Generic Programming**: `_SagaBase[StepT]` provides type-safe code reuse
- **Template Method Pattern**: Base class defines algorithm structure, subclasses implement specifics

### Arrow-kt Inspiration

Inspired by [Arrow-kt's Saga implementation](https://arrow-kt.io/learn/resilience/saga/):
- DSL-style API for defining transactional workflows
- Automatic compensation on failure
- Result chaining between steps
- Type-safe execution

## Implementation Details

### Type System

The library uses generics and modern Python type hints for type safety:

```python
# Generic base class
StepT = TypeVar("StepT", SyncSagaStep, SagaStep)

class _SagaBase(Generic[StepT]):
    def __init__(self) -> None:
        self._steps: list[StepT] = []
        self._executed: list[StepResult] = []

# Async Saga with strict async types
class Saga(_SagaBase[SagaStep]):
    async def step(
        self,
        action: Callable[..., Awaitable[StepResultT]],
        compensation: Callable[..., Awaitable[Any]],
        *,
        action_args: tuple[Any, ...] = (),
        action_kwargs: dict[str, Any] | None = None,
        compensation_args: tuple[Any, ...] = (),
        compensation_kwargs: dict[str, Any] | None = None,
    ) -> StepResultT:
        ...

# Sync Saga with sync types
class SyncSaga(_SagaBase[SyncSagaStep]):
    def step(
        self,
        action: Callable[..., StepResultT],
        compensation: Callable[..., Any],
        *,
        action_args: tuple[Any, ...] = (),
        action_kwargs: dict[str, Any] | None = None,
        compensation_args: tuple[Any, ...] = (),
        compensation_kwargs: dict[str, Any] | None = None,
    ) -> StepResultT:
        ...
```

**Key type system features:**
- Uses modern Python type hints (`|` instead of `Optional`, `list[]` instead of `List[]`)
- Generic base class `_SagaBase[StepT]` for code reuse with type safety
- `Saga` uses `Awaitable` types for async operations
- `SyncSaga` uses plain `Callable` types for sync operations
- TypeVar `StepResultT` preserves return types through the chain
- Strict mypy configuration in `pyproject.toml`
- All public methods have complete type annotations

### Context Manager Protocol

Both `Saga` (async) and `SyncSaga` (sync) implement the context manager protocol:

**Async version (`Saga`):**
```python
async def __aenter__(self) -> "Saga":
    """Enter saga context, reset state."""
    self._reset_context()  # Delegated to base class
    return self

async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: Any,
) -> Literal[False]:
    """Exit saga context, run compensation if exception occurred."""
    if exc_val is not None:
        self._context_error = exc_val
        await self._compensate()
    return False  # Propagate exception
```

**Sync version (`SyncSaga`):**
```python
def __enter__(self) -> "SyncSaga":
    """Enter saga context, reset state."""
    self._reset_context()  # Delegated to base class
    return self

def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: Any,
) -> Literal[False]:
    """Exit saga context, run compensation if exception occurred."""
    if exc_val is not None:
        self._context_error = exc_val
        self._compensate()
    return False  # Propagate exception
```

**Key design decisions:**
- Always returns `False` (`Literal[False]`) to propagate exceptions
- Compensation runs automatically on any exception
- State is reset on context entry via `_reset_context()` for reusability
- Both implementations delegate common logic to `_SagaBase`

### Immediate Step Execution

Unlike traditional saga implementations where steps are defined then executed, this uses immediate execution:

**Async version (`Saga.step()`):**
```python
async def step(self, action, compensation, ...) -> StepResultT:
    """Execute async step immediately and return result."""
    step_index = len(self._executed)
    action_name = getattr(action, "__name__", "anonymous")

    # Execute async action directly
    result = await action(*action_args, **(action_kwargs or {}))

    # Record step and execution for potential compensation
    self._record_step(action, compensation, ...)
    self._record_execution(step_index, action_name, result)

    return result  # Return to user for chaining
```

**Sync version (`SyncSaga.step()`):**
```python
def step(self, action, compensation, ...) -> StepResultT:
    """Execute sync step immediately and return result."""
    step_index = len(self._executed)
    action_name = getattr(action, "__name__", "anonymous")

    # Execute sync action directly
    result = action(*action_args, **(action_kwargs or {}))

    # Record step and execution for potential compensation
    self._record_step(action, compensation, ...)
    self._record_execution(step_index, action_name, result)

    return result  # Return to user for chaining
```

This enables natural result chaining:
```python
# Async saga
async with Saga() as saga:
    order = await saga.step(...)      # Returns order
    inventory = await saga.step(...)  # Can use 'order' variable

# Sync saga
with SyncSaga() as saga:
    order = saga.step(...)            # Returns order (no await)
    inventory = saga.step(...)        # Can use 'order' variable
```

### Async/Sync Separation

**Key architectural decision:** The library provides two separate classes instead of a single mixed-mode class:

**Why separate `Saga` and `SyncSaga`?**
- **Type safety**: Strict typing with `Awaitable` vs plain `Callable`
- **Clarity**: No runtime checks needed (like `asyncio.iscoroutinefunction()`)
- **Simplicity**: Each class has a single, clear responsibility
- **Performance**: No runtime overhead for type checking
- **Error prevention**: Compile-time detection of async/sync mismatches

**Current approach (v0.1.0+):**
```python
# Saga: All async
result = await action(...)  # Always awaits

# SyncSaga: All sync
result = action(...)  # Never awaits
```

**Usage guidelines:**
- Use `Saga` when your actions are async (I/O-bound, network calls, async database queries)
- Use `SyncSaga` when your actions are sync (CPU-bound, local operations)
- Do not mix async and sync in the same saga instance

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
├── __init__.py
├── conftest.py                    # Shared fixtures
└── saga/
    ├── __init__.py
    ├── test_saga.py              # Core async saga functionality
    ├── test_sync_saga.py         # Sync saga functionality
    └── test_compensation.py      # Compensation behavior and argument passing
```

### Key Test Scenarios

1. **Happy path**: All steps succeed, no compensation
2. **Early failure**: First step fails (no compensation needed)
3. **Mid-failure**: Compensation for partial execution
4. **Compensation failure**: Continue compensating despite errors
5. **Async saga tests** (`test_saga.py`): Async-specific scenarios
6. **Sync saga tests** (`test_sync_saga.py`): Sync-specific scenarios
7. **Result chaining**: Using previous step results in next steps
8. **Compensation arguments**: Passing additional args to compensations
9. **Context manager reuse**: Multiple uses of same saga instance

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
- **Tested**: 3.10, 3.11, 3.12, 3.13, 3.14
- **Reasoning**: Modern type hints (`X | Y`, `list[X]`), context manager protocol, Generic types

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
