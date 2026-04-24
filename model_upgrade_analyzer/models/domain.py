"""Core domain models shared across ingest, scanners, analysis, and reporting."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Urgency(str, Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IMMEDIATE = "immediate"


class DeploymentType(str, Enum):
    """Azure OpenAI / LLM deployment SKU category.

    - PTU / provisioned: capacity-reserved (ProvisionedManaged, DataZoneProvisioned,
      GlobalProvisionedManaged).
    - STANDARD / pay-as-you-go: token-billed (Standard, GlobalStandard, DataZoneStandard).
    - BATCH: offline batch deployments.
    """

    UNKNOWN = "unknown"
    STANDARD = "standard"
    PTU = "ptu"
    BATCH = "batch"


@dataclass
class Evidence:
    """A fact anchored to a file/line, supporting a finding."""

    file_path: str
    line: int | None = None
    snippet: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "snippet": self.snippet,
            "detail": self.detail,
        }


@dataclass
class Finding:
    """A single observation produced by a scanner or analyzer."""

    finding_type: str
    severity: Severity
    confidence: Confidence
    message: str
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None
    tags: list[str] = field(default_factory=list)
    related_model: str | None = None
    related_deployment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
            "recommendation": self.recommendation,
            "tags": list(self.tags),
            "related_model": self.related_model,
            "related_deployment": self.related_deployment,
        }


@dataclass
class ModelIQRecord:
    """A normalized Model IQ entry."""

    deployment_name: str | None = None
    current_model: str | None = None
    current_version: str | None = None
    recommended_replacement: str | None = None
    retirement_date: date | None = None
    region: str | None = None
    subscription: str | None = None
    sku: str | None = None
    environment: str | None = None
    urgency: Urgency = Urgency.UNKNOWN
    deployment_type: DeploymentType = DeploymentType.UNKNOWN
    capacity: int | None = None  # PTU units when applicable
    notes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_name": self.deployment_name,
            "current_model": self.current_model,
            "current_version": self.current_version,
            "recommended_replacement": self.recommended_replacement,
            "retirement_date": self.retirement_date.isoformat() if self.retirement_date else None,
            "region": self.region,
            "subscription": self.subscription,
            "sku": self.sku,
            "environment": self.environment,
            "urgency": self.urgency.value,
            "deployment_type": self.deployment_type.value,
            "capacity": self.capacity,
            "notes": self.notes,
        }


@dataclass
class ModelCard:
    """Normalized lifecycle metadata for a model."""

    model_name: str
    replacement: str | None = None
    retirement_date: date | None = None
    context_window: int | None = None
    modalities: list[str] = field(default_factory=list)
    supports_structured_output: bool | None = None
    supports_reasoning: bool | None = None
    migration_notes: str | None = None
    source_path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "replacement": self.replacement,
            "retirement_date": self.retirement_date.isoformat() if self.retirement_date else None,
            "context_window": self.context_window,
            "modalities": list(self.modalities),
            "supports_structured_output": self.supports_structured_output,
            "supports_reasoning": self.supports_reasoning,
            "migration_notes": self.migration_notes,
            "source_path": self.source_path,
        }


@dataclass
class CodeReference:
    """A detected reference in source code or config."""

    file_path: str
    line: int
    reference_kind: str  # e.g. 'model_name', 'deployment_name', 'endpoint', 'param'
    value: str
    context: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "reference_kind": self.reference_kind,
            "value": self.value,
            "context": self.context,
        }


@dataclass
class PromptObservation:
    """A prompt-file observation relevant to model upgrades."""

    file_path: str
    trait: str  # e.g. 'strict_json', 'chain_of_thought', 'token_heavy'
    detail: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "trait": self.trait,
            "detail": self.detail,
            "line": self.line,
        }


@dataclass
class DeploymentImpact:
    """Per-deployment correlated impact view."""

    deployment_name: str
    current_model: str | None = None
    target_model: str | None = None
    urgency: Urgency = Urgency.UNKNOWN
    deployment_type: DeploymentType = DeploymentType.UNKNOWN
    capacity: int | None = None
    retirement_date: date | None = None
    code_references: list[CodeReference] = field(default_factory=list)
    prompt_files: list[str] = field(default_factory=list)
    config_references: list[CodeReference] = field(default_factory=list)
    parameters_affected: list[str] = field(default_factory=list)
    migration_complexity: str = "unknown"  # low | medium | high | unknown
    recommended_validation: list[str] = field(default_factory=list)
    model_card_notes: str | None = None
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_name": self.deployment_name,
            "current_model": self.current_model,
            "target_model": self.target_model,
            "urgency": self.urgency.value,
            "deployment_type": self.deployment_type.value,
            "capacity": self.capacity,
            "retirement_date": self.retirement_date.isoformat() if self.retirement_date else None,
            "code_references": [r.to_dict() for r in self.code_references],
            "prompt_files": list(self.prompt_files),
            "config_references": [r.to_dict() for r in self.config_references],
            "parameters_affected": list(self.parameters_affected),
            "migration_complexity": self.migration_complexity,
            "recommended_validation": list(self.recommended_validation),
            "model_card_notes": self.model_card_notes,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class AnalysisReport:
    """Top-level report aggregate."""

    generated_at: str
    repo_path: str
    modeliq_records: list[ModelIQRecord] = field(default_factory=list)
    model_cards: list[ModelCard] = field(default_factory=list)
    code_references: list[CodeReference] = field(default_factory=list)
    prompt_observations: list[PromptObservation] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    deployments: list[DeploymentImpact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "repo_path": self.repo_path,
            "modeliq_records": [r.to_dict() for r in self.modeliq_records],
            "model_cards": [m.to_dict() for m in self.model_cards],
            "code_references": [r.to_dict() for r in self.code_references],
            "prompt_observations": [p.to_dict() for p in self.prompt_observations],
            "findings": [f.to_dict() for f in self.findings],
            "deployments": [d.to_dict() for d in self.deployments],
        }
