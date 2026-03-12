from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .models import (
    ConstraintAdjustment,
    ContradictionItem,
    DecisionTraceStep,
    ProvenanceSummary,
    Summary,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib


def _marker_hits(values: list[str], markers: tuple[str, ...]) -> int:
    haystack = " ".join(value.lower() for value in values if value)
    return sum(1 for marker in markers if marker in haystack)


def manifest_profile(repo_path: Path) -> dict[str, int]:
    profile = {
        "sdk_markers": 0,
        "plugin_markers": 0,
        "docs_markers": 0,
        "app_markers": 0,
        "cli_markers": 0,
        "workspace_markers": 0,
        "library_exports": 0,
    }
    texts: list[str] = []

    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        texts.extend(
            [
                str(payload.get("name", "")),
                str(payload.get("description", "")),
                " ".join(payload.get("keywords", []) or []),
            ]
        )
        scripts = payload.get("scripts", {}) or {}
        profile["app_markers"] += sum(1 for key in scripts if key in {"dev", "start", "serve", "preview"})
        profile["cli_markers"] += 1 if payload.get("bin") else 0
        profile["workspace_markers"] += 1 if payload.get("workspaces") else 0
        exports = payload.get("exports")
        if isinstance(exports, dict):
            profile["library_exports"] += len(exports)

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            payload = {}
        project = payload.get("project", {}) or {}
        poetry = payload.get("tool", {}).get("poetry", {}) if isinstance(payload.get("tool"), dict) else {}
        texts.extend(
            [
                str(project.get("name", "")),
                str(project.get("description", "")),
                " ".join(project.get("keywords", []) or []),
                str(poetry.get("name", "")),
                str(poetry.get("description", "")),
            ]
        )
        scripts = project.get("scripts", {}) or {}
        profile["cli_markers"] += len(scripts)
        profile["workspace_markers"] += 1 if project.get("optional-dependencies") else 0

    cargo_toml = repo_path / "Cargo.toml"
    if cargo_toml.exists():
        try:
            payload = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            payload = {}
        package = payload.get("package", {}) or {}
        texts.extend(
            [
                str(package.get("name", "")),
                str(package.get("description", "")),
                " ".join(package.get("keywords", []) or []),
            ]
        )
        profile["cli_markers"] += 1 if payload.get("bin") else 0

    profile["sdk_markers"] += _marker_hits(texts, ("sdk", "client", "bindings", "library", "api wrapper"))
    profile["plugin_markers"] += _marker_hits(texts, ("plugin", "extension", "plugin system", "integrations"))
    profile["docs_markers"] += _marker_hits(texts, ("cookbook", "example", "tutorial", "guide", "docs"))
    profile["app_markers"] += _marker_hits(texts, ("assistant", "agent", "platform", "runtime", "server"))
    return profile


def provenance_summary(file_analyses, artifacts, evidence_summary, runtime_evidence, prompt_runtime_links):
    role_counts = Counter(analysis.role for analysis in file_analyses)
    docs_evidence = role_counts["prompt_doc"] + sum(
        1 for analysis in file_analyses if any(item == "negative:readme" for item in analysis.negative_evidence)
    )
    config_evidence = role_counts["config_or_manifest"]
    prompt_asset_evidence = role_counts["prompt_doc"] + role_counts["rule_or_skill"] + len(artifacts)
    runtime_code_evidence = (
        (role_counts["runtime_entrypoint"] * 3)
        + (role_counts["state_or_storage"] * 3)
        + (role_counts["runtime_module"] * 2)
        + len(runtime_evidence)
    )
    graph_total = evidence_summary.graph_evidence
    negative_total = evidence_summary.negative_evidence
    docs_dominance_ratio = round((docs_evidence + config_evidence) / max(runtime_code_evidence, 1), 2)

    total_files = max(len(file_analyses), 1)
    metrics = {
        "runtime_density": round((runtime_code_evidence + (graph_total * 0.5)) / total_files, 2),
        "prompt_density": round((prompt_asset_evidence + (docs_evidence * 0.5)) / total_files, 2),
        "linkage_density": round(len(prompt_runtime_links) / max(len(runtime_evidence), 1), 2),
        "entrypoint_reachability": round(
            sum(
                1
                for analysis in file_analyses
                if analysis.runtime_level in {"entrypoint", "runtime_service"} and analysis.graph_evidence
            )
            / max(
                sum(
                    1
                    for analysis in file_analyses
                    if analysis.runtime_level in {"entrypoint", "runtime_service"}
                ),
                1,
            ),
            2,
        ),
    }

    return (
        ProvenanceSummary(
            docs_evidence=docs_evidence,
            config_evidence=config_evidence,
            prompt_asset_evidence=prompt_asset_evidence,
            runtime_code_evidence=runtime_code_evidence,
            graph_evidence=graph_total,
            negative_evidence=negative_total,
            docs_dominance_ratio=docs_dominance_ratio,
        ),
        metrics,
    )


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


def repo_family(file_analyses, tooling_surfaces, prompt_runtime_links, provenance, metrics, manifest):
    role_counts = Counter(analysis.role for analysis in file_analyses)
    runtime_total = role_counts["runtime_entrypoint"] + role_counts["runtime_module"] + role_counts["state_or_storage"]
    prompt_total = role_counts["prompt_doc"] + role_counts["rule_or_skill"]
    plugin_paths = sum(1 for analysis in file_analyses if "plugins/" in analysis.path.lower())
    docs_examples_total = role_counts["test_or_example"]

    scores = {key: 0.2 for key in ("prompt-pack", "runtime-framework", "sdk-library", "plugin-ecosystem", "docs-examples", "infra-tooling", "application-repo")}
    scores["unclear"] = 0.4

    if prompt_total >= 2 and runtime_total == 0:
        scores["prompt-pack"] += 4.0
    if manifest["docs_markers"] >= 2 and runtime_total <= 1 and prompt_total <= 1:
        scores["docs-examples"] += 3.2
    if provenance.docs_dominance_ratio >= 2.0 and runtime_total <= 1 and prompt_total <= 1:
        scores["docs-examples"] += 2.6
    if runtime_total >= 3 and provenance.runtime_code_evidence >= 8:
        scores["runtime-framework"] += 3.4
    if runtime_total >= 1 and prompt_total >= 1:
        scores["application-repo"] += 2.8
    if manifest["sdk_markers"] >= 2 and metrics["linkage_density"] == 0:
        scores["sdk-library"] += 3.0
    if manifest["plugin_markers"] >= 1 or plugin_paths >= 3:
        scores["plugin-ecosystem"] += 3.0
    if manifest["workspace_markers"] >= 1 and plugin_paths >= 1:
        scores["plugin-ecosystem"] += 1.2
    if "MCP" in tooling_surfaces and runtime_total <= 2:
        scores["infra-tooling"] += 2.2
    if provenance.config_evidence >= 10 and runtime_total <= 2 and prompt_total <= 3:
        scores["infra-tooling"] += 2.2
    if prompt_runtime_links:
        scores["application-repo"] += 1.5
        scores["runtime-framework"] += 1.0
    if manifest["app_markers"] >= 2 and runtime_total >= 2:
        scores["runtime-framework"] += 1.6
    if manifest["cli_markers"] >= 1 and manifest["sdk_markers"] >= 1 and prompt_total <= 2:
        scores["sdk-library"] += 1.2
    if docs_examples_total >= max(runtime_total * 2, 8) and runtime_total <= 1 and prompt_total <= 1:
        scores["docs-examples"] += 1.5
    if prompt_total == 0 and runtime_total == 0:
        scores["unclear"] += 2.0

    family = max(scores.items(), key=lambda item: item[1])[0]
    trace = DecisionTraceStep(
        stage="repo-family",
        label=family,
        basis="structural-evidence",
        reason=(
            f"runtime={runtime_total}, prompt={prompt_total}, docs-ratio={provenance.docs_dominance_ratio}, "
            f"links={len(prompt_runtime_links)}, manifest-sdk={manifest['sdk_markers']}, manifest-plugin={manifest['plugin_markers']}"
        ),
    )
    return family, scores, trace


def repo_archetype(repo_family_value, file_analyses, artifacts, runtime_evidence, prompt_runtime_links, provenance, metrics):
    role_counts = Counter(analysis.role for analysis in file_analyses)
    prompt_total = role_counts["prompt_doc"] + role_counts["rule_or_skill"]
    runtime_total = role_counts["runtime_entrypoint"] + role_counts["runtime_module"] + role_counts["state_or_storage"]
    workflow_total = sum(1 for artifact in artifacts if artifact.kind == "workflow_instruction")
    integration_total = sum(1 for artifact in artifacts if artifact.kind in {"integration_manifest", "tool_contract"})

    scores = {key: 0.2 for key in ("prompt-library", "agent-framework", "workflow-pack", "tool-integration-pack", "mixed")}
    scores["unclear"] = 0.4

    if prompt_total > 0 and runtime_total == 0:
        scores["prompt-library"] += 2.2
    if repo_family_value == "prompt-pack":
        scores["prompt-library"] += 3.0
    if workflow_total >= max(prompt_total * 2, 4) and runtime_total == 0:
        scores["workflow-pack"] += 2.6
    if integration_total > prompt_total and runtime_total == 0:
        scores["tool-integration-pack"] += 2.4
    if repo_family_value == "runtime-framework" and runtime_total >= 3 and metrics["prompt_density"] >= 0.3:
        scores["agent-framework"] += 3.2
    if runtime_evidence and prompt_total > 0:
        scores["mixed"] += 2.8
    if prompt_runtime_links and runtime_total:
        scores["mixed"] += 1.4
    if repo_family_value in {"sdk-library", "docs-examples", "infra-tooling"}:
        scores["unclear"] += 3.0
    if prompt_total == 0 and runtime_total == 0:
        scores["unclear"] += 1.8
    if provenance.docs_dominance_ratio >= 2.0 and runtime_total <= 1:
        scores["unclear"] += 1.2

    archetype = max(scores.items(), key=lambda item: item[1])[0]
    trace = DecisionTraceStep(
        stage="repo-archetype",
        label=archetype,
        basis="structural-evidence",
        reason=(
            f"runtime={runtime_total}, prompt={prompt_total}, workflow-artifacts={workflow_total}, "
            f"integration-artifacts={integration_total}, prompt-density={metrics['prompt_density']}"
        ),
    )
    return archetype, scores, trace


def _apply_adjustment(summary, field, after, reason, basis, adjustments, decision_trace):
    before = getattr(summary, field)
    if before == after:
        return
    setattr(summary, field, after)
    adjustments.append(ConstraintAdjustment(field=field, before=before, after=after, reason=reason, basis=basis))
    decision_trace.append(DecisionTraceStep(stage="constraint-resolution", label=f"{field}={after}", reason=reason, basis=basis))


def resolve_constraints(provisional_summary, provenance, metrics, runtime_evidence, prompt_runtime_links):
    final_summary = provisional_summary.model_copy(deep=True)
    adjustments: list[ConstraintAdjustment] = []
    decision_trace: list[DecisionTraceStep] = []

    if final_summary.repo_family == "prompt-pack":
        _apply_adjustment(final_summary, "repo_archetype", "prompt-library", "Prompt-dominant repos without runtime backing should resolve to prompt-library.", "family-policy", adjustments, decision_trace)
        if not runtime_evidence and final_summary.orchestration_model != "prompt-defined":
            _apply_adjustment(final_summary, "orchestration_model", "none", "Doc-led prompt packs should not imply executable orchestration.", "family-policy", adjustments, decision_trace)
        _apply_adjustment(final_summary, "memory_model", "none", "Prompt packs may describe memory, but memory is not runtime-backed here.", "family-policy", adjustments, decision_trace)

    if final_summary.repo_family == "sdk-library":
        _apply_adjustment(final_summary, "repo_archetype", "unclear", "SDK-style repositories are library surfaces first, even when docs mention agents or workflows.", "family-policy", adjustments, decision_trace)
        _apply_adjustment(final_summary, "orchestration_model", "none", "Library exports alone do not count as runtime orchestration for the repo itself.", "family-policy", adjustments, decision_trace)
        _apply_adjustment(final_summary, "memory_model", "none", "SDK/runtime helper state is not the same as implemented agent memory.", "family-policy", adjustments, decision_trace)

    if final_summary.repo_family == "docs-examples":
        _apply_adjustment(final_summary, "repo_archetype", "unclear", "Docs/example repositories should not collapse into agent-framework labels without stronger runtime evidence.", "family-policy", adjustments, decision_trace)
        _apply_adjustment(final_summary, "orchestration_model", "none", "Example code and guides do not constitute repo-level orchestration.", "family-policy", adjustments, decision_trace)
        _apply_adjustment(final_summary, "memory_model", "none", "Docs/example memory references are not runtime-backed memory.", "family-policy", adjustments, decision_trace)

    if final_summary.repo_family == "infra-tooling" and metrics["linkage_density"] == 0 and provenance.prompt_asset_evidence <= 6:
        _apply_adjustment(final_summary, "repo_archetype", "unclear", "Infra/tooling repos without prompt/runtime linkage should not be overcalled as prompt-centric systems.", "family-policy", adjustments, decision_trace)
        if final_summary.memory_model != "implemented-runtime":
            _apply_adjustment(final_summary, "memory_model", "none", "Operational state in tooling repos is not enough to call agent memory implemented.", "family-policy", adjustments, decision_trace)

    if final_summary.repo_family in {"sdk-library", "docs-examples"} and final_summary.repo_archetype == "unclear":
        _apply_adjustment(final_summary, "orchestration_model", "none", "Unclear family-constrained repos should not keep doc-led orchestration labels.", "family-policy", adjustments, decision_trace)

    if final_summary.repo_archetype in {"prompt-library", "workflow-pack", "tool-integration-pack"} and runtime_evidence:
        _apply_adjustment(final_summary, "repo_archetype", "mixed", "Runtime evidence and prompt assets coexist, so a pure prompt-pack archetype would be misleading.", "family-policy", adjustments, decision_trace)

    return final_summary, adjustments, decision_trace


def contradictions(provisional_summary, final_summary, provenance, runtime_evidence, prompt_runtime_links, file_analyses, adjustments):
    evidence_text = " ".join(" ".join(analysis.text_evidence + analysis.path_evidence).lower() for analysis in file_analyses)
    items: list[ContradictionItem] = []

    if "memory" in evidence_text and final_summary.memory_model == "none":
        items.append(ContradictionItem(severity="medium", message="The repo talks about memory/state, but runtime-backed persistence evidence remains weak.", basis="docs-overclaim-runtime"))
    if any(token in evidence_text for token in ("autonomous", "scheduler", "control loop")) and not runtime_evidence:
        items.append(ContradictionItem(severity="high", message="Autonomy or control-loop language appears without clear runtime loop evidence.", basis="docs-overclaim-runtime"))
    if any(token in evidence_text for token in ("workflow", "handoff", "phase 1")) and final_summary.orchestration_model == "none":
        items.append(ContradictionItem(severity="medium", message="The repo describes orchestration strongly, but implementation evidence stays doc-led.", basis="docs-overclaim-runtime"))
    if provisional_summary.repo_family != final_summary.repo_family or any(adj.basis == "family-policy" for adj in adjustments):
        items.append(ContradictionItem(severity="low", message="Family policy constrained at least one final label because the structural repo shape outweighed agent-like docs.", basis="family-policy-suppression"))
    if final_summary.memory_model in {"documented-only", "tool-assisted"} and provenance.runtime_code_evidence < 6:
        items.append(ContradictionItem(severity="medium", message="Memory is partially indicated, but the runtime evidence stack is still too weak to call it fully implemented.", basis="weak-runtime-memory"))
    if provenance.prompt_asset_evidence > 0 and not prompt_runtime_links and provenance.runtime_code_evidence >= 6:
        items.append(ContradictionItem(severity="low", message="Prompt-like assets exist, but runtime code does not appear to load them directly.", basis="orphaned-prompt-surface"))

    deduped: list[ContradictionItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.severity, item.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_confidence(score, reasons):
    bounded = min(max(score, 0.05), 0.99)
    if bounded >= 0.8:
        level = "high"
    elif bounded >= 0.55:
        level = "medium"
    else:
        level = "low"
    from .models import ConfidenceScore

    return ConfidenceScore(score=round(bounded, 2), level=level, reasons=reasons[:4])


def _score_margin(scores, selected):
    ordered = sorted(scores.values(), reverse=True)
    top = scores.get(selected, ordered[0] if ordered else 0.0)
    second = ordered[1] if len(ordered) > 1 else 0.0
    return top, max(top - second, 0.0)


def field_confidence(field, final_value, provisional_value, scores, provenance, metrics, adjustments, contradiction_details):
    top, margin = _score_margin(scores or {final_value: 1.0}, final_value)
    policy_adjustments = [item for item in adjustments if item.field == field]
    contradiction_penalty = 0.04 * sum(1 for item in contradiction_details if item.severity in {"medium", "high"})
    base = 0.45 + min(top / 4.0, 0.28) + min(margin / 2.5, 0.18)
    if policy_adjustments:
        base -= 0.12
    if final_value == "unclear":
        base -= 0.08
    if field == "repo_family":
        base += min(metrics["runtime_density"] * 0.05, 0.08)
    elif field == "repo_archetype":
        base += min(metrics["prompt_density"] * 0.04, 0.08)
    elif field == "orchestration_model" and final_value == "runtime-implemented":
        base += 0.1
    elif field == "memory_model" and final_value == "implemented-runtime":
        base += 0.12
    elif field == "memory_model" and final_value == "none" and provenance.docs_dominance_ratio >= 2:
        base += 0.04
    base -= contradiction_penalty

    reasons = [f"final={final_value}"]
    if provisional_value != final_value:
        reasons.append(f"provisional={provisional_value}")
    if policy_adjustments:
        reasons.append(f"constraint={policy_adjustments[-1].basis}:{policy_adjustments[-1].reason}")
    else:
        reasons.append(f"support={round(top, 2)} margin={round(margin, 2)}")
    if field == "repo_family":
        reasons.append(f"runtime-density={metrics['runtime_density']} docs-ratio={provenance.docs_dominance_ratio}")
    elif field == "repo_archetype":
        reasons.append(f"prompt-density={metrics['prompt_density']} links={metrics['linkage_density']}")
    elif field == "orchestration_model":
        reasons.append(f"entrypoint-reachability={metrics['entrypoint_reachability']}")
    elif field == "memory_model":
        reasons.append(f"runtime-code={provenance.runtime_code_evidence} docs-ratio={provenance.docs_dominance_ratio}")
    return _build_confidence(base, reasons)


def apply_confidence_fallbacks(summary, repo_family_confidence, archetype_confidence, orchestration_confidence, memory_confidence, adjustments, decision_trace):
    final_summary = summary.model_copy(deep=True)
    if repo_family_confidence.level == "low":
        _apply_adjustment(final_summary, "repo_family", "unclear", "Repo-family confidence stayed low after structural scoring and policy resolution.", "confidence-fallback", adjustments, decision_trace)
    if archetype_confidence.level == "low":
        _apply_adjustment(final_summary, "repo_archetype", "unclear", "Repo archetype confidence stayed low after structural scoring and policy resolution.", "confidence-fallback", adjustments, decision_trace)
    if orchestration_confidence.level == "low" and final_summary.orchestration_model != "runtime-implemented":
        _apply_adjustment(final_summary, "orchestration_model", "none", "Orchestration confidence stayed low and runtime-backed control loops were not strong enough.", "confidence-fallback", adjustments, decision_trace)
    if memory_confidence.level == "low" and final_summary.memory_model not in {"implemented-runtime", "documented-only"}:
        _apply_adjustment(final_summary, "memory_model", "none", "Memory confidence stayed low and runtime-backed storage evidence was not strong enough.", "confidence-fallback", adjustments, decision_trace)
    return final_summary


def verdict(summary, overall_confidence, adjustments):
    if overall_confidence.level == "low":
        return "Evidence is mixed or thin. Treat this result as directional rather than definitive."
    if summary.repo_archetype == "unclear":
        if any(item.basis == "family-policy" for item in adjustments):
            return "The repo shape is real, but the final call is constrained by family-level structure more than by prompt-centric behavior."
        return "No major prompt surface was found. This does not look like a prompt-centric agent repo."
    if summary.repo_archetype in {"mixed", "agent-framework"}:
        return (
            f"This repo behaves like a {summary.repo_family} with real implementation and prompt/config behavior surfaces; "
            "the call is grounded in runtime, graph, and prompt evidence together."
        )
    return f"This is best understood as a {summary.repo_archetype} inside the {summary.repo_family} family."


def xray_call(summary, overall_confidence, prompt_runtime_links, adjustments):
    if overall_confidence.level == "low":
        return "Unclear; evidence is mixed."
    if summary.repo_archetype == "prompt-library" and summary.orchestration_model == "prompt-defined":
        return "Prompt pack, not agent runtime."
    if summary.repo_archetype == "workflow-pack":
        return "Workflow theater without runtime enforcement."
    if summary.repo_archetype == "tool-integration-pack":
        return "Packaging logic around prompt assets."
    if summary.repo_archetype in {"mixed", "agent-framework"} and prompt_runtime_links:
        return "Real runtime with linked prompt layers."
    if summary.repo_archetype in {"mixed", "agent-framework"} and summary.orchestration_model == "runtime-implemented":
        return "Real runtime with visible prompt layers."
    if summary.repo_family in {"sdk-library", "infra-tooling"}:
        if any(item.basis == "family-policy" for item in adjustments):
            return "AI-adjacent runtime or tooling repo."
        return "Runtime-heavy repo with limited prompt centrality."
    if summary.repo_archetype == "unclear":
        return "Not a prompt-centric repo."
    return "Prompt-centric behavior surface detected."


def missing_runtime_pieces(summary, runtime_evidence, contradiction_details):
    missing: list[str] = []
    if summary.orchestration_model == "prompt-defined" and not runtime_evidence:
        missing.append("No orchestration engine, scheduler, or runtime-backed control loop was detected.")
    if summary.memory_model in {"documented-only", "tool-assisted"}:
        missing.append("Memory/state signals exist, but there is not enough storage/runtime evidence to call them fully implemented.")
    if summary.repo_family in {"prompt-pack", "plugin-ecosystem"} and summary.repo_archetype != "tool-integration-pack" and not runtime_evidence:
        missing.append("The repo exposes behavior mainly through authored assets rather than executable runtime code.")
    missing.extend(item.message for item in contradiction_details)
    return sorted(set(missing))
