"""Tests for saga compensation behavior with Arrow-kt style API."""

import pytest

from simple_saga import Saga


class TestCompensationTrigger:
    """Test when and how compensations are triggered."""

    @pytest.mark.asyncio
    async def test_no_compensation_on_success(self):
        """Test that compensations are not called when all steps succeed."""
        compensation_calls = []

        async def action() -> int:
            return 42

        async def compensation(result: int) -> None:
            compensation_calls.append(result)

        async with Saga() as saga:
            await saga.step(action=action, compensation=compensation)
            await saga.step(action=action, compensation=compensation)
            await saga.step(action=action, compensation=compensation)

        # No compensations should be called
        assert compensation_calls == []

    @pytest.mark.asyncio
    async def test_compensation_on_first_step_failure(self):
        """Test that no compensation runs if first step fails."""
        compensation_calls = []

        async def failing_action() -> None:
            raise RuntimeError("First step fails")

        async def compensation(result: int) -> None:
            compensation_calls.append(result)

        with pytest.raises(RuntimeError, match="First step fails"):
            async with Saga() as saga:
                await saga.step(action=failing_action, compensation=compensation)

        # No compensations since nothing succeeded before failure
        assert compensation_calls == []

    @pytest.mark.asyncio
    async def test_compensation_on_second_step_failure(self):
        """Test compensation runs for first step when second fails."""
        compensation_calls = []

        async def action1() -> int:
            return 1

        async def action2() -> None:
            raise RuntimeError("Second step fails")

        async def compensation(result: int) -> None:
            compensation_calls.append(result)

        with pytest.raises(RuntimeError, match="Second step fails"):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=compensation)
                await saga.step(action=action2, compensation=compensation)

        # Only first step should be compensated
        assert compensation_calls == [1]

    @pytest.mark.asyncio
    async def test_compensation_on_last_step_failure(self):
        """Test all compensations run when last step fails."""
        compensation_calls = []

        async def action(value: int) -> int:
            return value

        async def compensation(result: int) -> None:
            compensation_calls.append(result)

        async def failing_action() -> None:
            raise RuntimeError("Last step fails")

        async def action1():
            return await action(1)

        async def action2():
            return await action(2)

        async def action3():
            return await action(3)

        with pytest.raises(RuntimeError, match="Last step fails"):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=compensation)
                await saga.step(action=action2, compensation=compensation)
                await saga.step(action=action3, compensation=compensation)
                await saga.step(action=failing_action, compensation=compensation)

        # All three successful steps should be compensated in reverse order
        assert compensation_calls == [3, 2, 1]


class TestCompensationOrder:
    """Test that compensations execute in correct (reverse) order."""

    @pytest.mark.asyncio
    async def test_compensation_reverse_order(self):
        """Test compensations execute in reverse order (LIFO)."""
        compensation_log = []

        async def action(name: str) -> str:
            return name

        async def compensation(result: str) -> None:
            compensation_log.append(result)

        async def failing_action() -> None:
            raise ValueError("Trigger compensation")

        async def action1():
            return await action("first")

        async def action2():
            return await action("second")

        async def action3():
            return await action("third")

        async def action4():
            return await action("fourth")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=compensation)
                await saga.step(action=action2, compensation=compensation)
                await saga.step(action=action3, compensation=compensation)
                await saga.step(action=action4, compensation=compensation)
                await saga.step(action=failing_action, compensation=compensation)

        # Should compensate in reverse order: fourth, third, second, first
        assert compensation_log == ["fourth", "third", "second", "first"]

    @pytest.mark.asyncio
    async def test_compensation_receives_action_results(self):
        """Test that compensations receive results from their actions."""
        compensation_results = []

        async def action(value: int) -> int:
            return value * 2

        async def compensation(result: int) -> None:
            compensation_results.append(result)

        async def failing_action() -> None:
            raise RuntimeError("Fail")

        async def action1():
            return await action(5)

        async def action2():
            return await action(7)

        async def action3():
            return await action(9)

        with pytest.raises(RuntimeError):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=compensation)  # Returns 10
                await saga.step(action=action2, compensation=compensation)  # Returns 14
                await saga.step(action=action3, compensation=compensation)  # Returns 18
                await saga.step(action=failing_action, compensation=compensation)

        # Each compensation should receive the result of its action
        assert compensation_results == [18, 14, 10]


