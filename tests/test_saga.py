"""Tests for core SimpleSaga functionality with Arrow-kt style API."""

import pytest

from simple_saga import SimpleSaga


class TestSagaConstruction:
    """Test saga instance creation."""

    def test_create_empty_saga(self):
        """Test creating an empty saga."""
        saga = SimpleSaga()
        assert saga._steps == []
        assert saga._executed == []

    @pytest.mark.asyncio
    async def test_context_manager_entry(self):
        """Test entering saga context manager."""
        async with SimpleSaga() as saga:
            assert saga._steps == []
            assert saga._executed == []


class TestSagaExecution:
    """Test saga execution with successful steps."""

    @pytest.mark.asyncio
    async def test_execute_empty_saga(self):
        """Test executing an empty saga."""
        async with SimpleSaga() as saga:
            pass  # No steps

        assert saga._executed == []

    @pytest.mark.asyncio
    async def test_execute_single_step(self):
        """Test executing saga with single step."""

        def action() -> int:
            return 42

        def compensation(result: int) -> None:
            pass

        async with SimpleSaga() as saga:
            result = await saga.step(action=action, compensation=compensation)

            assert result == 42
            assert len(saga._executed) == 1
            assert saga._executed[0].result == 42

    @pytest.mark.asyncio
    async def test_execute_multiple_steps(self):
        """Test executing saga with multiple steps."""

        def step1() -> str:
            return "step1"

        def step2() -> str:
            return "step2"

        def step3() -> str:
            return "step3"

        def compensation(result: str) -> None:
            pass

        async with SimpleSaga() as saga:
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

        def action(x: int, y: int) -> int:
            return x * y

        def compensation(result: int) -> None:
            pass

        async with SimpleSaga() as saga:
            result = await saga.step(action=action, compensation=compensation, action_args=(5, 7))

            assert result == 35

    @pytest.mark.asyncio
    async def test_execute_with_action_kwargs(self):
        """Test executing saga with action keyword arguments."""

        def action(x: int = 0, y: int = 0) -> int:
            return x - y

        def compensation(result: int) -> None:
            pass

        async with SimpleSaga() as saga:
            result = await saga.step(action=action, compensation=compensation, action_kwargs={"x": 10, "y": 3})

            assert result == 7

    @pytest.mark.asyncio
    async def test_step_results_metadata(self):
        """Test that step results contain correct metadata."""

        def my_custom_action() -> int:
            return 42

        def compensation(result: int) -> None:
            pass

        async with SimpleSaga() as saga:
            await saga.step(action=my_custom_action, compensation=compensation)

            assert saga._executed[0].step_index == 0
            assert saga._executed[0].step_name == "my_custom_action"
            assert saga._executed[0].result == 42


class TestArrowKtStyleChaining:
    """Test Arrow-kt style result chaining between steps."""

    @pytest.mark.asyncio
    async def test_use_previous_result_in_next_step(self):
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

        async with SimpleSaga() as saga:
            # Step 1: Create order
            order = await saga.step(
                action=lambda: create_order("ORDER-123"),
                compensation=lambda order: cancel_order(order),
            )

            # Step 2: Reserve inventory (uses order from step 1)
            inventory = await saga.step(
                action=lambda: reserve_inventory(order),
                compensation=lambda inv: release_inventory(inv),
            )

            # Step 3: Charge payment (uses inventory from step 2)
            payment = await saga.step(
                action=lambda: charge_payment(inventory),
                compensation=lambda pay: refund_payment(pay),
            )

            assert order["order_id"] == "ORDER-123"
            assert inventory["inventory_reserved"] is True
            assert payment["payment_status"] == "charged"
            assert len(saga._executed) == 3

    @pytest.mark.asyncio
    async def test_complex_data_flow(self):
        """Test complex data flow between steps."""

        async with SimpleSaga() as saga:
            # Step 1: Initialize data
            data = await saga.step(
                action=lambda: {"value": 10},
                compensation=lambda: None,
            )

            # Step 2: Transform data
            doubled = await saga.step(
                action=lambda: {"value": data["value"] * 2},
                compensation=lambda: None,
            )

            # Step 3: Accumulate
            total = await saga.step(
                action=lambda: {"total": data["value"] + doubled["value"]},
                compensation=lambda: None,
            )

            assert data["value"] == 10
            assert doubled["value"] == 20
            assert total["total"] == 30


class TestSagaReusability:
    """Test that sagas can be reused multiple times."""

    @pytest.mark.asyncio
    async def test_reuse_saga_multiple_times(self):
        """Test executing the same saga definition multiple times."""
        execution_count = 0

        def action() -> int:
            nonlocal execution_count
            execution_count += 1
            return execution_count

        def compensation(result: int) -> None:
            pass

        # First execution
        async with SimpleSaga() as saga:
            result1 = await saga.step(action=action, compensation=compensation)
            assert result1 == 1

        # Second execution
        async with SimpleSaga() as saga:
            result2 = await saga.step(action=action, compensation=compensation)
            assert result2 == 2

        # Third execution
        async with SimpleSaga() as saga:
            result3 = await saga.step(action=action, compensation=compensation)
            assert result3 == 3

    @pytest.mark.asyncio
    async def test_context_manager_resets_state(self):
        """Test that each context manager entry resets state."""
        saga_instance = SimpleSaga()

        # First use
        async with saga_instance as saga:
            await saga.step(action=lambda: 1, compensation=lambda: None)
            assert len(saga._executed) == 1

        # Second use should have clean state
        async with saga_instance as saga:
            assert len(saga._executed) == 0
            await saga.step(action=lambda: 2, compensation=lambda: None)
            assert len(saga._executed) == 1
