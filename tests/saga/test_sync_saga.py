"""Tests for core SyncSaga functionality with Arrow-kt style API."""

from simple_saga import SyncSaga


class TestSyncSagaConstruction:
    """Test sync saga instance creation."""

    def test_create_empty_saga(self):
        """Test creating an empty sync saga."""
        saga = SyncSaga()
        assert saga._steps == []
        assert saga._executed == []

    def test_context_manager_entry(self):
        """Test entering sync saga context manager."""
        with SyncSaga() as saga:
            assert saga._steps == []
            assert saga._executed == []


class TestSyncSagaExecution:
    """Test sync saga execution with successful steps."""

    def test_execute_empty_saga(self):
        """Test executing an empty sync saga."""
        with SyncSaga() as saga:
            pass  # No steps

        assert saga._executed == []

    def test_execute_single_step(self):
        """Test executing sync saga with single step."""

        def action() -> int:
            return 42

        def compensation(result: int) -> None:
            pass

        with SyncSaga() as saga:
            result = saga.step(action=action, compensation=compensation)

            assert result == 42
            assert len(saga._executed) == 1
            assert saga._executed[0].result == 42

    def test_execute_multiple_steps(self):
        """Test executing sync saga with multiple steps."""

        def step1() -> str:
            return "step1"

        def step2() -> str:
            return "step2"

        def step3() -> str:
            return "step3"

        def compensation(result: str) -> None:
            pass

        with SyncSaga() as saga:
            result1 = saga.step(action=step1, compensation=compensation)
            result2 = saga.step(action=step2, compensation=compensation)
            result3 = saga.step(action=step3, compensation=compensation)

            assert result1 == "step1"
            assert result2 == "step2"
            assert result3 == "step3"
            assert len(saga._executed) == 3

    def test_execute_with_action_args(self):
        """Test executing sync saga with action arguments."""

        def action(x: int, y: int) -> int:
            return x * y

        def compensation(result: int) -> None:
            pass

        with SyncSaga() as saga:
            result = saga.step(action=action, compensation=compensation, action_args=(5, 7))

            assert result == 35

    def test_execute_with_action_kwargs(self):
        """Test executing sync saga with action keyword arguments."""

        def action(x: int = 0, y: int = 0) -> int:
            return x - y

        def compensation(result: int) -> None:
            pass

        with SyncSaga() as saga:
            result = saga.step(action=action, compensation=compensation, action_kwargs={"x": 10, "y": 3})

            assert result == 7

    def test_step_results_metadata(self):
        """Test that step results contain correct metadata."""

        def my_custom_action() -> int:
            return 42

        def compensation(result: int) -> None:
            pass

        with SyncSaga() as saga:
            saga.step(action=my_custom_action, compensation=compensation)

            assert saga._executed[0].step_index == 0
            assert saga._executed[0].step_name == "my_custom_action"
            assert saga._executed[0].result == 42


class TestSyncArrowKtStyleChaining:
    """Test Arrow-kt style result chaining between steps."""

    def test_use_previous_result_in_next_step(self):
        """Test using previous step's result in next step."""

        def create_order(order_id: str) -> dict:
            return {"order_id": order_id, "status": "created"}

        def reserve_inventory(order: dict) -> dict:
            return {"order_id": order["order_id"], "inventory_reserved": True}

        def charge_payment(inventory: dict) -> dict:
            return {"order_id": inventory["order_id"], "payment_status": "charged"}

        def cancel_order(order: dict) -> None:
            pass

        def release_inventory(inv: dict) -> None:
            pass

        def refund_payment(payment: dict) -> None:
            pass

        with SyncSaga() as saga:
            # Step 1: Create order
            order = saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order),
            )

            # Step 2: Reserve inventory (uses order from step 1)
            inventory = saga.step(
                action=lambda: reserve_inventory(order),
                compensation=lambda inv: release_inventory(inv),
            )

            # Step 3: Charge payment (uses inventory from step 2)
            payment = saga.step(
                action=lambda: charge_payment(inventory),
                compensation=lambda pay: refund_payment(pay),
            )

            assert order["order_id"] == "ORDER-123"
            assert inventory["inventory_reserved"] is True
            assert payment["payment_status"] == "charged"
            assert len(saga._executed) == 3

    def test_complex_data_flow(self):
        """Test complex data flow between steps."""

        with SyncSaga() as saga:
            # Step 1: Initialize data
            data = saga.step(
                action=lambda: {"value": 10},
                compensation=lambda: None,
            )

            # Step 2: Transform data
            doubled = saga.step(
                action=lambda: {"value": data["value"] * 2},
                compensation=lambda: None,
            )

            # Step 3: Accumulate
            total = saga.step(
                action=lambda: {"total": data["value"] + doubled["value"]},
                compensation=lambda: None,
            )

            assert data["value"] == 10
            assert doubled["value"] == 20
            assert total["total"] == 30