class TestCompensationArguments:
    """Test various compensation argument patterns."""

    @pytest.mark.asyncio
    async def test_compensation_default_argument(self):
        """Test compensation receives action result by default."""
        received_values = []

        async def action() -> dict:
            return {"id": 123, "status": "created"}

        async def compensation(result: dict) -> None:
            received_values.append(result)

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(action=action, compensation=compensation)
                await saga.step(action=failing_action, compensation=compensation)

        assert received_values == [{"id": 123, "status": "created"}]

    @pytest.mark.asyncio
    async def test_compensation_with_additional_args(self):
        """Test compensation with additional arguments after action result."""
        received_values = []

        async def action() -> int:
            return 100

        async def compensation(result: int, additional: str) -> None:
            received_values.append((result, additional))

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_args=("extra_data",),  # Additional arg after result
                )
                await saga.step(action=failing_action, compensation=compensation)

        # Should receive both action result and additional arg
        assert received_values == [(100, "extra_data")]

    @pytest.mark.asyncio
    async def test_compensation_with_kwargs(self):
        """Test compensation with keyword arguments."""
        received_values = []

        async def action() -> int:
            return 999

        async def compensation(result: int, x: int = 0, y: int = 0) -> None:
            received_values.append((result, x, y))

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_kwargs={"x": 10, "y": 20},
                )
                await saga.step(action=failing_action, compensation=compensation)

        assert received_values == [(999, 10, 20)]

    @pytest.mark.asyncio
    async def test_compensation_mixed_args_kwargs(self):
        """Test compensation with both additional args and kwargs."""
        received_values = []

        async def action() -> str:
            return "action_result"

        async def compensation(result: str, extra: int, flag: bool = False) -> None:
            received_values.append((result, extra, flag))

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_args=(42,),
                    compensation_kwargs={"flag": True},
                )
                await saga.step(action=failing_action, compensation=compensation)

        assert received_values == [("action_result", 42, True)]

    @pytest.mark.asyncio
    async def test_compensation_with_previous_step_results(self):
        """Test passing previous step results to compensation."""
        compensation_calls = []

        async def create_order() -> dict:
            return {"order_id": "ORDER-123"}

        async def reserve_inventory(order: dict) -> dict:
            return {"order_id": order["order_id"], "inventory_id": "INV-456"}

        async def cancel_order(order: dict) -> None:
            compensation_calls.append(("cancel_order", order["order_id"]))

        async def release_inventory(inventory: dict, order: dict) -> None:
            # Receives both inventory (action result) and order (via compensation_args)
            compensation_calls.append(("release_inventory", inventory["inventory_id"], order["order_id"]))

        async def failing_action() -> None:
            raise ValueError("Fail")

        async def noop_compensation() -> None:
            pass

        with pytest.raises(ValueError):
            async with Saga() as saga:
                order = await saga.step(action=create_order, compensation=cancel_order)

                async def reserve_action():
                    return await reserve_inventory(order)

                await saga.step(
                    action=reserve_action,
                    compensation=release_inventory,
                    compensation_args=(order,),  # Pass order to compensation
                )
                await saga.step(action=failing_action, compensation=noop_compensation)

        # Compensation should receive both action result and previous step data
        assert compensation_calls == [
            ("release_inventory", "INV-456", "ORDER-123"),
            ("cancel_order", "ORDER-123"),
        ]


