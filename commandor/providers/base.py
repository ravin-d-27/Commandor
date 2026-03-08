"""Slim providers/base.py — keeps only AgentResult for backward compatibility."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AgentResult:
    """Result returned by run_agent()."""

    success: bool
    final_answer: str
    steps: List[Any] = field(default_factory=list)
    iterations: int = 0
    error: Optional[str] = None
