import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from .schema import SagaStep, StepResult

logger = logging.getLogger(__name__)

# Type variable for step result type
StepResultT = TypeVar("StepResultT")


class SimpleSaga:
    """
    A simple implementation of the Saga pattern for managing distributed transactions.

    The Saga pattern breaks down a distributed transaction into a series of local transactions,
    each with a compensating transaction that can undo the changes if a later step fails.

    This implementation uses Arrow-kt style DSL with async context manager:

    Example:
        async with SimpleSaga() as saga:
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

    def __init__(self) -> None:
        """
        Initialize a new SimpleSaga instance.
        """
        self._steps: list[SagaStep] = []
        self._executed: list[StepResult] = []
        self._context_error: BaseException | None = None

    async def __aenter__(self) -> "SimpleSaga":
        """
        Enter the saga context manager.

        Returns:
            self: Returns the saga instance for use in the context
        """
        self._context_error = None
        self._executed.clear()
        self._steps.clear()
        logger.debug("Entering saga context")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
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

    async def step(
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
        Execute a single step in the saga (Arrow-kt style).

        This method is designed to be used within an async context manager.
        Each step is executed immediately and its result is returned.
        If any step fails, all previously executed steps are automatically compensated.

        Args:
            action: The function to execute for this step (can be sync or async)
            compensation: The function to compensate if this or later steps fail (can be sync or async)
            action_args: Positional arguments to pass to the action
            action_kwargs: Keyword arguments to pass to the action
            compensation_args: Additional positional arguments to pass to compensation (after action result)
            compensation_kwargs: Keyword arguments to pass to the compensation

        Returns:
            The result of the action function

        Raises:
            RuntimeError: If called outside of a context manager
            Exception: Any exception raised by the action function

        Example:
            async with SimpleSaga() as saga:
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

        # Execute the action (async or sync)
        if asyncio.iscoroutinefunction(action):
            result = await action(*action_args, **(action_kwargs or {}))
        else:
            result = action(*action_args, **(action_kwargs or {}))

        # Record the step for potential compensation
        step = SagaStep(
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs or {},
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs or {},
        )
        self._steps.append(step)

        # Record the successful execution
        step_result = StepResult(
            step_index=step_index,
            step_name=action_name,
            result=result,
        )
        self._executed.append(step_result)

        logger.info(f"✅ Step {step_index + 1} completed: {action_name}")

        return cast(StepResultT, result)

    async def _compensate(self) -> list[Exception]:
        """
        Run compensation for all executed steps in reverse order.

        This is called automatically when a step fails during execution.
        Compensation failures are logged but do not stop the compensation chain.
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

                # Execute compensation (async or sync)
                if asyncio.iscoroutinefunction(step.compensation):
                    await step.compensation(*comp_args, **comp_kwargs)
                else:
                    step.compensation(*comp_args, **comp_kwargs)

                logger.info(f"✅ Compensated step {step_result.step_index + 1}: {step.compensation.__name__}")
            except Exception as e:
                errors.append(e)
                logger.exception(f"⚠️ Compensation failed for step {step_result.step_index + 1}")

        if errors:
            logger.warning(f"Compensation completed with {len(errors)} error(s)")
        return errors
