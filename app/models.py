from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class EvidenceMap(BaseModel):
    signal: str = Field(..., description="Name of the signal or evidence source")
    effect: Literal["supports", "refutes", "context", "unknown"] = "context"
    detail: str = Field(..., description="How that signal influenced the ranking")


class Hypothesis(BaseModel):
    title: str = Field(..., description="Short title for the hypothesis")
    category: Literal["memory", "kernel", "disk", "thermal", "gpu", "power", "network", "unknown"] = "unknown"
    confidence: float = Field(..., ge=0.0, le=1.0)
    likely_root_cause: str
    evidence: List[str] = Field(default_factory=list)
    next_checks: List[str] = Field(default_factory=list)
    remediation: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    summary: str
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    analysis_notes: List[str] = Field(default_factory=list, description="Observable concise audit log, not hidden reasoning")
    evidence_map: List[EvidenceMap] = Field(default_factory=list)
    top_hypotheses: List[Hypothesis] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_priority: Literal["low", "medium", "high", "critical"] = "medium"
