from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .discovery import discover_candidate_files, discover_runtime_markers
from .intake import resolve_target
from .models import Artifact, BehaviorSource, Counts, RealVsPackaging, ScanReport, Summary

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

KIND_SIGNAL_MAP = {
    "system_prompt": {
        "paths": ("agents.md", "system", "copilot-instructions"),
        "phrases": ("you are", "system prompt", "instructions", "must follow"),
    },
    "agent_prompt": {
        "paths": ("agents/", "agent", "claude", "opencode"),
        "phrases": ("you are", "your identity", "core mission", "agent personality"),
    },
    "skill_definition": {
        "paths": ("skill.md", "skills/", "antigravity"),
        "phrases": ("when to use this skill", "default_prompt", "use this skill"),
    },
    "rule_file": {
        "paths": (".cursor/rules", ".windsurfrules", "copilot-instructions", ".mdc"),
        "phrases": ("alwaysapply", "globs:", "copilot instructions", ".windsurfrules"),
    },
    "workflow_instruction": {
        "paths": ("workflow", "playbook", "runbook"),
        "phrases": ("phase 1", "phase 2", "handoff", "activate", "spawn agent"),
    },
    "tool_contract": {
        "paths": ("integration", "tool", "mcp"),
        "phrases": ("tools:", "supported tools", "mcpservers", "install.sh", "convert.sh"),
    },
    "memory_pattern": {
        "paths": ("memory",),
        "phrases": ("remember", "recall", "rollback", "memory integration"),
    },
    "integration_manifest": {
        "paths": ("integrations/", "extension", "manifest", "openai.yaml"),
        "phrases": ("supported tools", "compatible with", "tool-specific", "gemini-extension.json"),
    },
    "persona_definition": {
        "paths": ("agent", "skill"),
        "phrases": ("personality", "vibe", "communication style", "identity & memory"),
    },
    "evaluation_pattern": {
        "paths": ("testing", "qa", "benchmark", "reality-checker"),
        "phrases": ("success metrics", "quality gate", "pass/fail", "production readiness"),
    },
}

TOOLING_PATTERNS = {
    "Claude Code": ("claude", ".claude", "claude-code"),
    "Cursor": (".cursor", "cursor"),
    "Copilot": ("copilot", ".github/copilot-instructions.md"),
    "Gemini CLI": ("gemini", "antigravity"),
    "Windsurf": ("windsurf", ".windsurfrules"),
    "OpenCode": ("opencode",),
    "Aider": ("aider", "conventions.md"),
    "MCP": ("mcp", "mcpservers"),
}

TOOLING_FILE_HINTS = {
    "Claude Code": ("claude-code", ".claude", "agents/"),
    "Cursor": (".cursor/rules", "cursor", ".mdc"),
    "Copilot": ("copilot-instructions", ".github/agents", "github-copilot"),
    "Gemini CLI": ("gemini", "antigravity", "gemini-cli"),
    "Windsurf": (".windsurfrules", "windsurf"),
    "OpenCode": ("opencode",),
    "Aider": ("aider", "conventions.md"),
    "MCP": (".mcp", "mcp-memory", "mcpservers", "modelcontextprotocol"),
}

FRONTMATTER_BY_KIND = {
    "agent_prompt": ("name", "description", "vibe"),
    "skill_definition": ("name", "description"),
    "tool_contract": ("tools", "services"),
    "persona_definition": ("vibe",),
}


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    frontmatter: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip().lower()] = value.strip()
    return frontmatter


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _file_title(path: Path, frontmatter: dict[str, str]) -> str:
    if frontmatter.get("name"):
        return frontmatter["name"]
    return path.name


def _signals_for_kind(path_text: str, text_lower: str, frontmatter: dict[str, str], kind: str) -> list[str]:
    path_signals: list[str] = []
    text_signals: list[str] = []
    frontmatter_signals: list[str] = []
    rules = KIND_SIGNAL_MAP[kind]

    for marker in rules["paths"]:
        if marker in path_text:
            path_signals.append(f"path:{marker}")
    for phrase in rules["phrases"]:
        if phrase in text_lower:
            text_signals.append(f"text:{phrase}")

    for key in FRONTMATTER_BY_KIND.get(kind, ()):
        if key in frontmatter:
            frontmatter_signals.append(f"frontmatter:{key}")

    if not path_signals and not text_signals:
        return []

    signals = path_signals + text_signals + frontmatter_signals
    return sorted(set(signals))


