"""Tests for mixed synchronous and asynchronous saga steps."""

import asyncio

import pytest

from simple_saga import SimpleSaga


class TestAsyncActions:
    """Test sagas with async actions."""

    @pytest.mark.asyncio
    async def test_single_async_action(self):
        """Test saga with single async action."""

        async def async_action() -> str:
            await asyncio.sleep(0.01)
            return "async_result"

        def compensation(result: str) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=async_action, compensation=compensation)

        results = await saga.execute()

        assert len(results) == 1
        assert results[0].result == "async_result"

    @pytest.mark.asyncio
    async def test_multiple_async_actions(self):
        """Test saga with multiple async actions."""

        async def action1() -> int:
            await asyncio.sleep(0.01)
            return 1

        async def action2() -> int:
            await asyncio.sleep(0.01)
            return 2

        async def action3() -> int:
            await asyncio.sleep(0.01)
            return 3

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action1, compensation=compensation)
        saga.add_step(action=action2, compensation=compensation)
        saga.add_step(action=action3, compensation=compensation)

        results = await saga.execute()

        assert len(results) == 3
        assert results[0].result == 1
        assert results[1].result == 2
        assert results[2].result == 3


class TestAsyncCompensations:
    """Test sagas with async compensations."""

    @pytest.mark.asyncio
    async def test_async_compensation_called(self):
        """Test that async compensations are called on failure."""
        compensation_calls = []

        def action() -> int:
            return 42

        async def async_compensation(result: int) -> None:
            await asyncio.sleep(0.01)
            compensation_calls.append(result)

        def failing_action() -> None:
            raise RuntimeError("Action failed")

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=async_compensation)
        saga.add_step(action=failing_action, compensation=async_compensation)

        with pytest.raises(RuntimeError, match="Action failed"):
            await saga.execute()

        # Async compensation should have been called
        assert compensation_calls == [42]


class TestMixedSyncAsync:
    """Test sagas with mixed sync and async steps."""

    @pytest.mark.asyncio
    async def test_sync_action_async_compensation(self):
        """Test sync action with async compensation."""
        compensation_called = []

        def sync_action() -> str:
            return "sync"

        async def async_compensation(result: str) -> None:
            await asyncio.sleep(0.01)
            compensation_called.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=sync_action, compensation=async_compensation)
        saga.add_step(action=failing_action, compensation=async_compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert compensation_called == ["sync"]

    @pytest.mark.asyncio
    async def test_async_action_sync_compensation(self):
        """Test async action with sync compensation."""
        compensation_called = []

        async def async_action() -> str:
            await asyncio.sleep(0.01)
            return "async"

        def sync_compensation(result: str) -> None:
            compensation_called.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=async_action, compensation=sync_compensation)
        saga.add_step(action=failing_action, compensation=sync_compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert compensation_called == ["async"]

    @pytest.mark.asyncio
    async def test_mixed_multiple_steps(self):
        """Test saga with various combinations of sync/async steps."""

        async def async_action1() -> str:
            await asyncio.sleep(0.01)
            return "async1"

        def sync_action2() -> str:
            return "sync2"

        async def async_action3() -> str:
            await asyncio.sleep(0.01)
            return "async3"

        def sync_action4() -> str:
            return "sync4"

        def compensation(result: str) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=async_action1, compensation=compensation)
        saga.add_step(action=sync_action2, compensation=compensation)
        saga.add_step(action=async_action3, compensation=compensation)
        saga.add_step(action=sync_action4, compensation=compensation)

        results = await saga.execute()

        assert len(results) == 4
        assert results[0].result == "async1"
        assert results[1].result == "sync2"
        assert results[2].result == "async3"
        assert results[3].result == "sync4"

    @pytest.mark.asyncio
    async def test_mixed_compensations(self):
        """Test mixed sync/async compensations are called in correct order."""
        compensation_log = []

        async def async_action1() -> int:
            await asyncio.sleep(0.01)
            return 1

        def sync_action2() -> int:
            return 2

        async def async_action3() -> int:
            await asyncio.sleep(0.01)
            return 3

        def sync_compensation(result: int) -> None:
            compensation_log.append(("sync", result))

        async def async_compensation(result: int) -> None:
            await asyncio.sleep(0.01)
            compensation_log.append(("async", result))

        def failing_action() -> None:
            raise RuntimeError("Fail at step 4")

        saga = SimpleSaga()
        saga.add_step(action=async_action1, compensation=async_compensation)
        saga.add_step(action=sync_action2, compensation=sync_compensation)
        saga.add_step(action=async_action3, compensation=async_compensation)
        saga.add_step(action=failing_action, compensation=sync_compensation)

        with pytest.raises(RuntimeError, match="Fail at step 4"):
            await saga.execute()

        # Compensations should be called in reverse order: 3, 2, 1
        assert compensation_log == [("async", 3), ("sync", 2), ("async", 1)]


