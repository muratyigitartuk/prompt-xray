from __future__ import annotations

from pydantic import BaseModel, Field


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
    repo_archetype: str
    orchestration_model: str
    memory_model: str
    xray_call: str = ""
    verdict: str


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
    artifacts: list[Artifact] = Field(default_factory=list)
