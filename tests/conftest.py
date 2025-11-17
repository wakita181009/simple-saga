"""Pytest configuration and shared fixtures for simple-saga tests."""

import pytest


@pytest.fixture
def mock_action():
    """Create a mock synchronous action function."""

    def action(value: int = 1) -> int:
        return value * 2

    return action


@pytest.fixture
def mock_compensation():
    """Create a mock synchronous compensation function."""
    calls = []

    def compensation(result: int) -> None:
        calls.append(result)

    compensation.calls = calls  # type: ignore
    return compensation


@pytest.fixture
async def mock_async_action():
    """Create a mock asynchronous action function."""

    async def action(value: int = 1) -> int:
        return value * 2

    return action


@pytest.fixture
def mock_async_compensation():
    """Create a mock asynchronous compensation function."""
    calls = []

    async def compensation(result: int) -> None:
        calls.append(result)

    compensation.calls = calls  # type: ignore
    return compensation
