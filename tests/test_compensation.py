"""Tests for saga compensation behavior."""

import pytest

from simple_saga import SimpleSaga


class TestCompensationTrigger:
    """Test when and how compensations are triggered."""

    @pytest.mark.asyncio
    async def test_no_compensation_on_success(self):
        """Test that compensations are not called when all steps succeed."""
        compensation_calls = []

        def action() -> int:
            return 42

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)
        saga.add_step(action=action, compensation=compensation)
        saga.add_step(action=action, compensation=compensation)

        await saga.execute()

        # No compensations should be called
        assert compensation_calls == []

    @pytest.mark.asyncio
    async def test_compensation_on_first_step_failure(self):
        """Test that no compensation runs if first step fails."""
        compensation_calls = []

        def failing_action() -> None:
            raise RuntimeError("First step fails")

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        saga = SimpleSaga()
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(RuntimeError, match="First step fails"):
            await saga.execute()

        # No compensations since nothing succeeded before failure
        assert compensation_calls == []

    @pytest.mark.asyncio
    async def test_compensation_on_second_step_failure(self):
        """Test compensation runs for first step when second fails."""
        compensation_calls = []

        def action1() -> int:
            return 1

        def action2() -> None:
            raise RuntimeError("Second step fails")

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        saga = SimpleSaga()
        saga.add_step(action=action1, compensation=compensation)
        saga.add_step(action=action2, compensation=compensation)

        with pytest.raises(RuntimeError, match="Second step fails"):
            await saga.execute()

        # Only first step should be compensated
        assert compensation_calls == [1]

    @pytest.mark.asyncio
    async def test_compensation_on_last_step_failure(self):
        """Test all compensations run when last step fails."""
        compensation_calls = []

        def action(value: int) -> int:
            return value

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        def failing_action() -> None:
            raise RuntimeError("Last step fails")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=(1,))
        saga.add_step(action=action, compensation=compensation, action_args=(2,))
        saga.add_step(action=action, compensation=compensation, action_args=(3,))
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(RuntimeError, match="Last step fails"):
            await saga.execute()

        # All three successful steps should be compensated in reverse order
        assert compensation_calls == [3, 2, 1]


class TestCompensationOrder:
    """Test that compensations execute in correct (reverse) order."""

    @pytest.mark.asyncio
    async def test_compensation_reverse_order(self):
        """Test compensations execute in reverse order (LIFO)."""
        compensation_log = []

        def action(name: str) -> str:
            return name

        def compensation(result: str) -> None:
            compensation_log.append(result)

        def failing_action() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=("first",))
        saga.add_step(action=action, compensation=compensation, action_args=("second",))
        saga.add_step(action=action, compensation=compensation, action_args=("third",))
        saga.add_step(action=action, compensation=compensation, action_args=("fourth",))
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # Should compensate in reverse order: fourth, third, second, first
        assert compensation_log == ["fourth", "third", "second", "first"]

    @pytest.mark.asyncio
    async def test_compensation_receives_action_results(self):
        """Test that compensations receive results from their actions."""
        compensation_results = []

        def action(value: int) -> int:
            return value * 2

        def compensation(result: int) -> None:
            compensation_results.append(result)

        def failing_action() -> None:
            raise RuntimeError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=(5,))  # Returns 10
        saga.add_step(action=action, compensation=compensation, action_args=(7,))  # Returns 14
        saga.add_step(action=action, compensation=compensation, action_args=(9,))  # Returns 18
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(RuntimeError):
            await saga.execute()

        # Each compensation should receive the result of its action
        assert compensation_results == [18, 14, 10]


class TestCompensationArguments:
    """Test various compensation argument patterns."""

    @pytest.mark.asyncio
    async def test_compensation_default_argument(self):
        """Test compensation receives action result by default."""
        received_values = []

        def action() -> dict:
            return {"id": 123, "status": "created"}

        def compensation(result: dict) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert received_values == [{"id": 123, "status": "created"}]

    @pytest.mark.asyncio
    async def test_compensation_explicit_args(self):
        """Test compensation with explicitly provided arguments."""
        received_values = []

        def action() -> int:
            return 999  # This should be ignored

        def compensation(value: int) -> None:
            received_values.append(value)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        # Explicitly provide compensation args
        saga.add_step(action=action, compensation=compensation, compensation_args=(42,))
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # Should use explicit arg (42), not action result (999)
        assert received_values == [42]

    @pytest.mark.asyncio
    async def test_compensation_explicit_kwargs(self):
        """Test compensation with explicitly provided keyword arguments."""
        received_values = []

        def action() -> int:
            return 999  # This should be ignored

        def compensation(x: int = 0, y: int = 0) -> None:
            received_values.append(x + y)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, compensation_kwargs={"x": 10, "y": 20})
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert received_values == [30]

    @pytest.mark.asyncio
    async def test_compensation_mixed_args_kwargs(self):
        """Test compensation with both args and kwargs."""
        received_values = []

        def action() -> int:
            return 999  # Ignored

        def compensation(a: int, b: int, c: int = 0) -> None:
            received_values.append((a, b, c))

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, compensation_args=(1, 2), compensation_kwargs={"c": 3})
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert received_values == [(1, 2, 3)]

    @pytest.mark.asyncio
    async def test_compensation_priority_explicit_over_default(self):
        """Test explicit compensation args take priority over default behavior."""
        received_values = []

        def action1() -> str:
            return "action1_result"

        def action2() -> str:
            return "action2_result"

        def compensation(value: str) -> None:
            received_values.append(value)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        # First step: use default (action result)
        saga.add_step(action=action1, compensation=compensation)
        # Second step: use explicit arg
        saga.add_step(action=action2, compensation=compensation, compensation_args=("explicit_arg",))
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # Reverse order: action2 (explicit), action1 (default)
        assert received_values == ["explicit_arg", "action1_result"]


