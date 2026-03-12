from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .models import Artifact, ConfidenceScore, ScanReport


def _artifact_line(artifact: Artifact) -> str:
    confidence = f"{artifact.confidence:.2f}"
    signals = ", ".join(artifact.signals[:4]) if artifact.signals else "no explicit signals"
    snippet = f" -- {artifact.source_snippet}" if artifact.source_snippet else ""
    return f"- `{artifact.kind}` `{artifact.path}` ({confidence}) [{signals}]{snippet}"


def _evidence_lines(items: list) -> str:
    return "\n".join(
        f"- `{item.path}` `{item.strength}` {item.label} [{', '.join(item.reasons) if item.reasons else 'no reasons'}]"
        for item in items
    ) or "- None detected"


def _confidence_line(label: str, score: ConfidenceScore) -> str:
    reasons = ", ".join(score.reasons) if score.reasons else "no reasons"
    return f"- {label}: `{score.level}` ({score.score:.2f}) [{reasons}]"


def render_markdown(report: ScanReport) -> str:
    tooling = ", ".join(report.tooling_surfaces) if report.tooling_surfaces else "None detected"
    behavior_sources = "\n".join(
        f"- `{source.path}` score={source.score:.2f} kinds={', '.join(source.kinds)}"
        for source in report.behavior_sources
    ) or "- No dominant behavior sources detected"

    prompt_surface = "\n".join(_artifact_line(artifact) for artifact in report.artifacts[:25])
    if not prompt_surface:
        prompt_surface = "- No major prompt surfaces detected"

    inventory = "\n".join(
        f"- `{artifact.path}` -> `{artifact.kind}`"
        for artifact in report.artifacts
    ) or "- No artifacts extracted"

    real_impl = "\n".join(f"- {item}" for item in report.real_vs_packaging.real_implementation) or "- None detected"
    prompt_cfg = (
        "\n".join(f"- {item}" for item in report.real_vs_packaging.prompt_config_structure) or "- None detected"
    )
    presentation = (
        "\n".join(f"- {item}" for item in report.real_vs_packaging.presentation_marketing_layer)
        or "- None detected"
    )
    missing = "\n".join(f"- {item}" for item in report.missing_runtime_pieces) or "- No missing pieces called out"
    file_roles = "\n".join(f"- `{item.role}`: {item.count}" for item in report.file_roles_summary) or "- None detected"
    evidence_summary = (
        f"- path evidence: {report.evidence_summary.path_evidence}\n"
        f"- text evidence: {report.evidence_summary.text_evidence}\n"
        f"- code evidence: {report.evidence_summary.code_evidence}\n"
        f"- graph evidence: {report.evidence_summary.graph_evidence}\n"
        f"- negative evidence: {report.evidence_summary.negative_evidence}"
    )
    confidence_summary = "\n".join(
        [
            _confidence_line("Repo family", report.repo_family_confidence),
            _confidence_line("Repo archetype", report.repo_archetype_confidence),
            _confidence_line("Orchestration", report.orchestration_confidence),
            _confidence_line("Memory", report.memory_confidence),
            _confidence_line("Overall", report.overall_confidence),
        ]
    )
    contradictions = "\n".join(f"- {item}" for item in report.contradictions) or "- None detected"
    contradiction_details = "\n".join(
        f"- `{item.severity}` {item.message} [{item.basis}]"
        for item in report.contradiction_details
    ) or "- None detected"
    prompt_runtime_links = "\n".join(
        f"- `{item.source_path}` -> `{item.target_path}` `{item.kind}` [{', '.join(item.reasons) if item.reasons else 'no reasons'}]"
        for item in report.prompt_runtime_links
    ) or "- No runtime-to-prompt/config links detected"
    scan_limits = (
        f"- candidate files scanned: {report.scan_limits.candidate_files_scanned}\n"
        f"- code files scanned: {report.scan_limits.code_files_scanned}/{report.scan_limits.code_files_total}\n"
        f"- max code files per language: {report.scan_limits.max_code_files_per_language}\n"
        f"- truncated languages: {', '.join(report.scan_limits.truncated_languages) or 'None'}"
    )
    provenance = (
        f"- docs evidence: {report.provenance_summary.docs_evidence}\n"
        f"- config evidence: {report.provenance_summary.config_evidence}\n"
        f"- prompt asset evidence: {report.provenance_summary.prompt_asset_evidence}\n"
        f"- runtime code evidence: {report.provenance_summary.runtime_code_evidence}\n"
        f"- graph evidence: {report.provenance_summary.graph_evidence}\n"
        f"- negative evidence: {report.provenance_summary.negative_evidence}\n"
        f"- docs dominance ratio: {report.provenance_summary.docs_dominance_ratio}"
    )
    adjustments = "\n".join(
        f"- `{item.field}` `{item.before}` -> `{item.after}` [{item.basis}] {item.reason}"
        for item in report.constraint_adjustments
    ) or "- No post-classification adjustments"
    decision_trace = "\n".join(
        f"- `{item.stage}` `{item.label}` [{item.basis or 'n/a'}] {item.reason}"
        for item in report.decision_trace
    ) or "- No decision trace"

    return f"""# Prompt-xray Report: {report.repo.name}

## What This Repo Is

This repo is classified as **{report.summary.repo_archetype}** in the **{report.summary.repo_family}** family.

> {report.summary.xray_call}

{report.summary.verdict}

### Provisional vs final

- Provisional: `{report.provisional_summary.repo_family}` / `{report.provisional_summary.repo_archetype}` / `{report.provisional_summary.orchestration_model}` / `{report.provisional_summary.memory_model}`
- Final: `{report.summary.repo_family}` / `{report.summary.repo_archetype}` / `{report.summary.orchestration_model}` / `{report.summary.memory_model}`

### Constraint adjustments

{adjustments}

## Prompt Surface Map

{prompt_surface}

## Behavior Sources

{behavior_sources}

## Tooling And Integrations

- Tooling surfaces: {tooling}

## Orchestration And Memory

- Orchestration model: `{report.summary.orchestration_model}`
- Memory model: `{report.summary.memory_model}`

### Runtime evidence
{_evidence_lines(report.runtime_evidence)}

### Memory evidence
{_evidence_lines(report.memory_evidence)}

### Orchestration evidence
{_evidence_lines(report.orchestration_evidence)}

### Prompt/runtime linkage
{prompt_runtime_links}

## Real Versus Packaging

### Real implementation
{real_impl}

### Prompt/config structure
{prompt_cfg}

### Presentation/marketing layer
{presentation}

## Missing Pieces

{missing}

## Confidence And Uncertainty

{confidence_summary}

### Claim/implementation mismatches
{contradictions}

### Contradiction severity
{contradiction_details}

## Evidence Summary

### File roles
{file_roles}

### Evidence counts
{evidence_summary}

### Provenance summary
{provenance}

### Scan limits
{scan_limits}

### Decision trace
{decision_trace}

## Artifact Inventory

{inventory}

## Verdict

{report.summary.verdict}
"""


