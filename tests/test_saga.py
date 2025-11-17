"""Tests for core SimpleSaga functionality."""

import pytest

from simple_saga import SimpleSaga, StepResult


class TestSagaConstruction:
    """Test saga instance creation and step addition."""

    def test_create_empty_saga(self):
        """Test creating an empty saga."""
        saga = SimpleSaga()
        assert saga.steps == []
        assert saga.executed == []

    def test_add_single_step(self, mock_action, mock_compensation):
        """Test adding a single step to saga."""
        saga = SimpleSaga()
        result = saga.add_step(action=mock_action, compensation=mock_compensation)

        # Should return self for chaining
        assert result is saga
        assert len(saga.steps) == 1
        assert saga.steps[0].action == mock_action
        assert saga.steps[0].compensation == mock_compensation

    def test_add_multiple_steps(self, mock_action, mock_compensation):
        """Test adding multiple steps to saga."""
        saga = SimpleSaga()
        saga.add_step(action=mock_action, compensation=mock_compensation)
        saga.add_step(action=mock_action, compensation=mock_compensation)
        saga.add_step(action=mock_action, compensation=mock_compensation)

        assert len(saga.steps) == 3

    def test_builder_pattern(self, mock_action, mock_compensation):
        """Test fluent interface / builder pattern."""
        saga = (
            SimpleSaga()
            .add_step(action=mock_action, compensation=mock_compensation)
            .add_step(action=mock_action, compensation=mock_compensation)
            .add_step(action=mock_action, compensation=mock_compensation)
        )

        assert len(saga.steps) == 3

    def test_add_step_with_args(self):
        """Test adding step with action arguments."""

        def action(x: int, y: int) -> int:
            return x + y

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=(5, 3))

        assert saga.steps[0].action_args == (5, 3)
        assert saga.steps[0].action_kwargs == {}

    def test_add_step_with_kwargs(self):
        """Test adding step with action keyword arguments."""

        def action(x: int = 0, y: int = 0) -> int:
            return x + y

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_kwargs={"x": 5, "y": 3})

        assert saga.steps[0].action_args == ()
        assert saga.steps[0].action_kwargs == {"x": 5, "y": 3}

    def test_add_step_with_compensation_args(self):
        """Test adding step with compensation arguments."""

        def action() -> int:
            return 42

        def compensation(value: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, compensation_args=(100,))

        assert saga.steps[0].compensation_args == (100,)
        assert saga.steps[0].compensation_kwargs == {}


class TestSagaExecution:
    """Test saga execution with successful steps."""

    @pytest.mark.asyncio
    async def test_execute_empty_saga(self):
        """Test executing an empty saga."""
        saga = SimpleSaga()
        results = await saga.execute()

        assert results == []
        assert saga.executed == []

    @pytest.mark.asyncio
    async def test_execute_single_step(self, mock_action, mock_compensation):
        """Test executing saga with single step."""
        saga = SimpleSaga()
        saga.add_step(action=mock_action, compensation=mock_compensation)

        results = await saga.execute()

        assert len(results) == 1
        assert isinstance(results[0], StepResult)
        assert results[0].step_index == 0
        assert results[0].step_name == "action"
        assert results[0].result == 2  # mock_action returns value * 2, default value=1

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

        saga = SimpleSaga()
        saga.add_step(action=step1, compensation=compensation)
        saga.add_step(action=step2, compensation=compensation)
        saga.add_step(action=step3, compensation=compensation)

        results = await saga.execute()

        assert len(results) == 3
        assert results[0].result == "step1"
        assert results[1].result == "step2"
        assert results[2].result == "step3"

    @pytest.mark.asyncio
    async def test_execute_with_action_args(self):
        """Test executing saga with action arguments."""

        def action(x: int, y: int) -> int:
            return x * y

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_args=(5, 7))

        results = await saga.execute()

        assert len(results) == 1
        assert results[0].result == 35

    @pytest.mark.asyncio
    async def test_execute_with_action_kwargs(self):
        """Test executing saga with action keyword arguments."""

        def action(x: int = 0, y: int = 0) -> int:
            return x - y

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation, action_kwargs={"x": 10, "y": 3})

        results = await saga.execute()

        assert len(results) == 1
        assert results[0].result == 7

    @pytest.mark.asyncio
    async def test_step_results_metadata(self):
        """Test that step results contain correct metadata."""

        def my_custom_action() -> int:
            return 42

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=my_custom_action, compensation=compensation)

        results = await saga.execute()

        assert results[0].step_index == 0
        assert results[0].step_name == "my_custom_action"
        assert results[0].result == 42


class TestSagaReset:
    """Test saga reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_executed(self, mock_action, mock_compensation):
        """Test that reset clears executed steps."""
        saga = SimpleSaga()
        saga.add_step(action=mock_action, compensation=mock_compensation)

        await saga.execute()
        assert len(saga.executed) == 1

        saga.reset()
        assert saga.executed == []
        assert len(saga.steps) == 1  # Steps should remain

    @pytest.mark.asyncio
    async def test_execute_resets_automatically(self):
        """Test that execute resets executed steps automatically."""
        call_count = 0

        def action() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        # First execution
        results1 = await saga.execute()
        assert results1[0].result == 1
        assert len(saga.executed) == 1

        # Second execution should reset and re-execute
        results2 = await saga.execute()
        assert results2[0].result == 2
        assert len(saga.executed) == 1  # Only current execution


class TestSagaReusability:
    """Test that sagas can be reused multiple times."""

    @pytest.mark.asyncio
    async def test_reuse_saga_multiple_times(self):
        """Test executing the same saga multiple times."""
        execution_count = 0

        def action() -> int:
            nonlocal execution_count
            execution_count += 1
            return execution_count

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        # Execute multiple times
        results1 = await saga.execute()
        assert results1[0].result == 1

        results2 = await saga.execute()
        assert results2[0].result == 2

        results3 = await saga.execute()
        assert results3[0].result == 3

    @pytest.mark.asyncio
    async def test_reuse_saga_after_failure(self):
        """Test reusing saga after a previous failure."""
        call_count = 0

        def action() -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return call_count

        def compensation(result: int) -> None:
            pass

        saga = SimpleSaga()
        saga.add_step(action=action, compensation=compensation)

        # First execution fails
        with pytest.raises(ValueError, match="First call fails"):
            await saga.execute()

        # Second execution should succeed
        results = await saga.execute()
        assert results[0].result == 2
        assert len(saga.executed) == 1
