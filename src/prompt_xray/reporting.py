from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .models import Artifact, ScanReport


def _artifact_line(artifact: Artifact) -> str:
    confidence = f"{artifact.confidence:.2f}"
    signals = ", ".join(artifact.signals[:4]) if artifact.signals else "no explicit signals"
    snippet = f" -- {artifact.source_snippet}" if artifact.source_snippet else ""
    return f"- `{artifact.kind}` `{artifact.path}` ({confidence}) [{signals}]{snippet}"


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

    return f"""# Prompt-xray Report: {report.repo.name}

## What This Repo Is

This repo is classified as **{report.summary.repo_archetype}**.

> {report.summary.xray_call}

{report.summary.verdict}

## Prompt Surface Map

{prompt_surface}

## Behavior Sources

{behavior_sources}

## Tooling And Integrations

- Tooling surfaces: {tooling}

## Orchestration And Memory

- Orchestration model: `{report.summary.orchestration_model}`
- Memory model: `{report.summary.memory_model}`

## Real Versus Packaging

### Real implementation
{real_impl}

### Prompt/config structure
{prompt_cfg}

### Presentation/marketing layer
{presentation}

## Missing Pieces

{missing}

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
      <div style="margin-bottom:12px;">{_html_badge(report.summary.repo_archetype, "accent")} {_html_badge(report.summary.orchestration_model, "warn")} {_html_badge(report.summary.memory_model, "neutral")}</div>
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
  </main>
</body>
</html>"""


def build_comparison(left: ScanReport, right: ScanReport) -> dict[str, Any]:
    left_sources = [item.path for item in left.behavior_sources[:5]]
    right_sources = [item.path for item in right.behavior_sources[:5]]

    return {
        "left": {
            "name": left.repo.name,
            "archetype": left.summary.repo_archetype,
            "orchestration": left.summary.orchestration_model,
            "memory": left.summary.memory_model,
            "xray_call": left.summary.xray_call,
            "artifacts": left.counts.artifacts,
            "top_behavior_sources": left_sources,
        },
        "right": {
            "name": right.repo.name,
            "archetype": right.summary.repo_archetype,
            "orchestration": right.summary.orchestration_model,
            "memory": right.summary.memory_model,
            "xray_call": right.summary.xray_call,
            "artifacts": right.counts.artifacts,
            "top_behavior_sources": right_sources,
        },
        "differences": {
            "same_archetype": left.summary.repo_archetype == right.summary.repo_archetype,
            "same_orchestration": left.summary.orchestration_model == right.summary.orchestration_model,
            "same_memory": left.summary.memory_model == right.summary.memory_model,
            "artifact_gap": left.counts.artifacts - right.counts.artifacts,
            "shared_tooling": sorted(set(left.tooling_surfaces).intersection(right.tooling_surfaces)),
            "left_only_tooling": sorted(set(left.tooling_surfaces) - set(right.tooling_surfaces)),
            "right_only_tooling": sorted(set(right.tooling_surfaces) - set(left.tooling_surfaces)),
        },
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

- Archetypes: `{left.summary.repo_archetype}` vs `{right.summary.repo_archetype}`
- Orchestration: `{left.summary.orchestration_model}` vs `{right.summary.orchestration_model}`
- Memory: `{left.summary.memory_model}` vs `{right.summary.memory_model}`
- Artifact count: `{left.counts.artifacts}` vs `{right.counts.artifacts}`

## Tooling Overlap

- Shared tooling: {shared_tooling}
- {left.repo.name} only: {left_only_tooling}
- {right.repo.name} only: {right_only_tooling}

## Top Behavior Sources

### {left.repo.name}
{left_sources}

### {right.repo.name}
{right_sources}

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
          <div style="margin-bottom:10px;">{_html_badge(left.summary.repo_archetype, "accent")} {_html_badge(left.summary.orchestration_model, "warn")}</div>
          <h2 style="margin:0 0 8px;">{escape(left.repo.name)}</h2>
          <p style="margin:0;font-size:20px;font-weight:700;">{escape(left.summary.xray_call)}</p>
        </div>
        <div style="background:#0f172a;border:1px solid #334155;border-radius:18px;padding:18px;">
          <div style="margin-bottom:10px;">{_html_badge(right.summary.repo_archetype, "accent")} {_html_badge(right.summary.orchestration_model, "warn")}</div>
          <h2 style="margin:0 0 8px;">{escape(right.repo.name)}</h2>
          <p style="margin:0;font-size:20px;font-weight:700;">{escape(right.summary.xray_call)}</p>
        </div>
      </div>
    </section>

    <section style="background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;margin-top:20px;">
      <h2 style="margin-top:0;">Headline difference</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>
          <tr><td style="padding:8px 0;color:#94a3b8;">Archetype</td><td style="padding:8px 0;">{escape(left.summary.repo_archetype)}</td><td style="padding:8px 0;">{escape(right.summary.repo_archetype)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Orchestration</td><td style="padding:8px 0;">{escape(left.summary.orchestration_model)}</td><td style="padding:8px 0;">{escape(right.summary.orchestration_model)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Memory</td><td style="padding:8px 0;">{escape(left.summary.memory_model)}</td><td style="padding:8px 0;">{escape(right.summary.memory_model)}</td></tr>
          <tr><td style="padding:8px 0;color:#94a3b8;">Artifacts</td><td style="padding:8px 0;">{left.counts.artifacts}</td><td style="padding:8px 0;">{right.counts.artifacts}</td></tr>
        </tbody>
      </table>
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
