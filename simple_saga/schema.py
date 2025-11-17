from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepResult:
    """Result of a saga step execution."""

    step_index: int
    step_name: str
    result: Any


@dataclass(frozen=True)
class SyncSagaStep:
    """Represents a single synchronous step in the saga with action and compensation."""

    action: Callable[..., Any]
    compensation: Callable[..., Any]
    action_args: tuple[Any, ...] = ()
    action_kwargs: dict[str, Any] = field(default_factory=dict)
    compensation_args: tuple[Any, ...] = ()
    compensation_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SagaStep:
    """Represents a single asynchronous step in the saga with action and compensation."""

    action: Callable[..., Awaitable[Any]]
    compensation: Callable[..., Awaitable[Any]]
    action_args: tuple[Any, ...] = ()
    action_kwargs: dict[str, Any] = field(default_factory=dict)
    compensation_args: tuple[Any, ...] = ()
    compensation_kwargs: dict[str, Any] = field(default_factory=dict)
