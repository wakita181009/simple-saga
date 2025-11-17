"""Synchronous implementation of the Saga pattern."""

import logging
from collections.abc import Callable
from typing import Any, Literal, TypeVar

from simple_saga.schema import SyncSagaStep

from .base import _SagaBase

logger = logging.getLogger(__name__)

StepResultT = TypeVar("StepResultT")


class SyncSaga(_SagaBase[SyncSagaStep]):
    """
    Synchronous implementation of the Saga pattern.

    This class provides a synchronous context manager for managing distributed transactions
    with automatic compensation on failure.

    Example:
        with SyncSaga() as saga:
            order = saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order)
            )
            inventory = saga.step(
                action=lambda: reserve_inventory(order["order_id"]),
                compensation=lambda inv: release_inventory(inv)
            )

    If any step fails, all previously executed steps are automatically compensated
    in reverse order.
    """

    def __enter__(self) -> "SyncSaga":
        """
        Enter the saga context manager.

        Returns:
            self: Returns the saga instance for use in the context
        """
        self._reset_context()
        logger.debug("Entering sync saga context")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """
        Exit the saga context manager.

        If an exception occurred, automatically runs compensation for all executed steps.

        Args:
            exc_type: The exception type
            exc_val: The exception value
            exc_tb: The exception traceback

        Returns:
            False: Always returns False to propagate the exception
        """
        if exc_val is not None:
            logger.error(f"❌ Saga failed with error: {exc_val}")
            self._context_error = exc_val
            self._compensate()

        return False  # Propagate the exception

    def _record_step(
        self,
        action: Callable[..., Any],
        compensation: Callable[..., Any],
        action_args: tuple[Any, ...],
        action_kwargs: dict[str, Any],
        compensation_args: tuple[Any, ...],
        compensation_kwargs: dict[str, Any],
    ) -> None:
        """
        Record a synchronous step for potential compensation.

        Args:
            action: The action function
            compensation: The compensation function
            action_args: Positional arguments for action
            action_kwargs: Keyword arguments for action
            compensation_args: Additional positional arguments for compensation
            compensation_kwargs: Keyword arguments for compensation
        """
        step = SyncSagaStep(
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs,
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs,
        )
        self._steps.append(step)

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
        """
        Execute a single synchronous step in the saga.

        This method is designed to be used within a context manager.
        Each step is executed immediately and its result is returned.
        If any step fails, all previously executed steps are automatically compensated.

        Args:
            action: The synchronous function to execute for this step
            compensation: The synchronous function to compensate if this or later steps fail
            action_args: Positional arguments to pass to the action
            action_kwargs: Keyword arguments to pass to the action
            compensation_args: Additional positional arguments to pass to compensation (after action result)
            compensation_kwargs: Keyword arguments to pass to the compensation

        Returns:
            The result of the action function

        Raises:
            Exception: Any exception raised by the action function

        Example:
            with SyncSaga() as saga:
                order = saga.step(
                    action=lambda: create_order("ORDER-123"),
                    compensation=lambda order: cancel_order(order)
                )
        """
        step_index = len(self._executed)
        action_name = getattr(action, "__name__", "anonymous")

        logger.info(f"Executing step {step_index + 1}: {action_name}")

        # Execute the action (synchronous)
        result = action(*action_args, **(action_kwargs or {}))

        # Record the step for potential compensation
        self._record_step(
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs or {},
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs or {},
        )

        # Record the successful execution
        self._record_execution(step_index, action_name, result)

        logger.info(f"✅ Step {step_index + 1} completed: {action_name}")

        return result

    def _compensate(self) -> list[Exception]:
        """
        Run compensation for all executed steps in reverse order.

        This is called automatically when a step fails during execution.
        Compensation failures are logged but do not stop the compensation chain.

        Returns:
            List of exceptions that occurred during compensation
        """
        logger.info("🔄 Starting compensation...")

        errors: list[Exception] = []
        for step_result in reversed(self._executed):
            step = self._steps[step_result.step_index]
            try:
                logger.info(f"Compensating step {step_result.step_index + 1}: {step.compensation.__name__}")

                # Pass action result as first argument, followed by additional compensation_args
                comp_args = (step_result.result,) + step.compensation_args
                comp_kwargs = step.compensation_kwargs

                # Execute compensation (synchronous)
                step.compensation(*comp_args, **comp_kwargs)

                logger.info(f"✅ Compensated step {step_result.step_index + 1}: {step.compensation.__name__}")
            except Exception as e:
                errors.append(e)
                logger.exception(f"⚠️ Compensation failed for step {step_result.step_index + 1}")

        if errors:
            logger.warning(f"Compensation completed with {len(errors)} error(s)")
        return errors
