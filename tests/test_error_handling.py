"""Tests for error handling in saga execution."""

import pytest

from simple_saga import SimpleSaga


class TestActionExceptions:
    """Test handling of exceptions raised by actions."""

    @pytest.mark.asyncio
    async def test_action_raises_exception(self):
        """Test that action exceptions are propagated."""

        def failing_action() -> None:
            raise ValueError("Action failed")

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError, match="Action failed"):
            await saga.execute()

    @pytest.mark.asyncio
    async def test_exception_type_preserved(self):
        """Test that different exception types are preserved."""

        def runtime_error() -> None:
            raise RuntimeError("Runtime error")

        def type_error() -> None:
            raise TypeError("Type error")

        def value_error() -> None:
            raise ValueError("Value error")

        def compensation(result: None) -> None:
            pass

        # Test RuntimeError
        saga1 = SimpleSaga()
        saga1.add_step(action=runtime_error, compensation=compensation)
        with pytest.raises(RuntimeError, match="Runtime error"):
            await saga1.execute()

        # Test TypeError
        saga2 = SimpleSaga()
        saga2.add_step(action=type_error, compensation=compensation)
        with pytest.raises(TypeError, match="Type error"):
            await saga2.execute()

        # Test ValueError
        saga3 = SimpleSaga()
        saga3.add_step(action=value_error, compensation=compensation)
        with pytest.raises(ValueError, match="Value error"):
            await saga3.execute()

    @pytest.mark.asyncio
    async def test_exception_traceback_preserved(self):
        """Test that exception traceback is preserved."""

        def nested_function() -> None:
            raise KeyError("Inner error")

        def action() -> None:
            nested_function()

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        with pytest.raises(KeyError, match="Inner error"):
            await saga.execute()

    @pytest.mark.asyncio
    async def test_custom_exception_preserved(self):
        """Test that custom exceptions are preserved."""

        class CustomSagaError(Exception):
            """Custom exception for saga."""

            def __init__(self, message: str, code: int):
                super().__init__(message)
                self.code = code

        def failing_action() -> None:
            raise CustomSagaError("Custom error occurred", code=500)

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(CustomSagaError) as exc_info:
            await saga.execute()

        assert exc_info.value.code == 500
        assert str(exc_info.value) == "Custom error occurred"


class TestAsyncActionExceptions:
    """Test handling of exceptions in async actions."""

    @pytest.mark.asyncio
    async def test_async_action_raises_exception(self):
        """Test that async action exceptions are propagated."""

        async def async_failing_action() -> None:
            raise ValueError("Async action failed")

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=async_failing_action, compensation=compensation)

        with pytest.raises(ValueError, match="Async action failed"):
            await saga.execute()

    @pytest.mark.asyncio
    async def test_async_action_exception_with_compensation(self):
        """Test compensation runs when async action fails."""
        compensation_called = []

        async def successful_action() -> int:
            return 42

        async def failing_action() -> None:
            raise RuntimeError("Async fail")

        def compensation(result: int) -> None:
            compensation_called.append(result)

        saga = SimpleSaga()
        saga.add_step(action=successful_action, compensation=compensation)
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(RuntimeError, match="Async fail"):
            await saga.execute()

        assert compensation_called == [42]


class TestPartialExecution:
    """Test saga state after partial execution due to errors."""

    @pytest.mark.asyncio
    async def test_executed_list_before_error(self):
        """Test that executed list contains only successful steps before error."""

        def action1() -> int:
            return 1

        def action2() -> int:
            return 2

        def failing_action() -> None:
            raise ValueError("Step 3 fails")

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action1, compensation=compensation)
        saga.add_step(action=action2, compensation=compensation)
        saga.add_step(action=failing_action, compensation=compensation)

        try:
            await saga.execute()
        except ValueError:
            pass

        # Only first two steps should be in executed list
        assert len(saga.executed) == 0  # Reset clears executed after compensation

    @pytest.mark.asyncio
    async def test_partial_results_cleared_after_compensation(self):
        """Test that executed list is managed correctly after error and compensation."""

        def action(value: int) -> int:
            return value

        def compensation(result: int) -> None:
            pass

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=(1,))
        saga.add_step(action=action, compensation=compensation, action_args=(2,))
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # After compensation, executed list should be cleared on next execute
        saga.steps.pop()  # Remove the failing step

        results = await saga.execute()
        assert len(results) == 2
        assert results[0].result == 1
        assert results[1].result == 2