def _artifact_summary(kind: str, path: Path) -> str:
    short_path = path.as_posix()
    messages = {
        "agent_prompt": f"Prompt-like agent definition in {short_path}.",
        "skill_definition": f"Skill definition or skill-like instruction source in {short_path}.",
        "rule_file": f"Tool-specific rule or instruction file in {short_path}.",
        "workflow_instruction": f"Workflow or handoff instructions detected in {short_path}.",
        "tool_contract": f"Tool contract or integration guidance detected in {short_path}.",
        "memory_pattern": f"Memory or recall behavior is described in {short_path}.",
        "integration_manifest": f"Integration manifest or packaging surface found in {short_path}.",
        "persona_definition": f"Persona/voice layer detected in {short_path}.",
        "evaluation_pattern": f"Evaluation or quality-gate pattern found in {short_path}.",
        "system_prompt": f"System-level instruction source detected in {short_path}.",
    }
    return messages[kind]


def _source_snippet(text: str, signals: list[str], include_snippets: bool) -> str:
    if not include_snippets:
        return ""

    evidence_terms = [signal.split(":", 1)[1] for signal in signals if signal.startswith("text:")]
    if not evidence_terms:
        evidence_terms = ["you are", "workflow", "remember", "tools:"]

    snippets: list[str] = []
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        line_lower = line_clean.lower()
        if any(term in line_lower for term in evidence_terms):
            snippets.append(_normalize_text(line_clean))
        if len(snippets) == 3:
            break

    return " | ".join(snippets)[:400]


def _build_artifacts(candidate_files: list[Path], repo_path: Path, include_snippets: bool) -> list[Artifact]:
    artifacts: list[Artifact] = []

    for file_path in candidate_files:
        rel_path = file_path.relative_to(repo_path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        text_lower = text.lower()
        path_text = rel_path.as_posix().lower()
        frontmatter = _parse_frontmatter(text)

        for kind in KIND_SIGNAL_MAP:
            signals = _signals_for_kind(path_text, text_lower, frontmatter, kind)
            if len(signals) < 2:
                continue

            confidence = min(0.45 + (0.08 * len(signals)), 0.98)
            artifacts.append(
                Artifact(
                    id=f"{rel_path.as_posix()}::{kind}",
                    kind=kind,
                    path=rel_path.as_posix(),
                    title=_file_title(rel_path, frontmatter),
                    summary=_artifact_summary(kind, rel_path),
                    signals=signals,
                    confidence=round(confidence, 2),
                    source_snippet=_source_snippet(text, signals, include_snippets),
                )
            )

    unique: dict[str, Artifact] = {}
    for artifact in artifacts:
        unique[artifact.id] = artifact
    return sorted(unique.values(), key=lambda item: (item.path, item.kind))


def _detect_tooling_surfaces(candidate_files: list[Path], artifacts: list[Artifact]) -> list[str]:
    path_haystack = " ".join([path.as_posix().lower() for path in candidate_files] + [a.path.lower() for a in artifacts])
    content_haystack = ""
    for path in candidate_files[:200]:
        try:
            content_haystack += "\n" + path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue

    tooling: list[str] = []
    for name, patterns in TOOLING_PATTERNS.items():
        score = 0
        if any(pattern.lower() in path_haystack for pattern in TOOLING_FILE_HINTS[name]):
            score += 2
        if any(pattern.lower() in content_haystack for pattern in patterns):
            score += 1
        if score >= 2:
            tooling.append(name)

    return sorted(set(tooling))


def _behavior_sources(artifacts: list[Artifact]) -> list[BehaviorSource]:
    weights = {
        "system_prompt": 6.0,
        "agent_prompt": 5.0,
        "skill_definition": 5.0,
        "rule_file": 4.5,
        "workflow_instruction": 4.0,
        "tool_contract": 3.5,
        "memory_pattern": 3.5,
        "integration_manifest": 3.0,
        "persona_definition": 2.5,
        "evaluation_pattern": 2.5,
    }
    scores: dict[str, float] = defaultdict(float)
    kinds: dict[str, set[str]] = defaultdict(set)
    reasons: dict[str, set[str]] = defaultdict(set)

    for artifact in artifacts:
        score = weights.get(artifact.kind, 2.0) * artifact.confidence
        path_lower = artifact.path.lower()
        if path_lower in {"readme.md", "contributing.md"}:
            score *= 0.35
        elif path_lower.endswith("/readme.md"):
            score *= 0.7
        if "/tests/" in path_lower or "__tests__" in path_lower or Path(path_lower).name.startswith("test"):
            score *= 0.35
        if path_lower.startswith("docs/") or "/docs/" in path_lower:
            score *= 0.8
        scores[artifact.path] += score
        kinds[artifact.path].add(artifact.kind)
        for signal in artifact.signals[:3]:
            reasons[artifact.path].add(signal)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]
    return [
        BehaviorSource(
            path=path,
            score=round(score, 2),
            kinds=sorted(kinds[path]),
            reasons=sorted(reasons[path]),
        )
        for path, score in ranked
    ]