def _html_badge(text: str, tone: str = "neutral") -> str:
    colors = {
        "neutral": "#e5e7eb",
        "accent": "#dbeafe",
        "good": "#dcfce7",
        "warn": "#fef3c7",
        "danger": "#fee2e2",
    }
    color = colors.get(tone, colors["neutral"])
    return (
        f"<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;"
        f"background:{color};font-size:12px;font-weight:700;letter-spacing:0.02em;\">{escape(text)}</span>"
    )


def render_html(report: ScanReport) -> str:
    behavior_rows = "".join(
        "<tr>"
        f"<td><code>{escape(source.path)}</code></td>"
        f"<td>{source.score:.2f}</td>"
        f"<td>{escape(', '.join(source.kinds))}</td>"
        "</tr>"
        for source in report.behavior_sources
    ) or "<tr><td colspan='3'>No dominant behavior sources detected</td></tr>"

    missing_items = "".join(f"<li>{escape(item)}</li>" for item in report.missing_runtime_pieces) or "<li>None</li>"
    prompt_items = "".join(
        "<li>"
        f"<strong>{escape(artifact.kind)}</strong> <code>{escape(artifact.path)}</code>"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(artifact.source_snippet or artifact.summary)}</div>"
        "</li>"
        for artifact in report.artifacts[:15]
    ) or "<li>No major prompt surfaces detected</li>"
    runtime_items = "".join(
        "<li>"
        f"<code>{escape(item.path)}</code> <strong>{escape(item.strength)}</strong> {escape(item.label)}"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(', '.join(item.reasons) or 'No reasons')}</div>"
        "</li>"
        for item in report.runtime_evidence[:6]
    ) or "<li>No runtime evidence detected</li>"
    memory_items = "".join(
        "<li>"
        f"<code>{escape(item.path)}</code> <strong>{escape(item.strength)}</strong> {escape(item.label)}"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(', '.join(item.reasons) or 'No reasons')}</div>"
        "</li>"
        for item in report.memory_evidence[:6]
    ) or "<li>No memory evidence detected</li>"
    orchestration_items = "".join(
        "<li>"
        f"<code>{escape(item.path)}</code> <strong>{escape(item.strength)}</strong> {escape(item.label)}"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(', '.join(item.reasons) or 'No reasons')}</div>"
        "</li>"
        for item in report.orchestration_evidence[:6]
    ) or "<li>No orchestration evidence detected</li>"
    file_roles = "".join(
        f"<li><code>{escape(item.role)}</code> {item.count}</li>"
        for item in report.file_roles_summary[:8]
    ) or "<li>No file roles detected</li>"
    confidence_items = "".join(
        "<li>"
        f"<strong>{escape(label)}</strong> {escape(score.level)} ({score.score:.2f})"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(', '.join(score.reasons) or 'No reasons')}</div>"
        "</li>"
        for label, score in (
            ("Repo family", report.repo_family_confidence),
            ("Repo archetype", report.repo_archetype_confidence),
            ("Orchestration", report.orchestration_confidence),
            ("Memory", report.memory_confidence),
            ("Overall", report.overall_confidence),
        )
    )
    contradiction_items = "".join(
        f"<li>{escape(item)}</li>" for item in report.contradictions
    ) or "<li>No contradictions detected</li>"
    prompt_link_items = "".join(
        "<li>"
        f"<code>{escape(item.source_path)}</code> -> <code>{escape(item.target_path)}</code>"
        f"<div style=\"color:#475569;margin-top:4px;\">{escape(item.kind)} | {escape(', '.join(item.reasons) or 'No reasons')}</div>"
        "</li>"
        for item in report.prompt_runtime_links[:8]
    ) or "<li>No runtime-to-prompt/config links detected</li>"

    tooling = "".join(_html_badge(tool, "accent") for tool in report.tooling_surfaces) or _html_badge("None detected")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prompt-xray Report: {escape(report.repo.name)}</title>