class TestAsyncWithArguments:
    """Test async actions/compensations with various argument patterns."""

    @pytest.mark.asyncio
    async def test_async_action_with_args(self):
        """Test async action with positional arguments."""

        async def async_action(x: int, y: int) -> int:
            await asyncio.sleep(0.01)
            return x + y

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=async_action, compensation=compensation, action_args=(10, 20))

        results = await saga.execute()

        assert results[0].result == 30

    @pytest.mark.asyncio
    async def test_async_action_with_kwargs(self):
        """Test async action with keyword arguments."""

        async def async_action(x: int = 0, y: int = 0, z: int = 0) -> int:
            await asyncio.sleep(0.01)
            return x * y * z

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=async_action, compensation=compensation, action_kwargs={"x": 2, "y": 3, "z": 4})

        results = await saga.execute()

        assert results[0].result == 24

    @pytest.mark.asyncio
    async def test_async_compensation_with_args(self):
        """Test async compensation with explicit arguments."""
        compensation_calls = []

        def action() -> int:
            return 100

        async def async_compensation(value: int, multiplier: int) -> None:
            await asyncio.sleep(0.01)
            compensation_calls.append(value * multiplier)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(
            action=action,
            compensation=async_compensation,
            compensation_args=(50,),
            compensation_kwargs={"multiplier": 2},
        )
        saga.add_step(action=failing_action, compensation=async_compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        # Should use explicit compensation args, not action result
        assert compensation_calls == [100]

    @pytest.mark.asyncio
    async def test_async_compensation_default_receives_result(self):
        """Test async compensation receives action result by default."""
        compensation_calls = []

        async def async_action() -> str:
            await asyncio.sleep(0.01)
            return "action_result"

        async def async_compensation(result: str) -> None:
            await asyncio.sleep(0.01)
            compensation_calls.append(result)

        def failing_action() -> None:
            raise ValueError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=async_action, compensation=async_compensation)
        saga.add_step(action=failing_action, compensation=async_compensation)

        with pytest.raises(ValueError):
            await saga.execute()

        assert compensation_calls == ["action_result"]


class TestConcurrentBehavior:
    """Test behavior related to concurrent execution patterns."""

    @pytest.mark.asyncio
    async def test_steps_execute_sequentially(self):
        """Test that steps execute sequentially, not in parallel."""
        execution_order = []

        async def action1() -> None:
            execution_order.append("start1")
            await asyncio.sleep(0.02)
            execution_order.append("end1")

        async def action2() -> None:
            execution_order.append("start2")
            await asyncio.sleep(0.01)
            execution_order.append("end2")

        def compensation(result: None) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action1, compensation=compensation)
        saga.add_step(action=action2, compensation=compensation)

        await saga.execute()

        # Action2 should only start after action1 completes
        assert execution_order == ["start1", "end1", "start2", "end2"]

    @pytest.mark.asyncio
    async def test_compensations_execute_sequentially(self):
        """Test that compensations execute sequentially in reverse order."""
        compensation_order = []

        def action1() -> int:
            return 1

        def action2() -> int:
            return 2

        def action3() -> int:
            return 3

        async def compensation1(result: int) -> None:
            compensation_order.append("start1")
            await asyncio.sleep(0.02)
            compensation_order.append("end1")

        async def compensation2(result: int) -> None:
            compensation_order.append("start2")
            await asyncio.sleep(0.01)
            compensation_order.append("end2")

        async def compensation3(result: int) -> None:
            compensation_order.append("start3")
            await asyncio.sleep(0.01)
            compensation_order.append("end3")

        def failing_action() -> None:
            raise RuntimeError("Fail")

        saga = SimpleSaga()
        saga.add_step(action=action1, compensation=compensation1)
        saga.add_step(action=action2, compensation=compensation2)
        saga.add_step(action=action3, compensation=compensation3)
        saga.add_step(action=failing_action, compensation=compensation1)

        with pytest.raises(RuntimeError):
            await saga.execute()

        # Compensations should execute in reverse order: 3, 2, 1
        # Each should complete before the next starts
        assert compensation_order == ["start3", "end3", "start2", "end2", "start1", "end1"]
