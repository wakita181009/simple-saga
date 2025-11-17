# Simple Saga

A lightweight implementation of the Saga pattern for managing distributed transactions in Python, inspired by [Arrow-kt](https://arrow-kt.io/)'s functional approach.

## Overview

The Saga pattern breaks down distributed transactions into a series of local transactions, each with a compensating transaction that can undo the changes if a later step fails. This library provides a simple, type-safe implementation with Arrow-kt style DSL.

## Features

- ✅ **Arrow-kt Style DSL** - Intuitive context manager API
- 🔄 **Automatic Compensation** - Failed transactions are automatically rolled back
- 🔗 **Result Chaining** - Use results from previous steps in subsequent steps
- ⚡ **Sync & Async Support** - Separate `Saga` (async) and `SyncSaga` (sync) implementations
- 🔒 **Type Safe** - Full type hints with mypy support
- 🪶 **Lightweight** - Zero dependencies (uses only Python standard library)
- 📚 **Well Documented** - Comprehensive docstrings and examples

## Installation

```bash
pip install simple-saga
```

Or with Poetry:

```bash
poetry add simple-saga
```

## Quick Start (Async)

```python
import asyncio
from simple_saga import Saga

# Define your async business logic
async def create_order(order_id: str) -> dict:
    print(f"Creating order: {order_id}")
    return {"order_id": order_id, "status": "created"}

async def cancel_order(order: dict) -> None:
    print(f"Cancelling order: {order['order_id']}")

async def reserve_inventory(product_id: str) -> dict:
    print(f"Reserving inventory for: {product_id}")
    return {"product_id": product_id, "reserved": True}

async def release_inventory(inventory: dict) -> None:
    print(f"Releasing inventory for: {inventory['product_id']}")

async def charge_payment(amount: float) -> dict:
    print(f"Charging payment: ${amount}")
    # Simulating a payment failure
    raise Exception("Payment failed")

async def refund_payment(payment: dict) -> None:
    print("Refunding payment")

# Execute the saga
async def main():
    try:
        async with Saga() as saga:
            # Step 1: Create order
            order = await saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order)
            )

            # Step 2: Reserve inventory (uses order from step 1)
            inventory = await saga.step(
                action=lambda: reserve_inventory("PRODUCT-456"),
                compensation=lambda inv: release_inventory(inv)
            )

            # Step 3: Charge payment (this will fail)
            payment = await saga.step(
                action=lambda: charge_payment(99.99),
                compensation=lambda pay: refund_payment(pay)
            )

            print("✅ All steps completed successfully!")
    except Exception as e:
        print(f"❌ Saga failed: {e}")
        print("✅ All completed steps have been compensated automatically")

if __name__ == "__main__":
    asyncio.run(main())
```

## Quick Start (Sync)

For synchronous operations, use `SyncSaga`:

```python
from simple_saga import SyncSaga

# Define your synchronous business logic
def create_order(order_id: str) -> dict:
    print(f"Creating order: {order_id}")
    return {"order_id": order_id, "status": "created"}

def cancel_order(order: dict) -> None:
    print(f"Cancelling order: {order['order_id']}")

def reserve_inventory(product_id: str) -> dict:
    print(f"Reserving inventory for: {product_id}")
    return {"product_id": product_id, "reserved": True}

def release_inventory(inventory: dict) -> None:
    print(f"Releasing inventory for: {inventory['product_id']}")

def charge_payment(amount: float) -> dict:
    print(f"Charging payment: ${amount}")
    # Simulating a payment failure
    raise Exception("Payment failed")

def refund_payment(payment: dict) -> None:
    print("Refunding payment")

# Execute the saga
def main():
    try:
        with SyncSaga() as saga:
            # Step 1: Create order
            order = saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order)
            )

            # Step 2: Reserve inventory (uses order from step 1)
            inventory = saga.step(
                action=lambda: reserve_inventory("PRODUCT-456"),
                compensation=lambda inv: release_inventory(inv)
            )

            # Step 3: Charge payment (this will fail)
            payment = saga.step(
                action=lambda: charge_payment(99.99),
                compensation=lambda pay: refund_payment(pay)
            )

            print("✅ All steps completed successfully!")
    except Exception as e:
        print(f"❌ Saga failed: {e}")
        print("✅ All completed steps have been compensated automatically")

if __name__ == "__main__":
    main()
```

### Output

```
Creating order: ORDER-123
✓ Step 1 completed: <lambda>
Reserving inventory for: PRODUCT-456
✓ Step 2 completed: <lambda>
Charging payment: $99.99
✗ Error at step 3: Payment failed
🔄 Starting compensation...
Releasing inventory for: PRODUCT-456
✓ Compensated step 2: <lambda>
Cancelling order: ORDER-123
✓ Compensated step 1: <lambda>
❌ Saga failed: Payment failed
✅ All completed steps have been compensated automatically
```

## Key Features

### 1. Result Chaining Between Steps

The most powerful feature is the ability to use results from previous steps:

```python
async with Saga() as saga:
    # Step 1: Create order
    order = await saga.step(
        action=lambda: create_order("ORDER-123"),
        compensation=lambda order: cancel_order(order)
    )

    # Step 2: Use order data from step 1
    inventory = await saga.step(
        action=lambda: reserve_inventory(order["order_id"]),  # Uses order
        compensation=lambda inv: release_inventory(inv)
    )

    # Step 3: Use both order and inventory
    shipment = await saga.step(
        action=lambda: create_shipment(order, inventory),  # Uses both
        compensation=lambda ship: cancel_shipment(ship)
    )
```

### 2. Automatic Compensation

Compensations receive the action result automatically:

```python
async with Saga() as saga:
    result = await saga.step(
        action=lambda: {"id": 123, "status": "created"},
        compensation=lambda result: delete_resource(result["id"])  # Gets action result
    )
```

### 3. Passing Additional Arguments to Compensation

You can pass previous step results to compensations:

```python
async with Saga() as saga:
    order = await saga.step(
        action=lambda: create_order("ORDER-123"),
        compensation=lambda order: cancel_order(order)
    )

    inventory = await saga.step(
        action=lambda: reserve_inventory(order["order_id"]),
        compensation=lambda inv, order_ref: release_inventory(inv, order_ref),
        compensation_args=(order,)  # Pass order to compensation
    )
```

The compensation receives:
1. First argument: The action's result (`inv`)
2. Following arguments: Values from `compensation_args` (`order_ref`)
3. Keyword arguments: Values from `compensation_kwargs`

### 4. Choosing Between Saga and SyncSaga

**Use `Saga` (async) when:**
- Working with async I/O operations (database, network, file I/O)
- Building async web applications (FastAPI, aiohttp)
- Need to handle multiple concurrent operations
- Using `asyncio` ecosystem

**Use `SyncSaga` (sync) when:**
- Working with synchronous libraries
- Building traditional web applications (Flask, Django)
- Simpler code without async/await complexity
- Performance is not I/O bound

### 5. Logging Control

The library uses Python's standard `logging` module:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Or disable saga logs
logging.getLogger("simple_saga").setLevel(logging.WARNING)
```

## API Reference

### `Saga` (Async)

Asynchronous implementation for async/await operations.

#### `async step(action, compensation, *, action_args=(), action_kwargs=None, compensation_args=(), compensation_kwargs=None)`

Execute a single asynchronous step in the saga. Must be called within an `async with Saga()` context manager.

**Parameters:**
- `action`: Async function to execute
- `compensation`: Async function to compensate if this or later steps fail
- `action_args`: Positional arguments for the action
- `action_kwargs`: Keyword arguments for the action
- `compensation_args`: Additional positional arguments for compensation (after action result)
- `compensation_kwargs`: Keyword arguments for the compensation

**Returns:** The result of the action function

**Raises:** Any exception raised by the action function (after running compensations)

**Example:**
```python
async with Saga() as saga:
    order = await saga.step(
        action=create_order,
        compensation=cancel_order
    )
```

### `SyncSaga` (Sync)

Synchronous implementation for traditional blocking operations.

#### `step(action, compensation, *, action_args=(), action_kwargs=None, compensation_args=(), compensation_kwargs=None)`

Execute a single synchronous step in the saga. Must be called within a `with SyncSaga()` context manager.

**Parameters:**
- `action`: Synchronous function to execute
- `compensation`: Synchronous function to compensate if this or later steps fail
- `action_args`: Positional arguments for the action
- `action_kwargs`: Keyword arguments for the action
- `compensation_args`: Additional positional arguments for compensation (after action result)
- `compensation_kwargs`: Keyword arguments for the compensation

**Returns:** The result of the action function

**Raises:** Any exception raised by the action function (after running compensations)

**Example:**
```python
with SyncSaga() as saga:
    order = saga.step(
        action=create_order,
        compensation=cancel_order
    )
```

### `StepResult`

Dataclass containing the result of a saga step execution.

**Attributes:**
- `step_index`: int - The index of the step
- `step_name`: str - The name of the action function
- `result`: Any - The result returned by the action

### `SagaStep` / `SyncSagaStep`

Dataclass representing a single step in the saga with action and compensation.

**Attributes:**
- `action`: Callable - The action function
- `compensation`: Callable - The compensation function
- `action_args`: tuple - Positional arguments for the action
- `action_kwargs`: dict - Keyword arguments for the action
- `compensation_args`: tuple - Additional positional arguments for the compensation
- `compensation_kwargs`: dict - Keyword arguments for the compensation

## Design Decisions

### Why Separate Saga and SyncSaga?

Version 0.0.6 introduced separate classes for async and sync operations:

1. **Type Safety**: Clearer type hints and better IDE support
2. **Performance**: Optimized implementations for each use case
3. **Clarity**: Explicit choice between async and sync patterns
4. **Maintenance**: Easier to maintain and extend independently

### Compensation Behavior

- Compensations run in **reverse order** (LIFO)
- Compensation failures are **logged but don't stop the chain**
- Each compensation receives the action's result as the first argument
- You can provide additional arguments via `compensation_args` and `compensation_kwargs`

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/simple-saga.git
cd simple-saga

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run type checking
poetry run mypy simple_saga

# Run linting
poetry run ruff check simple_saga
```

### Project Structure

```
simple-saga/
├── simple_saga/
│   ├── __init__.py           # Package exports
│   ├── schema.py             # Data classes (StepResult, SagaStep, SyncSagaStep)
│   └── saga/
│       ├── __init__.py       # Saga package exports
│       ├── base.py           # Base class with shared logic (_SagaBase)
│       ├── saga.py           # Saga (async implementation)
│       └── sync_saga.py      # SyncSaga (sync implementation)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── saga/
│       ├── __init__.py
│       ├── test_saga.py           # Core async saga functionality
│       ├── test_sync_saga.py      # Sync saga functionality
│       └── test_compensation.py   # Compensation behavior
├── pyproject.toml       # Project configuration
├── README.md            # This file
└── CLAUDE.md            # Development guide
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

This library implements the Saga pattern as described in:
- ["Sagas" by Hector Garcia-Molina and Kenneth Salem (1987)](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf)
- [Microservices Patterns by Chris Richardson](https://microservices.io/patterns/data/saga.html)
- Inspired by [Arrow-kt](https://arrow-kt.io/)'s [Saga implementation](https://arrow-kt.io/learn/resilience/saga/)