def _orchestration_model(artifacts: list[Artifact], runtime_markers: list[str]) -> str:
    prompt_orchestration = any(
        artifact.kind == "workflow_instruction"
        and any(token in " ".join(artifact.signals) for token in ("spawn agent", "handoff", "phase 1"))
        for artifact in artifacts
    )
    has_mcp_or_tools = any(artifact.kind == "tool_contract" for artifact in artifacts)
    if runtime_markers:
        return "runtime-implemented"
    if prompt_orchestration:
        return "prompt-defined"
    if has_mcp_or_tools:
        return "tool-assisted"
    return "none"


def _memory_model(artifacts: list[Artifact], runtime_markers: list[str]) -> str:
    memory_artifacts = [artifact for artifact in artifacts if artifact.kind == "memory_pattern"]
    code_memory_markers = [
        marker
        for marker in runtime_markers
        if not marker.lower().endswith("readme.md")
        and any(
            token in marker.lower()
            for token in ("memory", "state", "store", "history", "session", "checkpoint")
        )
    ]
    if code_memory_markers:
        return "implemented-runtime"
    if not memory_artifacts:
        return "none"
    if any("mcp" in " ".join(artifact.signals).lower() for artifact in memory_artifacts):
        return "tool-assisted"
    return "documented-only"


def _repo_archetype(
    artifacts: list[Artifact],
    runtime_markers: list[str],
    tooling_surfaces: list[str],
) -> str:
    counts = Counter(artifact.kind for artifact in artifacts)
    prompt_total = sum(
        counts[kind]
        for kind in (
            "system_prompt",
            "agent_prompt",
            "skill_definition",
            "rule_file",
            "workflow_instruction",
            "persona_definition",
        )
    )
    integration_total = counts["integration_manifest"] + counts["tool_contract"]
    workflow_total = counts["workflow_instruction"] + counts["memory_pattern"] + counts["evaluation_pattern"]

    if prompt_total == 0 and integration_total == 0:
        return "unclear"
    if runtime_markers and prompt_total > 0:
        return "mixed"
    if integration_total > prompt_total and len(tooling_surfaces) >= 2:
        return "tool-integration-pack"
    if workflow_total > 0 and counts["workflow_instruction"] >= counts["agent_prompt"]:
        return "workflow-pack"
    if prompt_total > 0:
        return "prompt-library"
    return "unclear"


def _real_vs_packaging(
    artifacts: list[Artifact],
    runtime_markers: list[str],
    tooling_surfaces: list[str],
) -> RealVsPackaging:
    counts = Counter(artifact.kind for artifact in artifacts)
    real_implementation: list[str] = []
    prompt_structure: list[str] = []
    presentation: list[str] = []

    if runtime_markers:
        real_implementation.append(
            f"Runtime-oriented files were detected ({min(len(runtime_markers), 5)} shown): "
            + ", ".join(runtime_markers[:5])
        )

    if counts["integration_manifest"] or counts["tool_contract"]:
        real_implementation.append("The repo contains real packaging/integration logic for multiple AI tool surfaces.")

    if counts["agent_prompt"] or counts["skill_definition"] or counts["rule_file"]:
        prompt_structure.append(
            "Behavior is primarily defined through prompt/rule assets rather than executable runtime code."
        )
    if counts["workflow_instruction"] or counts["memory_pattern"]:
        prompt_structure.append("Workflow, handoff, and memory behavior is largely expressed as instructions in docs/prompts.")
    if tooling_surfaces:
        prompt_structure.append("Behavior is adapted across tool ecosystems via repo-specific prompt packaging.")

    if any(artifact.path.lower().startswith("readme") for artifact in artifacts):
        presentation.append("README-level framing is part of the repo's perceived product story.")
    if any("frontmatter:vibe" in artifact.signals for artifact in artifacts):
        presentation.append("Persona branding is emphasized through frontmatter fields like vibe/personality.")

    return RealVsPackaging(
        real_implementation=real_implementation,
        prompt_config_structure=prompt_structure,
        presentation_marketing_layer=presentation,
    )


