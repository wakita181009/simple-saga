"""Simple Saga Pattern Library for Python.

A lightweight implementation of the Saga pattern for managing distributed transactions.
"""

from .saga import SimpleSaga
from .schema import StepResult, SagaStep

__version__ = "0.1.0"
__all__ = ["SimpleSaga", "StepResult", "SagaStep"]