</head>
<body style="margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;">
  <main style="max-width:1100px;margin:0 auto;padding:40px 24px 80px;">
    <section style="background:linear-gradient(135deg,#111827,#1e293b);border:1px solid #334155;border-radius:24px;padding:28px 28px 24px;">
      <div style="margin-bottom:12px;">{_html_badge(report.summary.repo_family, "accent")} {_html_badge(report.summary.repo_archetype, "accent")} {_html_badge(report.summary.orchestration_model, "warn")} {_html_badge(report.summary.memory_model, "neutral")} {_html_badge(report.overall_confidence.level, "good" if report.overall_confidence.level == "high" else "warn" if report.overall_confidence.level == "medium" else "danger")}</div>
      <h1 style="margin:0 0 10px;font-size:40px;line-height:1.1;">Prompt-xray: {escape(report.repo.name)}</h1>
      <p style="margin:0 0 16px;font-size:24px;font-weight:700;color:#f8fafc;">{escape(report.summary.xray_call)}</p>
      <p style="margin:0;color:#cbd5e1;max-width:900px;font-size:16px;line-height:1.6;">{escape(report.summary.verdict)}</p>
    </section>

    <section style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:20px;">
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:18px;"><div style="color:#94a3b8;font-size:12px;">Candidate files</div><div style="font-size:28px;font-weight:800;">{report.counts.candidate_files}</div></div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:18px;"><div style="color:#94a3b8;font-size:12px;">Artifacts</div><div style="font-size:28px;font-weight:800;">{report.counts.artifacts}</div></div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:18px;"><div style="color:#94a3b8;font-size:12px;">Source type</div><div style="font-size:28px;font-weight:800;">{escape(report.repo.source_type)}</div></div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:18px;"><div style="color:#94a3b8;font-size:12px;">Commit</div><div style="font-size:16px;font-weight:700;word-break:break-all;">{escape(report.repo.commit or 'n/a')}</div></div>
    </section>

    <section style="display:grid;grid-template-columns:1.3fr 0.7fr;gap:20px;margin-top:20px;">
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Top behavior sources</h2>
        <table style="width:100%;border-collapse:collapse;">
          <thead><tr style="color:#94a3b8;text-align:left;"><th style="padding:0 0 12px;">Path</th><th style="padding:0 0 12px;">Score</th><th style="padding:0 0 12px;">Kinds</th></tr></thead>
          <tbody>{behavior_rows}</tbody>
        </table>
      </div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Tooling</h2>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">{tooling}</div>
        <h2 style="margin:22px 0 12px;">Missing pieces</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{missing_items}</ul>
      </div>
    </section>

    <section style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin-top:20px;">
      <h2 style="margin-top:0;">Prompt surface highlights</h2>
      <ol style="margin:0;padding-left:20px;line-height:1.6;">{prompt_items}</ol>
    </section>

    <section style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:20px;">
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Runtime evidence</h2>
        <ol style="margin:0;padding-left:20px;line-height:1.6;">{runtime_items}</ol>
      </article>
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Memory evidence</h2>
        <ol style="margin:0;padding-left:20px;line-height:1.6;">{memory_items}</ol>
      </article>
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Orchestration evidence</h2>
        <ol style="margin:0;padding-left:20px;line-height:1.6;">{orchestration_items}</ol>
      </article>
    </section>

    <section style="display:grid;grid-template-columns:0.8fr 1.2fr;gap:20px;margin-top:20px;">
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">File roles</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{file_roles}</ul>
      </article>
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Scan limits</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">
          <li>Candidate files scanned: {report.scan_limits.candidate_files_scanned}</li>
          <li>Code files scanned: {report.scan_limits.code_files_scanned}/{report.scan_limits.code_files_total}</li>
          <li>Max code files per language: {report.scan_limits.max_code_files_per_language}</li>
          <li>Truncated languages: {escape(', '.join(report.scan_limits.truncated_languages) or 'None')}</li>
        </ul>
      </article>
    </section>

    <section style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Confidence and uncertainty</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{confidence_items}</ul>
      </article>
      <article style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">Claim / implementation mismatches</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{contradiction_items}</ul>
      </article>
    </section>

    <section style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin-top:20px;">
      <h2 style="margin-top:0;">Prompt/runtime linkage</h2>
      <ol style="margin:0;padding-left:20px;line-height:1.6;">{prompt_link_items}</ol>
    </section>
  </main>
