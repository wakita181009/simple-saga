import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .schema import SagaStep, StepResult

logger = logging.getLogger(__name__)


class SimpleSaga:
    """
    A simple implementation of the Saga pattern for managing distributed transactions.

    The Saga pattern breaks down a distributed transaction into a series of local transactions,
    each with a compensating transaction that can undo the changes if a later step fails.

    Example:
        saga = SimpleSaga()
        saga.add_step(
            action=create_order,
            compensation=cancel_order,
            action_args=(order_id,),
            action_kwargs={'user_id': 123}
        )
        saga.add_step(
            action=reserve_inventory,
            compensation=release_inventory
        )

        results = await saga.execute()
    """

    def __init__(self) -> None:
        """
        Initialize a new SimpleSaga instance.
        """
        self.steps: list[SagaStep] = []
        self.executed: list[StepResult] = []

    def add_step(
        self,
        action: Callable[..., Any],
        compensation: Callable[..., Any],
        *,
        action_args: tuple[Any, ...] = (),
        action_kwargs: dict[str, Any] | None = None,
        compensation_args: tuple[Any, ...] = (),
        compensation_kwargs: dict[str, Any] | None = None,
    ) -> "SimpleSaga":
        """
        Add a step to the saga.

        Args:
            action: The function to execute for this step (can be sync or async)
            compensation: The function to compensate if this or later steps fail (can be sync or async)
            action_args: Positional arguments to pass to the action
            action_kwargs: Keyword arguments to pass to the action
            compensation_args: Positional arguments to pass to the compensation
            compensation_kwargs: Keyword arguments to pass to the compensation

        Returns:
            self: Returns the saga instance for method chaining
        """
        step = SagaStep(
            action=action,
            compensation=compensation,
            action_args=action_args,
            action_kwargs=action_kwargs or {},
            compensation_args=compensation_args,
            compensation_kwargs=compensation_kwargs or {},
        )
        self.steps.append(step)
        return self

    def reset(self) -> None:
        """Reset the saga state, clearing all executed steps."""
        self.executed.clear()

    async def execute(self) -> list[StepResult]:
        """
        Execute all steps in the saga.

        If any step fails, automatically runs compensation for all previously
        executed steps in reverse order.

        Returns:
            list[StepResult]: List of results from each executed step

        Raises:
            Exception: Re-raises the exception that caused the saga to fail
        """
        self.reset()

        try:
            for idx, step in enumerate(self.steps):
                logger.info(f"Executing step {idx + 1}/{len(self.steps)}: {step.action.__name__}")

                # Execute the action (async or sync)
                if asyncio.iscoroutinefunction(step.action):
                    result = await step.action(*step.action_args, **step.action_kwargs)
                else:
                    result = step.action(*step.action_args, **step.action_kwargs)

                # Record the successful execution
                step_result = StepResult(
                    step_index=idx,
                    step_name=step.action.__name__,
                    result=result,
                )
                self.executed.append(step_result)

                logger.info(f"✅ Step {idx + 1} completed: {step.action.__name__}")

            return self.executed

        except Exception as e:
            logger.error(f"❌ Error at step {len(self.executed) + 1}: {e}")
            await self.__compensate()
            raise

    async def __compensate(self) -> list[Exception]:
        """
        Run compensation for all executed steps in reverse order.

        This is called automatically when a step fails during execution.
        Compensation failures are logged but do not stop the compensation chain.
        """
        logger.info("🔄 Starting compensation...")

        errors: list[Exception] = []
        for step_result in reversed(self.executed):
            step = self.steps[step_result.step_index]
            try:
                logger.info(f"Compensating step {step_result.step_index + 1}: {step.compensation.__name__}")

                # Use compensation_args/kwargs if provided, otherwise use the action result
                if step.compensation_args or step.compensation_kwargs:
                    comp_args = step.compensation_args
                    comp_kwargs = step.compensation_kwargs
                else:
                    # Default: pass the action result as the first argument
                    comp_args = (step_result.result,)
                    comp_kwargs = {}

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
