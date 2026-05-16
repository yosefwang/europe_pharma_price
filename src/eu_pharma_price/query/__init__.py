"""Researcher-facing query interface."""

from .api import (
    CandidateBundle,
    ComparisonRow,
    QueueEntry,
    available_molecules,
    available_windows,
    candidate_with_evidence,
    candidates_for_molecule,
    queue_for_window,
)
from .report import generate_report

__all__ = [
    "CandidateBundle",
    "ComparisonRow",
    "QueueEntry",
    "available_molecules",
    "available_windows",
    "candidate_with_evidence",
    "candidates_for_molecule",
    "generate_report",
    "queue_for_window",
]