</body>
</html>"""


def build_comparison(left: ScanReport, right: ScanReport) -> dict[str, Any]:
    left_sources = [item.path for item in left.behavior_sources[:5]]
    right_sources = [item.path for item in right.behavior_sources[:5]]

    def _basis(report: ScanReport) -> str:
        code = report.evidence_summary.code_evidence + report.evidence_summary.graph_evidence
        docs = report.evidence_summary.text_evidence + report.evidence_summary.path_evidence
        if code >= docs * 1.5:
            return "code-led"
        if docs > code * 1.5:
            return "docs-led"
        return "combined"

    runtime_gap = (left.evidence_summary.code_evidence + left.evidence_summary.graph_evidence) - (
        right.evidence_summary.code_evidence + right.evidence_summary.graph_evidence
    )
    prompt_gap = (left.counts.artifacts + left.evidence_summary.text_evidence) - (
        right.counts.artifacts + right.evidence_summary.text_evidence
    )
    confidence_gap = round(left.overall_confidence.score - right.overall_confidence.score, 2)
    contradiction_gap = len(left.contradictions) - len(right.contradictions)
    linkage_gap = len(left.prompt_runtime_links) - len(right.prompt_runtime_links)
    family_basis_delta = (
        f"{left.summary.repo_family}:{'policy-constrained' if left.constraint_adjustments else 'structural'} vs "
        f"{right.summary.repo_family}:{'policy-constrained' if right.constraint_adjustments else 'structural'}"
    )
    constraint_delta = len(left.constraint_adjustments) - len(right.constraint_adjustments)
    why_they_differ = [
        f"Repo family: {left.summary.repo_family} vs {right.summary.repo_family}",
        f"Runtime density gap: {runtime_gap}",
        f"Prompt density gap: {prompt_gap}",
        f"Confidence gap: {confidence_gap}",
        f"Contradiction gap: {contradiction_gap}",
        f"Linkage gap: {linkage_gap}",
        f"Constraint gap: {constraint_delta}",
    ]
    if left.summary.repo_family != right.summary.repo_family:
        most_defensible_difference = (
            f"{left.repo.name} reads as {left.summary.repo_family}; {right.repo.name} reads as {right.summary.repo_family}."
        )
    elif runtime_gap != 0:
        heavier = left.repo.name if runtime_gap > 0 else right.repo.name
        most_defensible_difference = f"{heavier} has the stronger runtime evidence stack."
    elif prompt_gap != 0:
        heavier = left.repo.name if prompt_gap > 0 else right.repo.name
        most_defensible_difference = f"{heavier} has the denser prompt and doc behavior surface."
    else:
        most_defensible_difference = "The repos differ more in confidence and contradictions than in raw shape."

    return {
        "left": {
            "name": left.repo.name,
            "repo_family": left.summary.repo_family,
            "archetype": left.summary.repo_archetype,
            "orchestration": left.summary.orchestration_model,
            "memory": left.summary.memory_model,
            "xray_call": left.summary.xray_call,
            "artifacts": left.counts.artifacts,
            "confidence": {
                "family": left.repo_family_confidence.model_dump(mode="json"),
                "archetype": left.repo_archetype_confidence.model_dump(mode="json"),
                "orchestration": left.orchestration_confidence.model_dump(mode="json"),
                "memory": left.memory_confidence.model_dump(mode="json"),
                "overall": left.overall_confidence.model_dump(mode="json"),
            },
            "contradictions": left.contradictions,
            "prompt_runtime_links": [item.model_dump(mode="json") for item in left.prompt_runtime_links[:6]],
            "call_basis": _basis(left),
            "runtime_density": left.runtime_density,
            "prompt_density": left.prompt_density,
            "linkage_density": left.linkage_density,
            "runtime_evidence": [item.model_dump(mode="json") for item in left.runtime_evidence[:4]],
            "top_behavior_sources": left_sources,
            "constraint_adjustments": [item.model_dump(mode="json") for item in left.constraint_adjustments],
            "decision_trace": [item.model_dump(mode="json") for item in left.decision_trace[:8]],
        },
        "right": {
            "name": right.repo.name,
            "repo_family": right.summary.repo_family,
            "archetype": right.summary.repo_archetype,
            "orchestration": right.summary.orchestration_model,
            "memory": right.summary.memory_model,
            "xray_call": right.summary.xray_call,
            "artifacts": right.counts.artifacts,
            "confidence": {
                "family": right.repo_family_confidence.model_dump(mode="json"),
                "archetype": right.repo_archetype_confidence.model_dump(mode="json"),
                "orchestration": right.orchestration_confidence.model_dump(mode="json"),
                "memory": right.memory_confidence.model_dump(mode="json"),
                "overall": right.overall_confidence.model_dump(mode="json"),
            },
            "contradictions": right.contradictions,
            "prompt_runtime_links": [item.model_dump(mode="json") for item in right.prompt_runtime_links[:6]],
            "call_basis": _basis(right),
            "runtime_density": right.runtime_density,
            "prompt_density": right.prompt_density,
            "linkage_density": right.linkage_density,
            "runtime_evidence": [item.model_dump(mode="json") for item in right.runtime_evidence[:4]],
            "top_behavior_sources": right_sources,
            "constraint_adjustments": [item.model_dump(mode="json") for item in right.constraint_adjustments],
            "decision_trace": [item.model_dump(mode="json") for item in right.decision_trace[:8]],
        },
        "differences": {
            "same_family": left.summary.repo_family == right.summary.repo_family,
            "same_archetype": left.summary.repo_archetype == right.summary.repo_archetype,
            "same_orchestration": left.summary.orchestration_model == right.summary.orchestration_model,
            "same_memory": left.summary.memory_model == right.summary.memory_model,
            "artifact_gap": left.counts.artifacts - right.counts.artifacts,
            "runtime_density_gap": runtime_gap,
            "prompt_density_gap": prompt_gap,
            "contradiction_gap": contradiction_gap,
            "linkage_gap": linkage_gap,
            "family_basis_delta": family_basis_delta,
            "constraint_delta": constraint_delta,
            "linkage_density_delta": round(left.linkage_density - right.linkage_density, 2),
            "shared_tooling": sorted(set(left.tooling_surfaces).intersection(right.tooling_surfaces)),
            "left_only_tooling": sorted(set(left.tooling_surfaces) - set(right.tooling_surfaces)),
            "right_only_tooling": sorted(set(right.tooling_surfaces) - set(left.tooling_surfaces)),
            "confidence_gap": confidence_gap,
        },
        "why_they_differ": why_they_differ,
        "most_defensible_difference": most_defensible_difference,
        "what_is_structurally_supported": [
            f"{left.repo.name}: {left.summary.repo_family} via {left.runtime_density} runtime density and {left.prompt_density} prompt density",
            f"{right.repo.name}: {right.summary.repo_family} via {right.runtime_density} runtime density and {right.prompt_density} prompt density",
        ],
        "what_is_policy_constrained": [
            f"{left.repo.name}: {len(left.constraint_adjustments)} adjustments",
            f"{right.repo.name}: {len(right.constraint_adjustments)} adjustments",
        ],
        "what_remains_uncertain": [
            f"{left.repo.name}: {left.overall_confidence.level} confidence",
            f"{right.repo.name}: {right.overall_confidence.level} confidence",
        ],
    }


def render_comparison_markdown(left: ScanReport, right: ScanReport) -> str:
    comparison = build_comparison(left, right)
    shared_tooling = ", ".join(comparison["differences"]["shared_tooling"]) or "None"
    left_only_tooling = ", ".join(comparison["differences"]["left_only_tooling"]) or "None"
    right_only_tooling = ", ".join(comparison["differences"]["right_only_tooling"]) or "None"
    left_sources = "\n".join(f"- `{item}`" for item in comparison["left"]["top_behavior_sources"]) or "- None"
    right_sources = "\n".join(f"- `{item}`" for item in comparison["right"]["top_behavior_sources"]) or "- None"

    return f"""# Prompt-xray Compare: {left.repo.name} vs {right.repo.name}

