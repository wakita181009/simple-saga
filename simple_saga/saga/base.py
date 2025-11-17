"""Base class for saga implementations."""

import logging
from typing import Any, Generic, TypeVar

from simple_saga.schema import SagaStep, StepResult, SyncSagaStep

logger = logging.getLogger(__name__)

StepT = TypeVar("StepT", SyncSagaStep, SagaStep)


class _SagaBase(Generic[StepT]):
    """
    Base class for saga implementations with common logic.

    This class provides shared functionality for both synchronous and asynchronous saga implementations.
    """

    def __init__(self) -> None:
        """
        Initialize a new saga instance.
        """
        self._steps: list[StepT] = []
        self._executed: list[StepResult] = []
        self._context_error: BaseException | None = None

    def _reset_context(self) -> None:
        """
        Reset the saga context for reuse.
        """
        self._context_error = None
        self._executed.clear()
        self._steps.clear()
        logger.debug("Saga context reset")

    def _record_execution(self, step_index: int, action_name: str, result: Any) -> None:
        """
        Record a successful step execution.

        Args:
            step_index: The index of the executed step
            action_name: The name of the action function
            result: The result of the action
        """
        step_result = StepResult(
            step_index=step_index,
            step_name=action_name,
            result=result,
        )
        self._executed.append(step_result)
