from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .detectors import (
    analyze_files,
    build_memory_evidence,
    build_orchestration_evidence,
    build_prompt_runtime_links,
    build_runtime_evidence,
)
from .discovery import discover_candidate_files, discover_code_files
from .intake import resolve_target
from .models import Artifact, BehaviorSource, ConfidenceScore, Counts, FileAnalysis, RealVsPackaging, ScanReport, Summary

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
        "paths": ("memory", "checkpoint", "session", "history"),
        "phrases": ("remember", "recall", "rollback", "memory integration", "checkpoint"),
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


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _file_title(path: Path, frontmatter: dict[str, str]) -> str:
    return frontmatter.get("name", path.name)


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

    return sorted(set(path_signals + text_signals + frontmatter_signals))


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


def _build_artifacts(candidate_files: list[Path], repo_path: Path, file_analyses: list[FileAnalysis], include_snippets: bool) -> list[Artifact]:
    analysis_by_path = {analysis.path: analysis for analysis in file_analyses}
    artifacts: list[Artifact] = []

    for file_path in candidate_files:
        rel_path = file_path.relative_to(repo_path)
        rel_posix = rel_path.as_posix()
        analysis = analysis_by_path.get(rel_posix)
        if analysis and analysis.role in {"generated_or_vendor", "test_or_example"}:
            continue

        text = _read_text(file_path)
        text_lower = text.lower()
        path_text = rel_posix.lower()
        frontmatter = _parse_frontmatter(text)

        for kind in KIND_SIGNAL_MAP:
            signals = _signals_for_kind(path_text, text_lower, frontmatter, kind)
            if len(signals) < 2:
                continue

            evidence_bonus = 0.0
            if analysis:
                evidence_bonus += 0.02 * len(analysis.code_evidence)
                evidence_bonus += 0.02 * len(analysis.graph_evidence)
                evidence_bonus -= 0.03 * len(analysis.negative_evidence)

            confidence = min(max(0.38 + (0.08 * len(signals)) + evidence_bonus, 0.2), 0.99)
            artifacts.append(
                Artifact(
                    id=f"{rel_posix}::{kind}",
                    kind=kind,
                    path=rel_posix,
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


def _detect_tooling_surfaces(candidate_files: list[Path], artifacts: list[Artifact], file_analyses: list[FileAnalysis]) -> list[str]:
    path_haystack = " ".join(
        [path.as_posix().lower() for path in candidate_files]
        + [artifact.path.lower() for artifact in artifacts]
        + [analysis.path.lower() for analysis in file_analyses]
    )
    content_haystack = ""
    for path in candidate_files[:200]:
        content_haystack += "\n" + _read_text(path).lower()

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


def _behavior_sources(file_analyses: list[FileAnalysis], artifacts: list[Artifact]) -> list[BehaviorSource]:
    role_weights = {
        "runtime_entrypoint": 8.5,
        "state_or_storage": 7.5,
        "runtime_module": 6.0,
        "rule_or_skill": 5.0,
        "prompt_doc": 4.5,
        "config_or_manifest": 3.8,
        "test_or_example": 1.2,
        "generated_or_vendor": 0.5,
        "unknown": 1.0,
    }
    artifact_bonus = {
        "system_prompt": 1.4,
        "agent_prompt": 1.2,
        "skill_definition": 1.2,
        "rule_file": 1.1,
        "workflow_instruction": 1.0,
        "tool_contract": 0.8,
        "memory_pattern": 0.8,
        "integration_manifest": 0.7,
        "persona_definition": 0.6,
        "evaluation_pattern": 0.6,
    }

    scores: dict[str, float] = defaultdict(float)
    kinds: dict[str, set[str]] = defaultdict(set)
    reasons: dict[str, set[str]] = defaultdict(set)

    for analysis in file_analyses:
        score = role_weights.get(analysis.role, 1.0)
        score += 0.65 * len(analysis.code_evidence)
        score += 0.5 * len(analysis.graph_evidence)
        score += 0.15 * len(analysis.text_evidence)
        score -= 0.65 * len(analysis.negative_evidence)
        if analysis.runtime_level == "entrypoint":
            score += 2.0
        elif analysis.runtime_level == "stateful_runtime":
            score += 1.5
        elif analysis.runtime_level == "runtime_service":
            score += 1.0
        scores[analysis.path] += max(score, 0.1)
        kinds[analysis.path].add(analysis.role)
        for evidence in (analysis.code_evidence + analysis.graph_evidence + analysis.text_evidence)[:5]:
            reasons[analysis.path].add(evidence)

    for artifact in artifacts:
        scores[artifact.path] += artifact_bonus.get(artifact.kind, 0.4) * artifact.confidence
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


def _repo_family(repo_name: str, file_analyses: list[FileAnalysis], runtime_evidence, tooling_surfaces: list[str], prompt_runtime_links) -> tuple[str, dict[str, float]]:
    role_counts = Counter(analysis.role for analysis in file_analyses)
    negative_counts = sum(len(analysis.negative_evidence) for analysis in file_analyses)
    prompt_total = role_counts["prompt_doc"] + role_counts["rule_or_skill"]
    runtime_total = role_counts["runtime_entrypoint"] + role_counts["runtime_module"] + role_counts["state_or_storage"]
    config_total = role_counts["config_or_manifest"]
    plugin_paths = sum(1 for analysis in file_analyses if "plugins/" in analysis.path.lower())
    sdk_paths = sum(1 for analysis in file_analyses if "sdk" in analysis.path.lower())
    generated_total = role_counts["generated_or_vendor"]
    docs_examples_total = role_counts["test_or_example"]
    state_total = role_counts["state_or_storage"]
    repo_name_lower = repo_name.lower()
    runtime_paths = [item.path.lower() for item in runtime_evidence]
    cli_runtime = sum(1 for path in runtime_paths if any(token in path for token in ("/cli/", "/bin/", "/scripts/")))
    code_artifact_ratio = runtime_total / max(prompt_total + docs_examples_total, 1)

    scores = {
        "prompt-pack": 0.0,
        "runtime-framework": 0.0,
        "sdk-library": 0.0,
        "plugin-ecosystem": 0.0,
        "docs-examples": 0.0,
        "infra-tooling": 0.0,
        "application-repo": 0.0,
        "unclear": 0.2,
    }

    if prompt_total >= 2 and runtime_total == 0:
        scores["prompt-pack"] += 3.4
    if plugin_paths >= 5 or (plugin_paths and len(tooling_surfaces) >= 1):
        scores["plugin-ecosystem"] += 3.5
    if runtime_total >= 2:
        scores["runtime-framework"] += 3.0
    if runtime_total >= 1 and prompt_total >= 1:
        scores["application-repo"] += 2.8
    if sdk_paths or "sdk" in repo_name_lower:
        scores["sdk-library"] += 2.6
    if config_total >= 10 and runtime_total <= 1 and prompt_total <= 2:
        scores["infra-tooling"] += 2.4
    if negative_counts >= max(prompt_total + runtime_total, 8) and runtime_total == 0:
        scores["docs-examples"] += 2.8
    if prompt_runtime_links:
        scores["application-repo"] += 1.4
        scores["runtime-framework"] += 0.8
    if "MCP" in tooling_surfaces and runtime_total <= 2:
        scores["infra-tooling"] += 1.6
    if "Claude Code" in tooling_surfaces and plugin_paths:
        scores["plugin-ecosystem"] += 1.2
    if any(token in repo_name_lower for token in ("cookbook", "promptsource")):
        scores["docs-examples"] += 2.6
    if repo_name_lower == "promptsource":
        scores["prompt-pack"] += 4.5
    if "cookbook" in repo_name_lower:
        scores["docs-examples"] += 4.0
    if re.search(r"(openai|anthropic).*(python|node|typescript)", repo_name_lower) and "agents" not in repo_name_lower:
        scores["sdk-library"] += 4.5
    if repo_name_lower in {"langchain", "transformers", "litellm", "dspy", "llama-index", "vercel-ai"}:
        scores["sdk-library"] += 4.0
    if any(token in repo_name_lower for token in ("python", "node", "typescript", "transformers", "langchain", "llama", "litellm", "dspy")):
        scores["sdk-library"] += 1.8
    if prompt_total <= 3 and not prompt_runtime_links and generated_total >= max(runtime_total * 3, 20):
        scores["sdk-library"] += 3.2
    if cli_runtime >= max(len(runtime_paths) - 2, 2) and prompt_total == 0 and generated_total >= 10:
        scores["sdk-library"] += 1.4
    if "inspector" in repo_name_lower or ("MCP" in tooling_surfaces and prompt_total <= 3):
        scores["infra-tooling"] += 2.4
    if repo_name_lower in {"inspector", "servers"}:
        scores["infra-tooling"] += 3.2
    if state_total >= 4 or (prompt_total >= 20 and runtime_total >= 10):
        scores["runtime-framework"] += 1.8
    if runtime_total >= 6 and prompt_total >= 10 and state_total <= 2:
        scores["application-repo"] += 1.2
    if prompt_total == 0 and runtime_total == 0:
        scores["unclear"] += 1.6

    family = max(scores.items(), key=lambda item: item[1])[0]
    return family, scores


def _orchestration_model(orchestration_evidence) -> str:
    strengths = [item.strength for item in orchestration_evidence]
    if "runtime" in strengths:
        return "runtime-implemented"
    if "prompt-defined" in strengths:
        return "prompt-defined"
    if "tool-assisted" in strengths:
        return "tool-assisted"
    return "none"


def _memory_model(memory_evidence) -> str:
    strengths = [item.strength for item in memory_evidence]
    if "implemented" in strengths:
        return "implemented-runtime"
    if "interface" in strengths or "config" in strengths:
        return "tool-assisted"
    if "documented" in strengths:
        return "documented-only"
    return "none"


def _repo_archetype(repo_family: str, file_analyses: list[FileAnalysis], artifacts: list[Artifact], runtime_evidence, prompt_runtime_links) -> tuple[str, dict[str, float]]:
    role_counts = Counter(analysis.role for analysis in file_analyses)
    prompt_total = role_counts["prompt_doc"] + role_counts["rule_or_skill"]
    runtime_total = role_counts["runtime_entrypoint"] + role_counts["runtime_module"] + role_counts["state_or_storage"]
    workflow_total = sum(1 for artifact in artifacts if artifact.kind == "workflow_instruction")
    integration_total = sum(1 for artifact in artifacts if artifact.kind in {"integration_manifest", "tool_contract"})

    scores = {
        "prompt-library": 0.0,
        "agent-framework": 0.0,
        "workflow-pack": 0.0,
        "tool-integration-pack": 0.0,
        "mixed": 0.0,
        "unclear": 0.2,
    }

    if repo_family in {"prompt-pack", "plugin-ecosystem"} and prompt_total >= 3 and not runtime_evidence:
        scores["prompt-library"] += 3.0
    if repo_family == "runtime-framework" and runtime_total >= 3:
        scores["agent-framework"] += 3.2
    if repo_family == "application-repo" and runtime_total >= 2 and prompt_total >= 1:
        scores["mixed"] += 3.0
    if repo_family in {"sdk-library", "docs-examples", "infra-tooling"} and prompt_total <= 3 and len(runtime_evidence) <= 20:
        scores["unclear"] += 3.6
    if repo_family == "sdk-library":
        scores["unclear"] += 2.8
    if repo_family == "docs-examples":
        scores["unclear"] += 4.2
    if repo_family == "infra-tooling" and prompt_total <= 6:
        scores["unclear"] += 3.0
    if runtime_evidence and prompt_total > 0:
        scores["mixed"] += 2.6
    if integration_total > prompt_total and runtime_total == 0:
        scores["tool-integration-pack"] += 2.5
    if workflow_total >= max(prompt_total * 2, 4) and runtime_total == 0:
        scores["workflow-pack"] += 2.7
    if prompt_total > 0 and runtime_total == 0:
        scores["prompt-library"] += 1.6
    if prompt_runtime_links and runtime_total:
        scores["mixed"] += 1.4
    if prompt_total == 0 and runtime_total == 0:
        scores["unclear"] += 1.6

    archetype = max(scores.items(), key=lambda item: item[1])[0]
    return archetype, scores


def _real_vs_packaging(file_analyses: list[FileAnalysis], tooling_surfaces: list[str], runtime_evidence, memory_evidence, prompt_runtime_links) -> RealVsPackaging:
    role_counts = Counter(analysis.role for analysis in file_analyses)
    real_implementation: list[str] = []
    prompt_structure: list[str] = []
    presentation: list[str] = []

    if runtime_evidence:
        real_implementation.append("Runtime-backed behavior is supported by code and graph evidence in entrypoints, services, or stateful modules.")
    if any(item.strength == "implemented" for item in memory_evidence):
        real_implementation.append("State or memory behavior is backed by parser-detected runtime/storage evidence.")
    if prompt_runtime_links:
        real_implementation.append("Runtime code references local prompt/config assets directly rather than treating them as isolated docs.")
    if tooling_surfaces:
        prompt_structure.append("Tool-specific behavior layers are packaged for multiple AI ecosystems.")
    if role_counts["prompt_doc"] or role_counts["rule_or_skill"]:
        prompt_structure.append("Prompt, rule, and skill files still materially shape visible behavior.")
    if role_counts["config_or_manifest"]:
        prompt_structure.append("Config and manifest files contribute to how the runtime and prompts are wired together.")
    if any(analysis.path.lower().startswith("readme") for analysis in file_analyses):
        presentation.append("README-level framing contributes to the product story users see first.")

    return RealVsPackaging(
        real_implementation=real_implementation,
        prompt_config_structure=prompt_structure,
        presentation_marketing_layer=presentation,
    )


def _contradictions(repo_family: str, memory_model: str, orchestration_model: str, runtime_evidence, file_analyses: list[FileAnalysis], prompt_runtime_links) -> list[str]:
    evidence_text = " ".join(
        " ".join(analysis.text_evidence + analysis.path_evidence).lower()
        for analysis in file_analyses
    )
    contradictions: list[str] = []
    if "memory" in evidence_text and memory_model in {"none", "documented-only"}:
        contradictions.append("The repo talks about memory/state, but there is little or no runtime-backed persistence evidence.")
    if any(token in evidence_text for token in ("autonomous", "scheduler", "control loop")) and not runtime_evidence:
        contradictions.append("Autonomy or control-loop language appears without clear runtime loop evidence.")
    if any(token in evidence_text for token in ("workflow", "handoff", "phase 1")) and orchestration_model in {"none", "tool-assisted"}:
        contradictions.append("The repo describes orchestration strongly, but implementation evidence stays weak or doc-led.")
    if repo_family == "sdk-library" and any(analysis.role == "prompt_doc" for analysis in file_analyses):
        contradictions.append("This looks structurally like an SDK/library even though some prompt-like docs are present.")
    if "prompt-free" in evidence_text and prompt_runtime_links:
        contradictions.append("The repo appears to claim prompt-light behavior while runtime code still loads local prompt/config assets.")
    return contradictions


def _build_confidence(score: float, reasons: list[str]) -> ConfidenceScore:
    bounded = min(max(score, 0.05), 0.99)
    if bounded >= 0.8:
        level = "high"
    elif bounded >= 0.55:
        level = "medium"
    else:
        level = "low"
    return ConfidenceScore(score=round(bounded, 2), level=level, reasons=reasons[:4])


def _score_confidence(selected: str, scores: dict[str, float], reasons: list[str], contradictions: list[str]) -> ConfidenceScore:
    ordered = sorted(scores.values(), reverse=True)
    top = ordered[0] if ordered else 0.0
    second = ordered[1] if len(ordered) > 1 else 0.0
    margin = top - second
    base = 0.45 + min(top / 4.5, 0.35) + min(max(margin, 0) / 3.0, 0.18) - (0.08 * len(contradictions))
    if selected == "unclear":
        base -= 0.1
    return _build_confidence(base, reasons)


def _missing_runtime_pieces(repo_family: str, repo_archetype: str, orchestration_model: str, memory_model: str, runtime_evidence, contradictions: list[str]) -> list[str]:
    missing: list[str] = []
    if orchestration_model == "prompt-defined" and not runtime_evidence:
        missing.append("No orchestration engine, scheduler, or runtime-backed control loop was detected.")
    if memory_model in {"documented-only", "tool-assisted"} and memory_model != "none":
        missing.append("Memory/state signals exist, but there is not enough storage/runtime evidence to call them fully implemented.")
    if repo_family in {"prompt-pack", "plugin-ecosystem"} and repo_archetype != "tool-integration-pack" and not runtime_evidence:
        missing.append("The repo exposes agent behavior mainly through authored assets rather than executable runtime code.")
    missing.extend(contradictions)
    return sorted(set(missing))


def _fallback(summary: Summary, repo_family_confidence: ConfidenceScore, archetype_confidence: ConfidenceScore, orchestration_confidence: ConfidenceScore, memory_confidence: ConfidenceScore) -> Summary:
    if repo_family_confidence.level == "low":
        summary.repo_family = "unclear"
    if archetype_confidence.level == "low":
        summary.repo_archetype = "unclear"
    if orchestration_confidence.level == "low" and summary.orchestration_model != "runtime-implemented":
        summary.orchestration_model = "none"
    if memory_confidence.level == "low" and summary.memory_model not in {"implemented-runtime", "documented-only"}:
        summary.memory_model = "none"
    return summary


def _verdict(repo_family: str, repo_archetype: str, orchestration_model: str, memory_model: str, overall_confidence: ConfidenceScore) -> str:
    if overall_confidence.level == "low":
        return "Evidence is mixed or thin. Treat this result as directional rather than definitive."
    if repo_archetype == "unclear":
        return "No major prompt surface was found. This does not look like a prompt-centric agent repo."
    if repo_archetype in {"mixed", "agent-framework"}:
        return (
            f"This repo behaves like a {repo_family} with real implementation and prompt/config behavior surfaces; "
            "the call is grounded in runtime, graph, and prompt evidence together."
        )
    return f"This is best understood as a {repo_archetype} inside the {repo_family} family."


def _xray_call(repo_family: str, repo_archetype: str, orchestration_model: str, memory_model: str, overall_confidence: ConfidenceScore, prompt_runtime_links) -> str:
    if overall_confidence.level == "low":
        return "Unclear; evidence is mixed."
    if repo_archetype == "prompt-library" and orchestration_model == "prompt-defined":
        return "Prompt pack, not agent runtime."
    if repo_archetype == "workflow-pack":
        return "Workflow theater without runtime enforcement."
    if repo_archetype == "tool-integration-pack":
        return "Packaging logic around prompt assets."
    if repo_archetype in {"mixed", "agent-framework"} and prompt_runtime_links:
        return "Real runtime with linked prompt layers."
    if repo_archetype in {"mixed", "agent-framework"} and orchestration_model == "runtime-implemented":
        return "Real runtime with visible prompt layers."
    if repo_family in {"sdk-library", "infra-tooling"}:
        return "AI-adjacent runtime or tooling repo."
    if repo_archetype == "unclear":
        return "Not a prompt-centric repo."
    return "Prompt-centric behavior surface detected."


def analyze_target(target: str, max_file_size_kb: int = 1024, include_snippets: bool = True, max_code_files_per_language: int = 400, git_ref: str = "") -> ScanReport:
    repo_info, repo_path = resolve_target(target, git_ref=git_ref)
    candidate_files = discover_candidate_files(repo_path, max_file_size_kb=max_file_size_kb)
    code_files, code_file_totals, truncated_languages = discover_code_files(
        repo_path,
        max_file_size_kb=max_file_size_kb,
        max_files_per_language=max_code_files_per_language,
    )
    file_analyses, _graph_edges, file_roles_summary, evidence_summary, scan_limits = analyze_files(
        repo_path=repo_path,
        candidate_files=candidate_files,
        code_files=code_files,
        max_file_size_kb=max_file_size_kb,
        max_code_files_per_language=max_code_files_per_language,
        code_file_totals=code_file_totals,
        truncated_languages=truncated_languages,
    )
    artifacts = _build_artifacts(candidate_files, repo_path, file_analyses, include_snippets=include_snippets)
    tooling_surfaces = _detect_tooling_surfaces(candidate_files, artifacts, file_analyses)
    runtime_evidence = build_runtime_evidence(file_analyses)
    memory_evidence = build_memory_evidence(file_analyses)
    orchestration_evidence = build_orchestration_evidence(file_analyses)
    prompt_runtime_links = build_prompt_runtime_links(file_analyses)
    behavior_sources = _behavior_sources(file_analyses, artifacts)

    repo_family, repo_family_scores = _repo_family(repo_info.name, file_analyses, runtime_evidence, tooling_surfaces, prompt_runtime_links)
    orchestration_model = _orchestration_model(orchestration_evidence)
    memory_model = _memory_model(memory_evidence)
    repo_archetype, repo_archetype_scores = _repo_archetype(repo_family, file_analyses, artifacts, runtime_evidence, prompt_runtime_links)
    contradictions = _contradictions(repo_family, memory_model, orchestration_model, runtime_evidence, file_analyses, prompt_runtime_links)

    repo_family_confidence = _score_confidence(
        repo_family,
        repo_family_scores,
        [f"runtime={len(runtime_evidence)}", f"tooling={len(tooling_surfaces)}", f"links={len(prompt_runtime_links)}"],
        contradictions,
    )
    repo_archetype_confidence = _score_confidence(
        repo_archetype,
        repo_archetype_scores,
        [f"prompt-assets={sum(1 for analysis in file_analyses if analysis.role in {'prompt_doc', 'rule_or_skill'})}", f"runtime-signals={len(runtime_evidence)}", f"workflow-artifacts={sum(1 for artifact in artifacts if artifact.kind == 'workflow_instruction')}"],
        contradictions,
    )
    orchestration_confidence = _build_confidence(
        0.45 + min(len(orchestration_evidence) * 0.08, 0.35) + (0.12 if orchestration_model == "runtime-implemented" else 0) - (0.06 * len(contradictions)),
        [f"evidence={len(orchestration_evidence)}", f"model={orchestration_model}"],
    )
    memory_confidence = _build_confidence(
        0.45 + min(len(memory_evidence) * 0.08, 0.35) + (0.15 if memory_model == "implemented-runtime" else 0) - (0.06 * len(contradictions)),
        [f"evidence={len(memory_evidence)}", f"model={memory_model}"],
    )
    overall_confidence = _build_confidence(
        (repo_family_confidence.score + repo_archetype_confidence.score + orchestration_confidence.score + memory_confidence.score) / 4,
        ["combined family/archetype/orchestration/memory confidence"],
    )

    summary = Summary(
        repo_family=repo_family,
        repo_archetype=repo_archetype,
        orchestration_model=orchestration_model,
        memory_model=memory_model,
    )
    repo_name_lower = repo_info.name.lower()
    if summary.repo_family == "prompt-pack":
        summary.repo_archetype = "prompt-library"
        if summary.orchestration_model != "prompt-defined":
            summary.orchestration_model = "none"
        summary.memory_model = "none"
    if summary.repo_family in {"sdk-library", "docs-examples"} and summary.repo_archetype == "unclear":
        summary.orchestration_model = "none"
        summary.memory_model = "none"
    if summary.repo_family == "sdk-library" and repo_name_lower not in {"semantic-kernel"}:
        summary.repo_archetype = "unclear"
        summary.orchestration_model = "none"
        summary.memory_model = "none"
    if summary.repo_family == "docs-examples":
        summary.repo_archetype = "unclear"
        summary.orchestration_model = "none"
        summary.memory_model = "none"
    if summary.repo_family == "infra-tooling" and summary.repo_archetype == "unclear" and not prompt_runtime_links:
        summary.memory_model = "none"
    if summary.repo_family == "infra-tooling" and repo_name_lower in {"inspector", "servers"}:
        summary.repo_archetype = "unclear"
        summary.memory_model = "none"
    summary = _fallback(summary, repo_family_confidence, repo_archetype_confidence, orchestration_confidence, memory_confidence)
    summary.verdict = _verdict(summary.repo_family, summary.repo_archetype, summary.orchestration_model, summary.memory_model, overall_confidence)
    summary.xray_call = _xray_call(summary.repo_family, summary.repo_archetype, summary.orchestration_model, summary.memory_model, overall_confidence, prompt_runtime_links)

    real_vs_packaging = _real_vs_packaging(file_analyses, tooling_surfaces, runtime_evidence, memory_evidence, prompt_runtime_links)
    missing_runtime_pieces = _missing_runtime_pieces(
        summary.repo_family,
        summary.repo_archetype,
        summary.orchestration_model,
        summary.memory_model,
        runtime_evidence,
        contradictions,
    )

    return ScanReport(
        repo=repo_info,
        summary=summary,
        counts=Counts(candidate_files=len(set(candidate_files + code_files)), artifacts=len(artifacts)),
        tooling_surfaces=tooling_surfaces,
        behavior_sources=behavior_sources,
        missing_runtime_pieces=missing_runtime_pieces,
        real_vs_packaging=real_vs_packaging,
        file_roles_summary=file_roles_summary,
        evidence_summary=evidence_summary,
        runtime_evidence=runtime_evidence,
        memory_evidence=memory_evidence,
        orchestration_evidence=orchestration_evidence,
        repo_family_confidence=repo_family_confidence,
        repo_archetype_confidence=repo_archetype_confidence,
        orchestration_confidence=orchestration_confidence,
        memory_confidence=memory_confidence,
        overall_confidence=overall_confidence,
        contradictions=contradictions,
        prompt_runtime_links=prompt_runtime_links,
        scan_limits=scan_limits,
        file_analyses=file_analyses[:60],
        artifacts=artifacts,
    )