## Calls

- **{left.repo.name}**: {left.summary.xray_call}
- **{right.repo.name}**: {right.summary.xray_call}

## Headline Difference

- Repo family: `{left.summary.repo_family}` vs `{right.summary.repo_family}`
- Archetypes: `{left.summary.repo_archetype}` vs `{right.summary.repo_archetype}`
- Orchestration: `{left.summary.orchestration_model}` vs `{right.summary.orchestration_model}`
- Memory: `{left.summary.memory_model}` vs `{right.summary.memory_model}`
- Artifact count: `{left.counts.artifacts}` vs `{right.counts.artifacts}`
- Evidence basis: `{comparison["left"]["call_basis"]}` vs `{comparison["right"]["call_basis"]}`
- Overall confidence: `{left.overall_confidence.level}` ({left.overall_confidence.score:.2f}) vs `{right.overall_confidence.level}` ({right.overall_confidence.score:.2f})

## Why They Differ

- Most defensible difference: {comparison["most_defensible_difference"]}
{chr(10).join(f"- {item}" for item in comparison["why_they_differ"])}

## Structural vs Policy

### Structurally supported
{chr(10).join(f"- {item}" for item in comparison["what_is_structurally_supported"])}

### Policy constrained
{chr(10).join(f"- {item}" for item in comparison["what_is_policy_constrained"])}