class TestCompensationFailures:
    """Test behavior when compensations themselves fail."""

    @pytest.mark.asyncio
    async def test_compensation_failure_continues_chain(self):
        """Test that compensation failure doesn't stop other compensations."""
        compensation_log = []

        def action(value: int) -> int:
            return value

        def working_compensation(result: int) -> None:
            compensation_log.append(f"compensated_{result}")

        def failing_compensation(result: int) -> None:
            compensation_log.append(f"failed_{result}")
            raise RuntimeError(f"Compensation failed for {result}")

        def trigger_failure() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=working_compensation, action_args=(1,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(2,))
        saga.add_step(action=action, compensation=working_compensation, action_args=(3,))
        saga.add_step(action=trigger_failure, compensation=working_compensation)

        with pytest.raises(ValueError, match="Trigger compensation"):
            await saga.execute()

        # All compensations should be attempted despite step 2's failure
        # Order: 3, 2 (fails), 1
        assert compensation_log == ["compensated_3", "failed_2", "compensated_1"]

    @pytest.mark.asyncio
    async def test_multiple_compensation_failures(self):
        """Test multiple compensation failures."""
        compensation_attempts = []

        def action(value: int) -> int:
            return value

        def failing_compensation(result: int) -> None:
            compensation_attempts.append(result)
            raise RuntimeError(f"Compensation {result} failed")

        def trigger_failure() -> None:
            raise ValueError("Trigger compensation")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=failing_compensation, action_args=(1,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(2,))
        saga.add_step(action=action, compensation=failing_compensation, action_args=(3,))
        saga.add_step(action=trigger_failure, compensation=failing_compensation)

        with pytest.raises(ValueError, match="Trigger compensation"):
            await saga.execute()

        # All compensation attempts should occur despite failures
        assert compensation_attempts == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_compensation_failure_original_exception_preserved(self):
        """Test that original exception is raised even if compensation fails."""

        def action() -> int:
            return 1

        def failing_compensation(result: int) -> None:
            raise RuntimeError("Compensation failed")

        def trigger_failure() -> None:
            raise ValueError("Original error")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=failing_compensation)
        saga.add_step(action=trigger_failure, compensation=failing_compensation)

        # Should raise the original ValueError, not the compensation RuntimeError
        with pytest.raises(ValueError, match="Original error"):
            await saga.execute()


class TestCompensationEdgeCases:
    """Test edge cases in compensation behavior."""

    @pytest.mark.asyncio
    async def test_compensation_with_none_result(self):
        """Test compensation when action returns None."""
        received_values = []

        def action() -> None:
            pass

        def compensation(result: None) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert received_values == [None]

    @pytest.mark.asyncio
    async def test_compensation_with_complex_result(self):
        """Test compensation with complex data structures."""
        received_values = []

        def action() -> dict:
            return {"nested": {"data": [1, 2, 3]}, "status": "ok"}

        def compensation(result: dict) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)
        saga.add_step(action=failing_action, compensation=compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert received_values == [{"nested": {"data": [1, 2, 3]}, "status": "ok"}]

    @pytest.mark.asyncio
    async def test_idempotent_compensation(self):
        """Test that compensation can be designed to be idempotent."""
        state = {"counter": 0, "cancelled": False}

        def action() -> dict:
            state["counter"] += 1
            return {"id": state["counter"]}

        def idempotent_compensation(result: dict) -> None:
            # Check if already cancelled
            if not state["cancelled"]:
                state["cancelled"] = True
                state["counter"] -= 1

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=idempotent_compensation)
        saga.add_step(action=failing_action, compensation=idempotent_compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # Counter should be decremented once
        assert state["counter"] == 0
        assert state["cancelled"] is True
