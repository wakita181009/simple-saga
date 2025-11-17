from typing import Callable, Any
from dataclasses import dataclass


@dataclass
class StepResult:
    """Result of a saga step execution."""
    step_index: int
    step_name: str
    result: Any


@dataclass
class SagaStep:
    """Represents a single step in the saga with action and compensation."""
    action: Callable
    compensation: Callable
    action_args: tuple = ()
    action_kwargs: dict[str, Any] = None
    compensation_args: tuple = ()
    compensation_kwargs: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.action_kwargs is None:
            self.action_kwargs = {}
        if self.compensation_kwargs is None:
            self.compensation_kwargs = {}