### Still uncertain
{chr(10).join(f"- {item}" for item in comparison["what_remains_uncertain"])}

## Tooling Overlap

- Shared tooling: {shared_tooling}
- {left.repo.name} only: {left_only_tooling}
- {right.repo.name} only: {right_only_tooling}

## Top Behavior Sources

### {left.repo.name}
{left_sources}

### {right.repo.name}
{right_sources}

## Strongly Supported Differences

- Runtime density gap: `{comparison["differences"]["runtime_density_gap"]}`
- Prompt density gap: `{comparison["differences"]["prompt_density_gap"]}`
- Confidence gap: `{comparison["differences"]["confidence_gap"]}`

## Contradictions And Uncertainty

### {left.repo.name}
{chr(10).join(f"- {item}" for item in left.contradictions) or "- None detected"}

### {right.repo.name}
{chr(10).join(f"- {item}" for item in right.contradictions) or "- None detected"}

## Verdict

- {left.repo.name}: {left.summary.verdict}
- {right.repo.name}: {right.summary.verdict}
"""


def render_comparison_html(left: ScanReport, right: ScanReport) -> str:
    comparison = build_comparison(left, right)
    left_sources = "".join(f"<li><code>{escape(item)}</code></li>" for item in comparison["left"]["top_behavior_sources"])
    right_sources = "".join(f"<li><code>{escape(item)}</code></li>" for item in comparison["right"]["top_behavior_sources"])
    shared_tooling = ", ".join(comparison["differences"]["shared_tooling"]) or "None"
    left_only_tooling = ", ".join(comparison["differences"]["left_only_tooling"]) or "None"
    right_only_tooling = ", ".join(comparison["differences"]["right_only_tooling"]) or "None"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prompt-xray Compare: {escape(left.repo.name)} vs {escape(right.repo.name)}</title>
</head>
<body style="margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:#0b1020;color:#e5e7eb;">
  <main style="max-width:1200px;margin:0 auto;padding:40px 24px 80px;">
    <section style="background:linear-gradient(135deg,#111827,#172554);border:1px solid #334155;border-radius:24px;padding:28px;">
      <h1 style="margin:0 0 14px;font-size:38px;">Prompt-xray Compare</h1>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <div style="background:#0f172a;border:1px solid #334155;border-radius:18px;padding:18px;">
          <div style="margin-bottom:10px;">{_html_badge(left.summary.repo_family, "accent")} {_html_badge(left.summary.repo_archetype, "accent")} {_html_badge(left.summary.orchestration_model, "warn")} {_html_badge(left.overall_confidence.level, "good" if left.overall_confidence.level == "high" else "warn" if left.overall_confidence.level == "medium" else "danger")}</div>
          <h2 style="margin:0 0 8px;">{escape(left.repo.name)}</h2>
          <p style="margin:0;font-size:20px;font-weight:700;">{escape(left.summary.xray_call)}</p>
        </div>
        <div style="background:#0f172a;border:1px solid #334155;border-radius:18px;padding:18px;">
          <div style="margin-bottom:10px;">{_html_badge(right.summary.repo_family, "accent")} {_html_badge(right.summary.repo_archetype, "accent")} {_html_badge(right.summary.orchestration_model, "warn")} {_html_badge(right.overall_confidence.level, "good" if right.overall_confidence.level == "high" else "warn" if right.overall_confidence.level == "medium" else "danger")}</div>
          <h2 style="margin:0 0 8px;">{escape(right.repo.name)}</h2>
          <p style="margin:0;font-size:20px;font-weight:700;">{escape(right.summary.xray_call)}</p>
        </div>
      </div>
    </section>

    <section style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin-top:20px;">
      <h2 style="margin-top:0;">Headline difference</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>
          <tr><td style="padding:8px 0;color:#94a3b8;">Repo family</td><td style="padding:8px 0;">{escape(left.summary.repo_family)}</td><td style="padding:8px 0;">{escape(right.summary.repo_family)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Archetype</td><td style="padding:8px 0;">{escape(left.summary.repo_archetype)}</td><td style="padding:8px 0;">{escape(right.summary.repo_archetype)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Orchestration</td><td style="padding:8px 0;">{escape(left.summary.orchestration_model)}</td><td style="padding:8px 0;">{escape(right.summary.orchestration_model)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Memory</td><td style="padding:8px 0;">{escape(left.summary.memory_model)}</td><td style="padding:8px 0;">{escape(right.summary.memory_model)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Evidence basis</td><td style="padding:8px 0;">{escape(comparison["left"]["call_basis"])}</td><td style="padding:8px 0;">{escape(comparison["right"]["call_basis"])}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Overall confidence</td><td style="padding:8px 0;">{left.overall_confidence.level} ({left.overall_confidence.score:.2f})</td><td style="padding:8px 0;">{right.overall_confidence.level} ({right.overall_confidence.score:.2f})</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Artifacts</td><td style="padding:8px 0;">{left.counts.artifacts}</td><td style="padding:8px 0;">{right.counts.artifacts}</td></tr>
        </tbody>
      </table>
      <p style="margin:18px 0 0;"><strong>Most defensible difference:</strong> {escape(comparison["most_defensible_difference"])}</p>
      <ul style="margin:12px 0 0;padding-left:18px;line-height:1.6;">{"".join(f"<li>{escape(item)}</li>" for item in comparison["why_they_differ"])}</ul>
    </section>

    <section style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">{escape(left.repo.name)} top sources</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{left_sources}</ul>
      </div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">{escape(right.repo.name)} top sources</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{right_sources}</ul>
      </div>
    </section>

    <section style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin-top:20px;">
      <h2 style="margin-top:0;">Tooling overlap</h2>
      <p><strong>Shared:</strong> {escape(shared_tooling)}</p>
      <p><strong>{escape(left.repo.name)} only:</strong> {escape(left_only_tooling)}</p>
      <p><strong>{escape(right.repo.name)} only:</strong> {escape(right_only_tooling)}</p>
    </section>

    <section style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">{escape(left.repo.name)} contradictions</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{"".join(f"<li>{escape(item)}</li>" for item in left.contradictions) or "<li>None detected</li>"}</ul>
      </div>
      <div style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;">
        <h2 style="margin-top:0;">{escape(right.repo.name)} contradictions</h2>
        <ul style="margin:0;padding-left:18px;line-height:1.6;">{"".join(f"<li>{escape(item)}</li>" for item in right.contradictions) or "<li>None detected</li>"}</ul>
      </div>
    </section>
  </main>
</body>
</html>"""


def write_outputs(report: ScanReport, out_dir: Path, fmt: str, html: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if fmt in {"markdown", "both"}:
        markdown_path = out_dir / "report.md"
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        written.append(markdown_path)

    if fmt in {"json", "both"}:
        json_path = out_dir / "report.json"
        json_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        written.append(json_path)

    if html:
        html_path = out_dir / "report.html"
        html_path.write_text(render_html(report), encoding="utf-8")
        written.append(html_path)

    return written


def write_comparison_outputs(
    left: ScanReport,
    right: ScanReport,
    out_dir: Path,
    fmt: str,
    html: bool = False,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if fmt in {"markdown", "both"}:
        markdown_path = out_dir / "compare.md"
        markdown_path.write_text(render_comparison_markdown(left, right), encoding="utf-8")
        written.append(markdown_path)

    if fmt in {"json", "both"}:
        json_path = out_dir / "compare.json"
        json_path.write_text(
            json.dumps(build_comparison(left, right), indent=2),
            encoding="utf-8",
        )
        written.append(json_path)

    if html:
        html_path = out_dir / "compare.html"
        html_path.write_text(render_comparison_html(left, right), encoding="utf-8")
        written.append(html_path)

    return written
