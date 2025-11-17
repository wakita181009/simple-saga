"""Asynchronous implementation of the Saga pattern."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeVar

from simple_saga.schema import SagaStep

from .base import _SagaBase

logger = logging.getLogger(__name__)

StepResultT = TypeVar("StepResultT")


class Saga(_SagaBase[SagaStep]):
    """
    Asynchronous implementation of the Saga pattern for managing distributed transactions.

    The Saga pattern breaks down a distributed transaction into a series of local transactions,
    each with a compensating transaction that can undo the changes if a later step fails.

    This implementation uses Arrow-kt style DSL with async context manager and supports
    asynchronous actions/compensations.

    Example:
        async with Saga() as saga:
            order = await saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order)
            )
            inventory = await saga.step(
                action=lambda: reserve_inventory(order["order_id"]),
                compensation=lambda inv: release_inventory(inv)
            )
            payment = await saga.step(
                action=lambda: charge_payment(99.99),
                compensation=lambda pay: refund_payment(pay)
            )

    If any step fails, all previously executed steps are automatically compensated
    in reverse order.
    """

    async def __aenter__(self) -> "Saga":
        """
        Enter the saga context manager.

        Returns:
            self: Returns the saga instance for use in the context
        """
        self._reset_context()
        logger.debug("Entering async saga context")
        return self

    async def __aexit__(
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
            await self._compensate()

        return False  # Propagate the exception

    def _record_step(
        self,
        action: Callable[..., Awaitable[Any]],
        compensation: Callable[..., Awaitable[Any]],
        action_args: tuple[Any, ...],
        action_kwargs: dict[str, Any],
        compensation_args: tuple[Any, ...],
        compensation_kwargs: dict[str, Any],
    ) -> None:
        """
        Record an asynchronous step for potential compensation.

        Args:
            action: The action function
            compensation: The compensation function
            action_args: Positional arguments for action
            action_kwargs: Keyword arguments for action
            compensation_args: Additional positional arguments for compensation
            compensation_kwargs: Keyword arguments for compensation
        """
        step = SagaStep(
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs,
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs,
        )
        self._steps.append(step)

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
        """
        Execute a single step in the saga (Arrow-kt style).

        This method is designed to be used within an async context manager.
        Each step is executed immediately and its result is returned.
        If any step fails, all previously executed steps are automatically compensated.

        Args:
            action: The asynchronous function to execute for this step
            compensation: The asynchronous function to compensate if this or later steps fail
            action_args: Positional arguments to pass to the action
            action_kwargs: Keyword arguments to pass to the action
            compensation_args: Additional positional arguments to pass to compensation (after action result)
            compensation_kwargs: Keyword arguments to pass to the compensation

        Returns:
            The result of the action function

        Raises:
            Exception: Any exception raised by the action function

        Example:
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
        """
        step_index = len(self._executed)
        action_name = getattr(action, "__name__", "anonymous")

        logger.info(f"Executing step {step_index + 1}: {action_name}")

        # Execute the async action
        result = await action(*action_args, **(action_kwargs or {}))

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

    async def _compensate(self) -> list[Exception]:
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

                # Execute async compensation
                await step.compensation(*comp_args, **comp_kwargs)

                logger.info(f"✅ Compensated step {step_result.step_index + 1}: {step.compensation.__name__}")
            except Exception as e:
                errors.append(e)
                logger.exception(f"⚠️ Compensation failed for step {step_result.step_index + 1}")

        if errors:
            logger.warning(f"Compensation completed with {len(errors)} error(s)")
        return errors
