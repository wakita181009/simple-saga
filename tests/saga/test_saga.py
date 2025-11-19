"""Tests for core Saga functionality with Arrow-kt style API."""

import pytest

from simple_saga import Saga


class TestSagaConstruction:
    """Test saga instance creation."""

    def test_create_empty_saga(self):
        """Test creating an empty saga."""
        saga = Saga()
        assert saga._steps == []
        assert saga._executed == []

    @pytest.mark.asyncio
    async def test_context_manager_entry(self):
        """Test entering saga context manager."""
        async with Saga() as saga:
            assert saga._steps == []
            assert saga._executed == []


class TestSagaExecution:
    """Test saga execution with successful steps."""

    @pytest.mark.asyncio
    async def test_execute_empty_saga(self):
        """Test executing an empty saga."""
        async with Saga() as saga:
            pass  # No steps

        assert saga._executed == []

    @pytest.mark.asyncio
    async def test_execute_single_step(self):
        """Test executing saga with single step."""

        async def action() -> int:
            return 42

        async def compensation(result: int) -> None:
            pass

        async with Saga() as saga:
            result = await saga.step(action=action, compensation=compensation)

            assert result == 42
            assert len(saga._executed) == 1
            assert saga._executed[0].result == 42

    @pytest.mark.asyncio
    async def test_execute_multiple_steps(self):
        """Test executing saga with multiple steps."""

        async def step1() -> str:
            return "step1"

        async def step2() -> str:
            return "step2"

        async def step3() -> str:
            return "step3"

        async def compensation(result: str) -> None:
            pass

        async with Saga() as saga:
            result1 = await saga.step(action=step1, compensation=compensation)
            result2 = await saga.step(action=step2, compensation=compensation)
            result3 = await saga.step(action=step3, compensation=compensation)

            assert result1 == "step1"
            assert result2 == "step2"
            assert result3 == "step3"
            assert len(saga._executed) == 3

    @pytest.mark.asyncio
    async def test_execute_with_action_args(self):
        """Test executing saga with action arguments."""

        async def action(x: int, y: int) -> int:
            return x * y

        async def compensation(result: int) -> None:
            pass

        async with Saga() as saga:
            result = await saga.step(action=action, compensation=compensation, action_args=(5, 7))

            assert result == 35

    @pytest.mark.asyncio
    async def test_execute_with_action_kwargs(self):
        """Test executing saga with action keyword arguments."""

        async def action(x: int = 0, y: int = 0) -> int:
            return x - y

        async def compensation(result: int) -> None:
            pass

        async with Saga() as saga:
            result = await saga.step(action=action, compensation=compensation, action_kwargs={"x": 10, "y": 3})

            assert result == 7

    @pytest.mark.asyncio
    async def test_step_results_metadata(self):
        """Test that step results contain correct metadata."""

        async def my_custom_action() -> int:
            return 42

        async def compensation(result: int) -> None:
            pass

        async with Saga() as saga:
            await saga.step(action=my_custom_action, compensation=compensation)

            assert saga._executed[0].step_index == 0
            assert saga._executed[0].step_name == "my_custom_action"
            assert saga._executed[0].result == 42


class TestArrowKtStyleChaining:
    """Test Arrow-kt style result chaining between steps."""

    @pytest.mark.asyncio
    async def test_use_previous_result_in_next_step(self):
        """Test using previous step's result in next step."""

        async def create_order(order_id: str) -> dict:
            return {"order_id": order_id, "status": "created"}

        async def reserve_inventory(order: dict) -> dict:
            return {"order_id": order["order_id"], "inventory_reserved": True}

        async def charge_payment(inventory: dict) -> dict:
            return {"order_id": inventory["order_id"], "payment_status": "charged"}

        async def cancel_order(order: dict) -> None:
            pass

        async def release_inventory(inv: dict) -> None:
            pass

        async def refund_payment(payment: dict) -> None:
            pass

        async with Saga() as saga:
            # Step 1: Create order
            async def action1():
                return await create_order("ORDER-123")

            async def compensation1(order):
                await cancel_order(order)

            order = await saga.step(action=action1, compensation=compensation1)

            # Step 2: Reserve inventory (uses order from step 1)
            async def action2():
                return await reserve_inventory(order)

            async def compensation2(inv):
                await release_inventory(inv)

            inventory = await saga.step(action=action2, compensation=compensation2)

            # Step 3: Charge payment (uses inventory from step 2)
            async def action3():
                return await charge_payment(inventory)

            async def compensation3(pay):
                await refund_payment(pay)

            payment = await saga.step(action=action3, compensation=compensation3)

            assert order["order_id"] == "ORDER-123"
            assert inventory["inventory_reserved"] is True
            assert payment["payment_status"] == "charged"
            assert len(saga._executed) == 3

    @pytest.mark.asyncio
    async def test_complex_data_flow(self):
        """Test complex data flow between steps."""

        async with Saga() as saga:
            # Step 1: Initialize data
            async def action1():
                return {"value": 10}

            async def compensation1():
                pass

            data = await saga.step(action=action1, compensation=compensation1)

            # Step 2: Transform data
            async def action2():
                return {"value": data["value"] * 2}

            async def compensation2(result):
                pass

            doubled = await saga.step(action=action2, compensation=compensation2)

            # Step 3: Accumulate
            async def action3():
                return {"total": data["value"] + doubled["value"]}

            async def compensation3(result):
                pass

            total = await saga.step(action=action3, compensation=compensation3)

            assert data["value"] == 10
            assert doubled["value"] == 20
            assert total["total"] == 30


class TestSagaReusability:
    """Test that sagas can be reused multiple times."""

    @pytest.mark.asyncio
    async def test_reuse_saga_multiple_times(self):
        """Test executing the same saga definition multiple times."""
        execution_count = 0

        async def action() -> int:
            nonlocal execution_count
            execution_count += 1
            return execution_count

        async def compensation() -> None:
            pass

        # First execution
        async with Saga() as saga:
            result1 = await saga.step(action=action, compensation=compensation)
            assert result1 == 1

        # Second execution
        async with Saga() as saga:
            result2 = await saga.step(action=action, compensation=compensation)
            assert result2 == 2

        # Third execution
        async with Saga() as saga:
            result3 = await saga.step(action=action, compensation=compensation)
            assert result3 == 3

    @pytest.mark.asyncio
    async def test_context_manager_resets_state(self):
        """Test that each context manager entry resets state."""
        saga_instance = Saga()

        async def action1():
            return 1

        async def action2():
            return 2

        async def compensation():
            pass

        # First use
        async with saga_instance as saga:
            await saga.step(action=action1, compensation=compensation)
            assert len(saga._executed) == 1

        # Second use should have clean state
        async with saga_instance as saga:
            assert len(saga._executed) == 0
            await saga.step(action=action2, compensation=compensation)
            assert len(saga._executed) == 1


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