class TestCompensationFailures:
    """Test behavior when compensations themselves fail."""

    @pytest.mark.asyncio
    async def test_compensation_failure_continues_chain(self):
        """Test that compensation failure doesn't stop other compensations."""
        compensation_log = []

        async def action(value: int) -> int:
            return value

        async def working_compensation(result: int) -> None:
            compensation_log.append(f"compensated_{result}")

        async def failing_compensation(result: int) -> None:
            compensation_log.append(f"failed_{result}")
            raise RuntimeError(f"Compensation failed for {result}")

        async def trigger_failure() -> None:
            raise ValueError("Trigger compensation")

        async def action1():
            return await action(1)

        async def action2():
            return await action(2)

        async def action3():
            return await action(3)

        with pytest.raises(ValueError, match="Trigger compensation"):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=working_compensation)
                await saga.step(action=action2, compensation=failing_compensation)
                await saga.step(action=action3, compensation=working_compensation)
                await saga.step(action=trigger_failure, compensation=working_compensation)

        # All compensations should be attempted despite step 2's failure
        # Order: 3, 2 (fails), 1
        assert compensation_log == ["compensated_3", "failed_2", "compensated_1"]

    @pytest.mark.asyncio
    async def test_multiple_compensation_failures(self):
        """Test multiple compensation failures."""
        compensation_attempts = []

        async def action(value: int) -> int:
            return value

        async def failing_compensation(result: int) -> None:
            compensation_attempts.append(result)
            raise RuntimeError(f"Compensation {result} failed")

        async def trigger_failure() -> None:
            raise ValueError("Trigger compensation")

        async def action1():
            return await action(1)

        async def action2():
            return await action(2)

        async def action3():
            return await action(3)

        with pytest.raises(ValueError, match="Trigger compensation"):
            async with Saga() as saga:
                await saga.step(action=action1, compensation=failing_compensation)
                await saga.step(action=action2, compensation=failing_compensation)
                await saga.step(action=action3, compensation=failing_compensation)
                await saga.step(action=trigger_failure, compensation=failing_compensation)

        # All compensation attempts should occur despite failures
        assert compensation_attempts == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_compensation_failure_original_exception_preserved(self):
        """Test that original exception is raised even if compensation fails."""

        async def action() -> int:
            return 1

        async def failing_compensation(result: int) -> None:
            raise RuntimeError("Compensation failed")

        async def trigger_failure() -> None:
            raise ValueError("Original error")

        # Should raise the original ValueError, not the compensation RuntimeError
        with pytest.raises(ValueError, match="Original error"):
            async with Saga() as saga:
                await saga.step(action=action, compensation=failing_compensation)
                await saga.step(action=trigger_failure, compensation=failing_compensation)


class TestCompensationEdgeCases:
    """Test edge cases in compensation behavior."""

    @pytest.mark.asyncio
    async def test_compensation_with_none_result(self):
        """Test compensation when action returns None."""
        received_values = []

        async def action() -> None:
            pass

        async def compensation(result: None) -> None:
            received_values.append(result)

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(action=action, compensation=compensation)
                await saga.step(action=failing_action, compensation=compensation)

        assert received_values == [None]

    @pytest.mark.asyncio
    async def test_compensation_with_complex_result(self):
        """Test compensation with complex data structures."""
        received_values = []

        async def action() -> dict:
            return {"nested": {"data": [1, 2, 3]}, "status": "ok"}

        async def compensation(result: dict) -> None:
            received_values.append(result)

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(action=action, compensation=compensation)
                await saga.step(action=failing_action, compensation=compensation)

        assert received_values == [{"nested": {"data": [1, 2, 3]}, "status": "ok"}]

    @pytest.mark.asyncio
    async def test_idempotent_compensation(self):
        """Test that compensation can be designed to be idempotent."""
        state = {"counter": 0, "cancelled": False}

        async def action() -> dict:
            state["counter"] += 1
            return {"id": state["counter"]}

        async def idempotent_compensation(result: dict) -> None:
            # Check if already cancelled
            if not state["cancelled"]:
                state["cancelled"] = True
                state["counter"] -= 1

        async def failing_action() -> None:
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            async with Saga() as saga:
                await saga.step(action=action, compensation=idempotent_compensation)
                await saga.step(action=failing_action, compensation=idempotent_compensation)

        # Counter should be decremented once
        assert state["counter"] == 0
        assert state["cancelled"] is True
