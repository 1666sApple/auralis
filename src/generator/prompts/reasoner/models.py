"""Data models for reasoning traces."""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ReasoningTrace:
    """Represents a reasoning trace for transparency."""

    method: str
    branches: List[str]
    conclusions: List[Dict[str, Any]]
    confidence: float
    citations: List[str]


@dataclass
class ThoughtBranch:
    """Represents a single thought branch in Tree of Thought."""

    id: str
    steps: List[str]
    conclusion: str
    citations: List[str]
    value_score: float
