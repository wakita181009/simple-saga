"""Simple Saga Pattern Library for Python.

A lightweight implementation of the Saga pattern for managing distributed transactions.
"""

from .saga import SimpleSaga
from .schema import SagaStep, StepResult

__version__ = "0.0.1"
__all__ = ["SimpleSaga", "StepResult", "SagaStep"]
