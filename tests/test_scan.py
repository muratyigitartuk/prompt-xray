from __future__ import annotations

import json
from pathlib import Path

from prompt_xray.analysis import analyze_target
from prompt_xray.reporting import build_comparison, render_comparison_html, render_comparison_markdown, render_html, render_markdown


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_prompt_library_repo_is_classified_correctly(tmp_path: Path) -> None:
    repo = tmp_path / "agency-like"
    _write(
        repo / "engineering" / "frontend-agent.md",
        """---
name: Frontend Developer
description: Frontend agent
vibe: sharp
---

You are Frontend Developer.

## Your Identity & Memory
## Your Core Mission
## Critical Rules You Must Follow
Remember successful patterns.
""",
    )
    _write(
        repo / "specialized" / "agents-orchestrator.md",
        """---
name: Agents Orchestrator
description: Orchestrates agents
---

Spawn agent.
Phase 1.
Handoff to QA.
Remember project state.
Rollback when QA fails.
""",
    )
    _write(
        repo / "integrations" / "README.md",
        "Supported tools: Cursor, Claude Code, Gemini CLI. Install with install.sh.",
    )
    _write(repo / "integrations" / "cursor" / "README.md", "Cursor integration files live here.")
    _write(repo / "scripts" / "convert.sh", "#!/usr/bin/env bash\necho convert\n")

    report = analyze_target(str(repo))

    assert report.summary.repo_archetype in {"prompt-library", "workflow-pack", "tool-integration-pack"}
    assert report.summary.orchestration_model == "prompt-defined"
    assert report.summary.memory_model in {"documented-only", "tool-assisted"}
    assert "Cursor" in report.tooling_surfaces
    assert report.artifacts


def test_tool_specific_rules_are_detected(tmp_path: Path) -> None:
    repo = tmp_path / "tooling"
    _write(
        repo / ".cursor" / "rules" / "persona.mdc",
        """---
description: Cursor rule
globs: ""
alwaysApply: false
---
You are a strict reviewer.
""",
    )
    _write(repo / ".windsurfrules", "Always follow these instructions.")

    report = analyze_target(str(repo))

    assert "Cursor" in report.tooling_surfaces
    assert "Windsurf" in report.tooling_surfaces
    assert any(artifact.kind == "rule_file" for artifact in report.artifacts)


def test_readme_name_drops_do_not_count_as_tool_support_by_themselves(tmp_path: Path) -> None:
    repo = tmp_path / "mentions-only"
    _write(
        repo / "README.md",
        "Compatible with Cursor, Claude Code, Copilot, Gemini CLI, and Windsurf clients.",
    )

    report = analyze_target(str(repo))

    assert report.tooling_surfaces == []


def test_repo_with_little_prompt_content_is_graceful(tmp_path: Path) -> None:
    repo = tmp_path / "plain-repo"
    _write(repo / "README.md", "Simple utility library.")
    _write(repo / "src" / "main.py", "print('hello')\n")

    report = analyze_target(str(repo))

    assert report.counts.candidate_files >= 1
    assert report.summary.repo_archetype in {"unclear", "mixed"}
    assert "prompt" in report.summary.verdict.lower() or "agent" in report.summary.verdict.lower()


def test_mixed_repo_is_not_prompt_only(tmp_path: Path) -> None:
    repo = tmp_path / "mixed-repo"
    _write(repo / "AGENTS.md", "You are the system prompt. Critical rules apply.")
    _write(
        repo / "src" / "server.py",
        """from fastapi import FastAPI
app = FastAPI()
""",
    )

    report = analyze_target(str(repo))

    assert report.summary.repo_archetype == "mixed"
    assert report.summary.orchestration_model == "runtime-implemented"
    assert any("Runtime-oriented files" in item for item in report.real_vs_packaging.real_implementation)


def test_markdown_and_json_shapes_are_stable(tmp_path: Path) -> None:
    repo = tmp_path / "skill-repo"
    _write(
        repo / "SKILL.md",
        """---
name: analysis-surgeon
description: Deep skill
---

Use this skill when you need deep analysis.
You are surgical.
""",
    )

    report = analyze_target(str(repo))
    markdown = render_markdown(report)
    html = render_html(report)
    payload = report.model_dump(mode="json")

    assert "# Prompt-xray Report:" in markdown
    assert "## Prompt Surface Map" in markdown
    assert report.summary.xray_call
    assert "Prompt-xray:" in html
    assert report.summary.xray_call in html
    assert payload["summary"]["repo_archetype"]
    assert isinstance(payload["artifacts"], list)
    json.dumps(payload)


def test_behavior_sources_downweight_top_level_docs(tmp_path: Path) -> None:
    repo = tmp_path / "behavior-weighting"
    _write(
        repo / "README.md",
        """You are a powerful system.
Critical rules.
Phase 1.
Phase 2.
""",
    )
    _write(
        repo / "agents" / "system.md",
        """---
name: Runtime Agent
description: Main agent
---
You are Runtime Agent.
## Your Identity & Memory
## Critical Rules You Must Follow
""",
    )

    report = analyze_target(str(repo))

    assert report.behavior_sources
    assert report.behavior_sources[0].path == "agents/system.md"


def test_compare_output_is_stable(tmp_path: Path) -> None:
    left = tmp_path / "left-repo"
    right = tmp_path / "right-repo"
    _write(
        left / "SKILL.md",
        """---
name: deep-reader
description: skill
---
Use this skill when you need depth.
You are systematic.
""",
    )
    _write(
        right / "src" / "server.py",
        """from fastapi import FastAPI
app = FastAPI()
""",
    )
    _write(right / "AGENTS.md", "You are the system prompt.")

    left_report = analyze_target(str(left))
    right_report = analyze_target(str(right))
    comparison = build_comparison(left_report, right_report)
    markdown = render_comparison_markdown(left_report, right_report)
    html = render_comparison_html(left_report, right_report)

    assert comparison["left"]["name"] == "left-repo"
    assert comparison["right"]["name"] == "right-repo"
    assert "# Prompt-xray Compare:" in markdown
    assert "## Headline Difference" in markdown
    assert "Prompt-xray Compare" in html