class TestSyncSagaReusability:
    """Test that sync sagas can be reused multiple times."""

    def test_reuse_saga_multiple_times(self):
        """Test executing the same sync saga definition multiple times."""
        execution_count = 0

        def action() -> int:
            nonlocal execution_count
            execution_count += 1
            return execution_count

        def compensation(result: int) -> None:
            pass

        # First execution
        with SyncSaga() as saga:
            result1 = saga.step(action=action, compensation=compensation)
            assert result1 == 1

        # Second execution
        with SyncSaga() as saga:
            result2 = saga.step(action=action, compensation=compensation)
            assert result2 == 2

        # Third execution
        with SyncSaga() as saga:
            result3 = saga.step(action=action, compensation=compensation)
            assert result3 == 3

    def test_context_manager_resets_state(self):
        """Test that each context manager entry resets state."""
        saga_instance = SyncSaga()

        def action1():
            return 1

        def action2():
            return 2

        def compensation(result):
            pass

        # First use
        with saga_instance as saga:
            saga.step(action=action1, compensation=compensation)
            assert len(saga._executed) == 1

        # Second use should have clean state
        with saga_instance as saga:
            assert len(saga._executed) == 0
            saga.step(action=action2, compensation=compensation)
            assert len(saga._executed) == 1


class TestSyncCompensationTrigger:
    """Test when and how compensations are triggered."""

    def test_no_compensation_on_success(self):
        """Test that compensations are not called when all steps succeed."""
        compensation_calls = []

        def action() -> int:
            return 42

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        with SyncSaga() as saga:
            saga.step(action=action, compensation=compensation)
            saga.step(action=action, compensation=compensation)
            saga.step(action=action, compensation=compensation)

        # No compensations should be called
        assert compensation_calls == []

    def test_compensation_on_first_step_failure(self):
        """Test that no compensation runs if first step fails."""
        compensation_calls = []

        def failing_action() -> None:
            raise RuntimeError("First step fails")

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        try:
            with SyncSaga() as saga:
                saga.step(action=failing_action, compensation=compensation)
        except RuntimeError as e:
            assert str(e) == "First step fails"

        # No compensations since nothing succeeded before failure
        assert compensation_calls == []

    def test_compensation_on_second_step_failure(self):
        """Test compensation runs for first step when second fails."""
        compensation_calls = []

        def action1() -> int:
            return 1

        def action2() -> None:
            raise RuntimeError("Second step fails")

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        try:
            with SyncSaga() as saga:
                saga.step(action=action1, compensation=compensation)
                saga.step(action=action2, compensation=compensation)
        except RuntimeError as e:
            assert str(e) == "Second step fails"

        # Only first step should be compensated
        assert compensation_calls == [1]

    def test_compensation_on_last_step_failure(self):
        """Test all compensations run when last step fails."""
        compensation_calls = []

        def action(value: int) -> int:
            return value

        def compensation(result: int) -> None:
            compensation_calls.append(result)

        def failing_action() -> None:
            raise RuntimeError("Last step fails")

        try:
            with SyncSaga() as saga:
                saga.step(action=lambda: action(1), compensation=compensation)
                saga.step(action=lambda: action(2), compensation=compensation)
                saga.step(action=lambda: action(3), compensation=compensation)
                saga.step(action=failing_action, compensation=compensation)
        except RuntimeError as e:
            assert str(e) == "Last step fails"

        # All three successful steps should be compensated in reverse order
        assert compensation_calls == [3, 2, 1]


