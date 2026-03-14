"""Simple Saga Pattern Library for Python.

A lightweight implementation of the Saga pattern for managing distributed transactions.
"""

from .saga.saga import Saga
from .saga.sync_saga import SyncSaga
from .schema import SagaStep, StepResult, SyncSagaStep

__version__ = __import__("importlib.metadata", fromlist=["version"]).version("simple-saga")
__all__ = ["Saga", "SyncSaga", "SagaStep", "StepResult", "SyncSagaStep"]
