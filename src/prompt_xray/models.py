from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    path: str
    label: str
    strength: str
    reasons: list[str] = Field(default_factory=list)


class ConfidenceScore(BaseModel):
    score: float
    level: str
    reasons: list[str] = Field(default_factory=list)


class PromptRuntimeLink(BaseModel):
    source_path: str
    target_path: str
    kind: str
    strength: str
    reasons: list[str] = Field(default_factory=list)


class FileAnalysis(BaseModel):
    path: str
    role: str
    language: str = ""
    runtime_level: str = "none"
    path_evidence: list[str] = Field(default_factory=list)
    text_evidence: list[str] = Field(default_factory=list)
    code_evidence: list[str] = Field(default_factory=list)
    graph_evidence: list[str] = Field(default_factory=list)
    negative_evidence: list[str] = Field(default_factory=list)


class RoleCount(BaseModel):
    role: str
    count: int


class EvidenceSummary(BaseModel):
    path_evidence: int = 0
    text_evidence: int = 0
    code_evidence: int = 0
    graph_evidence: int = 0
    negative_evidence: int = 0


class ScanLimits(BaseModel):
    max_file_size_kb: int
    max_code_files_per_language: int
    candidate_files_scanned: int = 0
    code_files_scanned: int = 0
    code_files_total: int = 0
    truncated_languages: list[str] = Field(default_factory=list)


class RepoInfo(BaseModel):
    name: str
    target: str
    source_type: str
    commit: str = ""
    root_path: str = ""


class BehaviorSource(BaseModel):
    path: str
    score: float
    kinds: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    id: str
    kind: str
    path: str
    title: str
    summary: str
    signals: list[str] = Field(default_factory=list)
    confidence: float
    source_snippet: str = ""


class Summary(BaseModel):
    repo_family: str = "unclear"
    repo_archetype: str
    orchestration_model: str
    memory_model: str
    xray_call: str = ""
    verdict: str = ""


class Counts(BaseModel):
    candidate_files: int
    artifacts: int


class RealVsPackaging(BaseModel):
    real_implementation: list[str] = Field(default_factory=list)
    prompt_config_structure: list[str] = Field(default_factory=list)
    presentation_marketing_layer: list[str] = Field(default_factory=list)


class ScanReport(BaseModel):
    repo: RepoInfo
    summary: Summary
    counts: Counts
    tooling_surfaces: list[str] = Field(default_factory=list)
    behavior_sources: list[BehaviorSource] = Field(default_factory=list)
    missing_runtime_pieces: list[str] = Field(default_factory=list)
    real_vs_packaging: RealVsPackaging
    file_roles_summary: list[RoleCount] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    runtime_evidence: list[EvidenceItem] = Field(default_factory=list)
    memory_evidence: list[EvidenceItem] = Field(default_factory=list)
    orchestration_evidence: list[EvidenceItem] = Field(default_factory=list)
    repo_family_confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(score=0.0, level="low"))
    repo_archetype_confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(score=0.0, level="low"))
    orchestration_confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(score=0.0, level="low"))
    memory_confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(score=0.0, level="low"))
    overall_confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(score=0.0, level="low"))
    contradictions: list[str] = Field(default_factory=list)
    prompt_runtime_links: list[PromptRuntimeLink] = Field(default_factory=list)
    scan_limits: ScanLimits = Field(default_factory=lambda: ScanLimits(max_file_size_kb=1024, max_code_files_per_language=400))
    file_analyses: list[FileAnalysis] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