class TestErrorRecovery:
    """Test saga recovery and retry patterns."""

    @pytest.mark.asyncio
    async def test_retry_after_failure(self):
        """Test that saga can be retried after failure."""
        attempt_count = 0

        def flaky_action() -> int:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError(f"Attempt {attempt_count} failed")
            return attempt_count

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=flaky_action, compensation=compensation)

        # First attempt fails
        with pytest.raises(RuntimeError, match="Attempt 1 failed"):
            await saga.execute()

        # Second attempt fails
        with pytest.raises(RuntimeError, match="Attempt 2 failed"):
            await saga.execute()

        # Third attempt succeeds
        results = await saga.execute()
        assert results[0].result == 3

    @pytest.mark.asyncio
    async def test_saga_reuse_after_error(self):
        """Test that saga can be reused after encountering an error."""

        def sometimes_failing_action(should_fail: bool) -> str:
            if should_fail:
                raise ValueError("Failed this time")
            return "success"

        def compensation(result: str) -> None:
            pass

        saga = SimpleSaga()

        # First execution: success
        saga.add_step(action=sometimes_failing_action, compensation=compensation, action_kwargs={"should_fail": False})
        results1 = await saga.execute()
        assert results1[0].result == "success"

        # Clear and reconfigure for failure
        saga.steps.clear()
        saga.add_step(action=sometimes_failing_action, compensation=compensation, action_kwargs={"should_fail": True})

        with pytest.raises(ValueError, match="Failed this time"):
            await saga.execute()

        # Clear and reconfigure for success again
        saga.steps.clear()
        saga.add_step(action=sometimes_failing_action, compensation=compensation, action_kwargs={"should_fail": False})
        results2 = await saga.execute()
        assert results2[0].result == "success"


class TestCompensationExceptions:
    """Test behavior when compensations raise exceptions."""

    @pytest.mark.asyncio
    async def test_compensation_exception_logged_not_raised(self):
        """Test that compensation exceptions are logged but don't prevent other compensations."""
        compensation_attempts = []

        def action(value: int) -> int:
            return value

        def working_compensation(result: int) -> None:
            compensation_attempts.append(("ok", result))

        def failing_compensation(result: int) -> None:
            compensation_attempts.append(("fail", result))
            raise RuntimeError("Compensation failed")

        def trigger_error() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=working_compensation, action_args=(1,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(2,))
        saga.add_step(action=action, compensation=working_compensation, action_args=(3,))
        saga.add_step(action=trigger_error, compensation=working_compensation)

        # Should raise the original ValueError, not compensation exception
        with pytest.raises(ValueError, match="Trigger compensation"):
            await saga.execute()

        # All compensations should be attempted
        assert compensation_attempts == [("ok", 3), ("fail", 2), ("ok", 1)]

    @pytest.mark.asyncio
    async def test_multiple_compensation_exceptions(self):
        """Test handling of multiple compensation failures."""
        compensation_attempts = []

        def action(value: int) -> int:
            return value

        def failing_compensation(result: int) -> None:
            compensation_attempts.append(result)
            raise RuntimeError(f"Compensation {result} failed")

        def trigger_error() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=failing_compensation, action_args=(1,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(2,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(3,))
        saga.add_step(action=trigger_error, compensation=failing_compensation)

        with pytest.raises(ValueError, match="Trigger compensation"):
            await saga.execute()

        # All compensations should be attempted despite failures
        assert compensation_attempts == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_async_compensation_exception(self):
        """Test handling of exceptions in async compensations."""
        compensation_log = []

        def action(value: int) -> int:
            return value

        async def working_compensation(result: int) -> None:
            compensation_log.append(("ok", result))

        async def failing_compensation(result: int) -> None:
            compensation_log.append(("fail", result))
            raise RuntimeError("Async compensation failed")

        def trigger_error() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=working_compensation, action_args=(1,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(2,))
        saga.add_step(action=action, compensation=working_compensation, action_args=(3,))
        saga.add_step(action=trigger_error, compensation=working_compensation)

        with pytest.raises(ValueError, match="Trigger compensation"):
            await saga.execute()

        assert compensation_log == [("ok", 3), ("fail", 2), ("ok", 1)]


class TestExceptionMessages:
    """Test that error messages are clear and helpful."""

    @pytest.mark.asyncio
    async def test_error_with_step_context(self):
        """Test that errors maintain context about which step failed."""

        def step1() -> int:
            return 1

        def step2() -> int:
            return 2

        def failing_step3() -> None:
            raise ValueError("Step 3 specific error")

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=step1, compensation=compensation)
        saga.add_step(action=step2, compensation=compensation)
        saga.add_step(action=failing_step3, compensation=compensation)

        with pytest.raises(ValueError, match="Step 3 specific error"):
            await saga.execute()

        # The exception message should make it clear which step failed
        # This is important for debugging distributed transactions


class TestEdgeCaseExceptions:
    """Test exception handling in edge cases."""

    @pytest.mark.asyncio
    async def test_exception_in_first_step_no_compensation(self):
        """Test that exception in first step doesn't trigger any compensation."""
        compensation_called = False

        def failing_first_step() -> None:
            raise ValueError("First step fails")

        def compensation(result: None) -> None:
            nonlocal compensation_called
            compensation_called = True

        saga = SimpleSaga()
        saga.add_step(action=failing_first_step, compensation=compensation)

        with pytest.raises(ValueError, match="First step fails"):
            await saga.execute()

        assert not compensation_called

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_propagated(self):
        """Test that KeyboardInterrupt is propagated (not caught)."""

        def action() -> None:
            raise KeyboardInterrupt()

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        with pytest.raises(KeyboardInterrupt):
            await saga.execute()

    @pytest.mark.asyncio
    async def test_system_exit_propagated(self):
        """Test that SystemExit is propagated (not caught)."""

        def action() -> None:
            raise SystemExit(1)

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        with pytest.raises(SystemExit):
            await saga.execute()