class TestSyncCompensationOrder:
    """Test that compensations execute in correct (reverse) order."""

    def test_compensation_reverse_order(self):
        """Test compensations execute in reverse order (LIFO)."""
        compensation_log = []

        def action(name: str) -> str:
            return name

        def compensation(result: str) -> None:
            compensation_log.append(result)

        def failing_action() -> None:
            raise ValueError("Trigger compensation")

        try:
            with SyncSaga() as saga:
                saga.step(action=lambda: action("first"), compensation=compensation)
                saga.step(action=lambda: action("second"), compensation=compensation)
                saga.step(action=lambda: action("third"), compensation=compensation)
                saga.step(action=lambda: action("fourth"), compensation=compensation)
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        # Should compensate in reverse order: fourth, third, second, first
        assert compensation_log == ["fourth", "third", "second", "first"]

    def test_compensation_receives_action_results(self):
        """Test that compensations receive results from their actions."""
        compensation_results = []

        def action(value: int) -> int:
            return value * 2

        def compensation(result: int) -> None:
            compensation_results.append(result)

        def failing_action() -> None:
            raise RuntimeError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(action=lambda: action(5), compensation=compensation)  # Returns 10
                saga.step(action=lambda: action(7), compensation=compensation)  # Returns 14
                saga.step(action=lambda: action(9), compensation=compensation)  # Returns 18
                saga.step(action=failing_action, compensation=compensation)
        except RuntimeError:
            pass

        # Each compensation should receive the result of its action
        assert compensation_results == [18, 14, 10]


class TestSyncCompensationArguments:
    """Test various compensation argument patterns."""

    def test_compensation_default_argument(self):
        """Test compensation receives action result by default."""
        received_values = []

        def action() -> dict:
            return {"id": 123, "status": "created"}

        def compensation(result: dict) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(action=action, compensation=compensation)
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        assert received_values == [{"id": 123, "status": "created"}]

    def test_compensation_with_additional_args(self):
        """Test compensation with additional arguments after action result."""
        received_values = []

        def action() -> int:
            return 100

        def compensation(result: int, additional: str) -> None:
            received_values.append((result, additional))

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_args=("extra_data",),  # Additional arg after result
                )
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        # Should receive both action result and additional arg
        assert received_values == [(100, "extra_data")]

    def test_compensation_with_kwargs(self):
        """Test compensation with keyword arguments."""
        received_values = []

        def action() -> int:
            return 999

        def compensation(result: int, x: int = 0, y: int = 0) -> None:
            received_values.append((result, x, y))

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_kwargs={"x": 10, "y": 20},
                )
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        assert received_values == [(999, 10, 20)]

    def test_compensation_mixed_args_kwargs(self):
        """Test compensation with both additional args and kwargs."""
        received_values = []

        def action() -> str:
            return "action_result"

        def compensation(result: str, extra: int, flag: bool = False) -> None:
            received_values.append((result, extra, flag))

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(
                    action=action,
                    compensation=compensation,
                    compensation_args=(42,),
                    compensation_kwargs={"flag": True},
                )
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        assert received_values == [("action_result", 42, True)]

    def test_compensation_with_previous_step_results(self):
        """Test passing previous step results to compensation."""
        compensation_calls = []

        def create_order() -> dict:
            return {"order_id": "ORDER-123"}

        def reserve_inventory(order: dict) -> dict:
            return {"order_id": order["order_id"], "inventory_id": "INV-456"}

        def cancel_order(order: dict) -> None:
            compensation_calls.append(("cancel_order", order["order_id"]))

        def release_inventory(inventory: dict, order: dict) -> None:
            # Receives both inventory (action result) and order (via compensation_args)
            compensation_calls.append(("release_inventory", inventory["inventory_id"], order["order_id"]))

        def failing_action() -> None:
            raise ValueError("Fail")

        def noop_compensation(result) -> None:
            pass

        try:
            with SyncSaga() as saga:
                order = saga.step(action=create_order, compensation=cancel_order)
                saga.step(
                    action=lambda: reserve_inventory(order),
                    compensation=release_inventory,
                    compensation_args=(order,),  # Pass order to compensation
                )
                saga.step(action=failing_action, compensation=noop_compensation)
        except ValueError:
            pass

        # Compensation should receive both action result and previous step data
        assert compensation_calls == [
            ("release_inventory", "INV-456", "ORDER-123"),
            ("cancel_order", "ORDER-123"),
        ]