def _missing_runtime_pieces(
    repo_archetype: str,
    orchestration_model: str,
    memory_model: str,
    artifacts: list[Artifact],
    runtime_markers: list[str],
) -> list[str]:
    missing: list[str] = []
    artifact_text = " ".join(
        " ".join(artifact.signals).lower() + " " + artifact.summary.lower() for artifact in artifacts
    )

    if orchestration_model == "prompt-defined" and not runtime_markers:
        missing.append("No orchestration engine, scheduler, or agent runtime was detected.")
    if memory_model in {"documented-only", "tool-assisted"} and not runtime_markers:
        missing.append("No built-in persistent state layer was detected in repo code.")
    if any(token in artifact_text for token in ("qa gate", "pass/fail", "quality gate")) and not runtime_markers:
        missing.append("No implemented evaluation loop or enforcement layer was detected.")
    if repo_archetype in {"prompt-library", "workflow-pack"} and "autonomous" in artifact_text and not runtime_markers:
        missing.append("Autonomy appears to be described at the prompt layer rather than implemented as runtime behavior.")

    return sorted(set(missing))


def _verdict(
    repo_archetype: str,
    orchestration_model: str,
    memory_model: str,
    missing_runtime_pieces: list[str],
) -> str:
    if repo_archetype == "unclear":
        return "No major prompt surface was found. This does not look like a prompt-centric agent repo."
    if repo_archetype == "mixed":
        return "This repo mixes real implementation with prompt/config behavior surfaces; it is not prompt-only."
    if missing_runtime_pieces:
        return (
            f"This is best understood as a {repo_archetype} with {orchestration_model} orchestration "
            f"and {memory_model} memory, not a full runtime-implemented agent system."
        )
    return f"This is a {repo_archetype} with meaningful behavior defined by prompts, rules, and tool packaging."


def _xray_call(
    repo_archetype: str,
    orchestration_model: str,
    memory_model: str,
    missing_runtime_pieces: list[str],
) -> str:
    if repo_archetype == "prompt-library" and orchestration_model == "prompt-defined":
        return "Prompt pack, not agent runtime."
    if repo_archetype == "workflow-pack" and missing_runtime_pieces:
        return "Workflow theater without runtime enforcement."
    if repo_archetype == "tool-integration-pack":
        return "Packaging logic around prompt assets."
    if repo_archetype == "mixed" and orchestration_model == "runtime-implemented":
        if memory_model in {"implemented-runtime", "documented-only"}:
            return "Real runtime with visible prompt layers."
        return "Runtime-first repo with prompt surfaces on top."
    if repo_archetype == "unclear":
        return "Not a prompt-centric repo."
    return "Prompt-centric behavior surface detected."


def analyze_target(target: str, max_file_size_kb: int = 1024, include_snippets: bool = True) -> ScanReport:
    repo_info, repo_path = resolve_target(target)
    candidate_files = discover_candidate_files(repo_path, max_file_size_kb=max_file_size_kb)
    runtime_markers = discover_runtime_markers(repo_path)
    artifacts = _build_artifacts(candidate_files, repo_path, include_snippets=include_snippets)
    tooling_surfaces = _detect_tooling_surfaces(candidate_files, artifacts)
    behavior_sources = _behavior_sources(artifacts)
    orchestration_model = _orchestration_model(artifacts, runtime_markers)
    memory_model = _memory_model(artifacts, runtime_markers)
    repo_archetype = _repo_archetype(artifacts, runtime_markers, tooling_surfaces)
    real_vs_packaging = _real_vs_packaging(artifacts, runtime_markers, tooling_surfaces)
    missing_runtime_pieces = _missing_runtime_pieces(
        repo_archetype,
        orchestration_model,
        memory_model,
        artifacts,
        runtime_markers,
    )
    verdict = _verdict(repo_archetype, orchestration_model, memory_model, missing_runtime_pieces)

    return ScanReport(
        repo=repo_info,
        summary=Summary(
            repo_archetype=repo_archetype,
            orchestration_model=orchestration_model,
            memory_model=memory_model,
            xray_call=_xray_call(
                repo_archetype,
                orchestration_model,
                memory_model,
                missing_runtime_pieces,
            ),
            verdict=verdict,
        ),
        counts=Counts(candidate_files=len(candidate_files), artifacts=len(artifacts)),
        tooling_surfaces=tooling_surfaces,
        behavior_sources=behavior_sources,
        missing_runtime_pieces=missing_runtime_pieces,
        real_vs_packaging=real_vs_packaging,
        artifacts=artifacts,
    )