class TestSyncCompensationFailures:
    """Test behavior when compensations themselves fail."""

    def test_compensation_failure_continues_chain(self):
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

        try:
            with SyncSaga() as saga:
                saga.step(action=lambda: action(1), compensation=working_compensation)
                saga.step(action=lambda: action(2), compensation=failing_compensation)
                saga.step(action=lambda: action(3), compensation=working_compensation)
                saga.step(action=trigger_failure, compensation=working_compensation)
        except ValueError as e:
            assert str(e) == "Trigger compensation"

        # All compensations should be attempted despite step 2's failure
        # Order: 3, 2 (fails), 1
        assert compensation_log == ["compensated_3", "failed_2", "compensated_1"]

    def test_multiple_compensation_failures(self):
        """Test multiple compensation failures."""
        compensation_attempts = []

        def action(value: int) -> int:
            return value

        def failing_compensation(result: int) -> None:
            compensation_attempts.append(result)
            raise RuntimeError(f"Compensation {result} failed")

        def trigger_failure() -> None:
            raise ValueError("Trigger compensation")

        try:
            with SyncSaga() as saga:
                saga.step(action=lambda: action(1), compensation=failing_compensation)
                saga.step(action=lambda: action(2), compensation=failing_compensation)
                saga.step(action=lambda: action(3), compensation=failing_compensation)
                saga.step(action=trigger_failure, compensation=failing_compensation)
        except ValueError as e:
            assert str(e) == "Trigger compensation"

        # All compensation attempts should occur despite failures
        assert compensation_attempts == [3, 2, 1]

    def test_compensation_failure_original_exception_preserved(self):
        """Test that original exception is raised even if compensation fails."""

        def action() -> int:
            return 1

        def failing_compensation(result: int) -> None:
            raise RuntimeError("Compensation failed")

        def trigger_failure() -> None:
            raise ValueError("Original error")

        # Should raise the original ValueError, not the compensation RuntimeError
        try:
            with SyncSaga() as saga:
                saga.step(action=action, compensation=failing_compensation)
                saga.step(action=trigger_failure, compensation=failing_compensation)
        except ValueError as e:
            assert str(e) == "Original error"


class TestSyncCompensationEdgeCases:
    """Test edge cases in compensation behavior."""

    def test_compensation_with_none_result(self):
        """Test compensation when action returns None."""
        received_values = []

        def action() -> None:
            pass

        def compensation(result: None) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(action=action, compensation=compensation)
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        assert received_values == [None]

    def test_compensation_with_complex_result(self):
        """Test compensation with complex data structures."""
        received_values = []

        def action() -> dict:
            return {"nested": {"data": [1, 2, 3]}, "status": "ok"}

        def compensation(result: dict) -> None:
            received_values.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        try:
            with SyncSaga() as saga:
                saga.step(action=action, compensation=compensation)
                saga.step(action=failing_action, compensation=compensation)
        except ValueError:
            pass

        assert received_values == [{"nested": {"data": [1, 2, 3]}, "status": "ok"}]

    def test_idempotent_compensation(self):
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

        try:
            with SyncSaga() as saga:
                saga.step(action=action, compensation=idempotent_compensation)
                saga.step(action=failing_action, compensation=idempotent_compensation)
        except ValueError:
            pass

        # Counter should be decremented once
        assert state["counter"] == 0
        assert state["cancelled"] is True
