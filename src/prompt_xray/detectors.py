from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .ast_analysis import analyze_python_ast, analyze_ts_ast
from .models import EvidenceItem, EvidenceSummary, FileAnalysis, PromptRuntimeLink, RoleCount, ScanLimits

PYTHON_RUNTIME_PATTERNS = {
    "fastapi": re.compile(r"\b(FastAPI|APIRouter)\s*\("),
    "flask": re.compile(r"\bFlask\s*\("),
    "django": re.compile(r"\b(get_wsgi_application|execute_from_command_line|urlpatterns)\b"),
    "cli": re.compile(r"\b(typer\.Typer|click\.(command|group)|ArgumentParser)\b"),
    "worker": re.compile(r"\b(Celery|BackgroundTasks|APScheduler|schedule\.every|create_task)\b"),
    "queue": re.compile(r"\b(rq|dramatiq|huey|arq)\b", re.IGNORECASE),
    "storage": re.compile(r"\b(sqlite3|redis|sqlalchemy|SessionLocal|checkpoint|history|state_store|store)\b"),
}

TS_RUNTIME_PATTERNS = {
    "express": re.compile(r"\b(express|Express)\s*\("),
    "fastify": re.compile(r"\bfastify\s*\("),
    "nest": re.compile(r"\bNestFactory\.create\b"),
    "next_api": re.compile(r"\b(NextRequest|NextResponse|route\.ts|pages/api)\b"),
    "cli": re.compile(r"\b(commander|yargs|cac)\b"),
    "worker": re.compile(r"\b(BullMQ|Worker|Agenda|queueMicrotask|setInterval)\b"),
    "storage": re.compile(r"\b(redis|prisma|typeorm|sequelize|checkpoint|history|session|store)\b"),
}

FROM_IMPORT_RE = re.compile(r"^\s*from\s+([A-Za-z0-9_./-]+)\s+import\b", re.MULTILINE)
JS_IMPORT_RE = re.compile(r"""(?:from|require\()\s*["'](\.{1,2}/[^"']+)["']""")
DYNAMIC_IMPORT_RE = re.compile(r"""import\(\s*["'](\.{1,2}/[^"']+)["']\s*\)""")
CONFIG_TARGET_RE = re.compile(r"""["']([A-Za-z0-9_./-]+\.(?:py|js|ts|tsx|jsx))["']""")
PYPROJECT_SCRIPT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*['\"]([A-Za-z0-9_.]+):", re.MULTILINE)

PROMPT_HINTS = (
    "you are",
    "system prompt",
    "critical rules",
    "your mission",
    "workflow",
    "remember",
    "recall",
    "rollback",
    "agent",
)
RULE_HINTS = ("skill.md", ".windsurfrules", ".mdc", ".cursor/rules", "copilot-instructions")
CONFIG_NAMES = {"package.json", "pyproject.toml", "dockerfile", "docker-compose.yml", "docker-compose.yaml"}
NEGATIVE_PARTS = {
    "tests",
    "__tests__",
    "test",
    "testing",
    "examples",
    "example",
    "benchmarks",
    "benchmark",
    "fixtures",
    "fixture",
    "docs",
    "migrations",
    "snapshots",
    "snapshot",
    "generated",
    "vendor",
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _language_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        return "javascript"
    if suffix in {".ts", ".tsx", ".mts", ".cts"}:
        return "typescript"
    return ""


def _resolve_relative_import(base: Path, target: str, repo_rel_paths: set[str]) -> str | None:
    raw = (base.parent / target).as_posix()
    candidates = [raw]
    for suffix in (".py", ".js", ".ts", ".tsx", ".jsx"):
        candidates.append(raw + suffix)
        candidates.append(f"{raw}/index{suffix}")
    normalized: list[str] = []
    for candidate in candidates:
        parts: list[str] = []
        for piece in candidate.split("/"):
            if piece in {"", "."}:
                continue
            if piece == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(piece)
        normalized.append("/".join(parts))
    for candidate in normalized:
        if candidate in repo_rel_paths:
            return candidate
    return None


def _resolve_python_module(base: Path, module_name: str, repo_rel_paths: set[str]) -> str | None:
    cleaned = module_name.lstrip(".")
    if module_name.startswith("."):
        return _resolve_relative_import(base, module_name.replace(".", "/"), repo_rel_paths)

    module_path = cleaned.replace(".", "/")
    for candidate in (f"{module_path}.py", f"{module_path}/__init__.py"):
        if candidate in repo_rel_paths:
            return candidate
    if base.parts[:-1]:
        prefixed = f"{base.parts[0]}/{module_path}.py"
        if prefixed in repo_rel_paths:
            return prefixed
    return None


def _regex_graph_targets(rel_path: Path, text: str, language: str, repo_rel_paths: set[str]) -> list[str]:
    targets: set[str] = set()
    file_name_map = {Path(item).name: item for item in repo_rel_paths}

    if language in {"javascript", "typescript"}:
        for pattern in (JS_IMPORT_RE, DYNAMIC_IMPORT_RE):
            for match in pattern.findall(text):
                resolved = _resolve_relative_import(rel_path, match, repo_rel_paths)
                if resolved:
                    targets.add(resolved)
    elif language == "python":
        for match in FROM_IMPORT_RE.findall(text):
            resolved = _resolve_python_module(rel_path, match, repo_rel_paths)
            if resolved:
                targets.add(resolved)

    if rel_path.name == "package.json":
        try:
            payload = json.loads(text or "{}")
        except json.JSONDecodeError:
            payload = {}
        for command in payload.get("scripts", {}).values():
            for match in CONFIG_TARGET_RE.findall(command):
                resolved = file_name_map.get(Path(match).name)
                if resolved:
                    targets.add(resolved)

    if rel_path.name == "pyproject.toml":
        for _, module_ref in PYPROJECT_SCRIPT_RE.findall(text):
            resolved = _resolve_python_module(rel_path, module_ref, repo_rel_paths)
            if resolved:
                targets.add(resolved)

    return sorted(targets)


def _regex_code_signals(language: str, text: str) -> list[str]:
    signals: list[str] = []
    if language not in {"python", "javascript", "typescript"}:
        return signals

    pattern_map = PYTHON_RUNTIME_PATTERNS if language == "python" else TS_RUNTIME_PATTERNS
    for label, pattern in pattern_map.items():
        if pattern.search(text):
            signals.append(f"regex:{label}")
    return sorted(set(signals))


def _path_signals(rel_path: Path) -> list[str]:
    rel_posix = rel_path.as_posix().lower()
    signals: list[str] = []
    for token in ("agents", "prompts", "skills", "integrations", "workflows", "memory", "checkpoint", "plugins", "sdk"):
        if token in rel_posix:
            signals.append(token)
    if rel_path.name.lower() in CONFIG_NAMES:
        signals.append("config-name")
    if rel_path.name.lower().startswith(("readme", "system", "prompt")):
        signals.append("special-doc")
    return sorted(set(signals))


def _text_signals(text: str) -> list[str]:
    text_lower = text.lower()
    signals = [hint for hint in PROMPT_HINTS if hint in text_lower]
    if "supported tools" in text_lower or "tools:" in text_lower:
        signals.append("tooling")
    if any(token in text_lower for token in ("checkpoint", "session", "history", "remember", "recall", "rollback")):
        signals.append("memory")
    if any(token in text_lower for token in ("phase 1", "handoff", "qa gate", "autonomous", "scheduler", "control loop")):
        signals.append("orchestration")
    return sorted(set(signals))


def _negative_signals(rel_path: Path, text: str) -> list[str]:
    parts = {part.lower() for part in rel_path.parts}
    signals = [part for part in NEGATIVE_PARTS if part in parts]
    rel_posix = rel_path.as_posix().lower()
    if rel_posix.startswith("readme") or rel_posix.endswith("/readme.md"):
        signals.append("readme")
    if "generated" in text.lower():
        signals.append("generated-text")
    return sorted(set(signals))


def _infer_role(
    rel_path: Path,
    language: str,
    path_signals: list[str],
    text_signals: list[str],
    code_signals: list[str],
    negative_signals: list[str],
    prompt_links: list[str],
) -> str:
    rel_posix = rel_path.as_posix().lower()
    name = rel_path.name.lower()
    code_text = " ".join(code_signals).lower()

    if any(signal in negative_signals for signal in {"tests", "__tests__", "test", "testing", "examples", "example", "benchmarks", "benchmark", "fixtures", "fixture"}):
        return "test_or_example"
    if any(signal in negative_signals for signal in {"generated", "generated-text", "vendor"}):
        return "generated_or_vendor"
    if any(token in rel_posix for token in RULE_HINTS):
        return "rule_or_skill"
    if name in CONFIG_NAMES or rel_path.suffix.lower() in {".json", ".yaml", ".yml", ".toml"}:
        return "config_or_manifest"
    if prompt_links:
        return "runtime_module"
    if any(token in rel_posix for token in ("memory", "checkpoint", "session", "history", "store")) and any(
        token in code_text for token in ("ast:storage", "ast:state", "regex:storage")
    ):
        return "state_or_storage"
    if language and any(token in code_text for token in ("ast:entrypoint", "ast:web-service", "ast:cli", "regex:fastapi", "regex:flask", "regex:django", "regex:express", "regex:fastify", "regex:nest", "regex:next_api", "regex:cli")):
        return "runtime_entrypoint"
    if language and code_signals:
        return "runtime_module"
    if any(signal in path_signals for signal in {"agents", "prompts", "skills"}) or any(
        signal in text_signals for signal in {"you are", "system prompt", "critical rules", "workflow", "agent"}
    ):
        return "prompt_doc"
    if "special-doc" in path_signals and any(
        signal in text_signals for signal in {"you are", "system prompt", "critical rules", "workflow"}
    ):
        return "prompt_doc"
    return "unknown"


def _runtime_level(role: str, code_signals: list[str], graph_targets: list[str], prompt_links: list[str]) -> str:
    code_text = " ".join(code_signals).lower()
    if role == "state_or_storage":
        return "stateful_runtime"
    if role == "runtime_entrypoint":
        return "entrypoint"
    if role == "runtime_module":
        if any(token in code_text for token in ("ast:storage", "ast:state", "ast:worker", "regex:storage", "regex:worker", "regex:queue")):
            return "stateful_runtime"
        if graph_targets or prompt_links:
            return "runtime_service"
        return "library_only"
    if code_signals:
        return "library_only"
    return "none"


def analyze_files(
    repo_path: Path,
    candidate_files: list[Path],
    code_files: list[Path],
    max_file_size_kb: int,
    max_code_files_per_language: int,
    code_file_totals: dict[str, int],
    truncated_languages: list[str],
) -> tuple[list[FileAnalysis], dict[str, list[str]], list[RoleCount], EvidenceSummary, ScanLimits]:
    unique_files = sorted(set(candidate_files + code_files))
    repo_rel_paths = {path.relative_to(repo_path).as_posix() for path in unique_files}
    graph_edges: dict[str, list[str]] = defaultdict(list)
    analyses: list[FileAnalysis] = []

    for file_path in unique_files:
        rel_path = file_path.relative_to(repo_path)
        text = _read_text(file_path)
        language = _language_for_path(rel_path)
        path_signals = _path_signals(rel_path)
        text_signals = _text_signals(text)
        regex_signals = _regex_code_signals(language, text)
        regex_targets = _regex_graph_targets(rel_path, text, language, repo_rel_paths)

        ast_signals = None
        if language == "python":
            ast_signals = analyze_python_ast(rel_path, text, repo_rel_paths)
        elif language in {"javascript", "typescript"}:
            ast_signals = analyze_ts_ast(language, rel_path, text, repo_rel_paths)

        code_signals = _dedupe(regex_signals + (ast_signals.code_signals if ast_signals else []))
        graph_targets = _dedupe(regex_targets + (ast_signals.graph_targets if ast_signals else []))
        prompt_links = ast_signals.prompt_links if ast_signals else []
        negative_signals = _negative_signals(rel_path, text)
        role = _infer_role(rel_path, language, path_signals, text_signals, code_signals, negative_signals, prompt_links)
        runtime_level = _runtime_level(role, code_signals, graph_targets, prompt_links)

        graph_evidence = [f"imports:{target}" for target in graph_targets[:8]]
        graph_evidence.extend(f"links:{target}" for target in prompt_links[:8])
        if graph_targets:
            graph_edges[rel_path.as_posix()].extend(graph_targets)
        if prompt_links:
            graph_edges[rel_path.as_posix()].extend(prompt_links)

        analyses.append(
            FileAnalysis(
                path=rel_path.as_posix(),
                role=role,
                language=language,
                runtime_level=runtime_level,
                path_evidence=[f"path:{item}" for item in path_signals],
                text_evidence=[f"text:{item}" for item in text_signals],
                code_evidence=code_signals,
                graph_evidence=_dedupe(graph_evidence),
                negative_evidence=[f"negative:{item}" for item in negative_signals],
            )
        )

    inbound_counts = Counter(target for targets in graph_edges.values() for target in targets)
    analysis_by_path = {analysis.path: analysis for analysis in analyses}
    for path, count in inbound_counts.items():
        if path in analysis_by_path:
            analysis_by_path[path].graph_evidence.append(f"referenced-by:{count}")
            analysis_by_path[path].graph_evidence = _dedupe(analysis_by_path[path].graph_evidence)

    role_counts = [
        RoleCount(role=role, count=count)
        for role, count in Counter(analysis.role for analysis in analyses).most_common()
    ]
    evidence_summary = EvidenceSummary(
        path_evidence=sum(len(analysis.path_evidence) for analysis in analyses),
        text_evidence=sum(len(analysis.text_evidence) for analysis in analyses),
        code_evidence=sum(len(analysis.code_evidence) for analysis in analyses),
        graph_evidence=sum(len(analysis.graph_evidence) for analysis in analyses),
        negative_evidence=sum(len(analysis.negative_evidence) for analysis in analyses),
    )
    scan_limits = ScanLimits(
        max_file_size_kb=max_file_size_kb,
        max_code_files_per_language=max_code_files_per_language,
        candidate_files_scanned=len(candidate_files),
        code_files_scanned=len(code_files),
        code_files_total=sum(code_file_totals.values()),
        truncated_languages=truncated_languages,
    )
    return sorted(analyses, key=lambda item: item.path), graph_edges, role_counts, evidence_summary, scan_limits


def build_runtime_evidence(file_analyses: list[FileAnalysis]) -> list[EvidenceItem]:
    rank = {"entrypoint": 4, "stateful_runtime": 3, "runtime_service": 2, "library_only": 1, "none": 0}
    items = []
    for analysis in file_analyses:
        if analysis.runtime_level == "none":
            continue
        reasons = (analysis.code_evidence + analysis.graph_evidence)[:5]
        items.append(
            EvidenceItem(
                path=analysis.path,
                label=analysis.role,
                strength=analysis.runtime_level,
                reasons=reasons,
            )
        )
    return sorted(items, key=lambda item: (-rank.get(item.strength, 0), item.path))[:10]


def build_memory_evidence(file_analyses: list[FileAnalysis]) -> list[EvidenceItem]:
    items = []
    for analysis in file_analyses:
        evidence = " ".join(analysis.path_evidence + analysis.text_evidence + analysis.code_evidence + analysis.graph_evidence).lower()
        if analysis.role == "test_or_example":
            continue
        if not any(token in evidence for token in ("memory", "checkpoint", "history", "store", "ast:state", "ast:storage", "regex:storage")):
            continue
        strength = "documented"
        if analysis.role == "state_or_storage":
            strength = "implemented"
        elif analysis.role == "config_or_manifest" and any(
            token in evidence for token in ("memory", "checkpoint", "history", "store")
        ):
            strength = "config"
        elif analysis.role.startswith("runtime") and (
            any(token in evidence for token in ("ast:storage", "ast:state", "regex:storage"))
            or any(token in evidence for token in ("memory", "checkpoint", "history"))
        ):
            strength = "interface"
        items.append(
            EvidenceItem(
                path=analysis.path,
                label=analysis.role,
                strength=strength,
                reasons=(analysis.code_evidence + analysis.text_evidence + analysis.graph_evidence)[:5],
            )
        )
    strength_rank = {"implemented": 4, "interface": 3, "config": 2, "documented": 1}
    return sorted(items, key=lambda item: (-strength_rank.get(item.strength, 0), item.path))[:10]


def build_orchestration_evidence(file_analyses: list[FileAnalysis]) -> list[EvidenceItem]:
    items = []
    for analysis in file_analyses:
        evidence = " ".join(analysis.text_evidence + analysis.code_evidence + analysis.path_evidence + analysis.graph_evidence).lower()
        if analysis.role == "runtime_entrypoint" and analysis.code_evidence:
            items.append(
                EvidenceItem(
                    path=analysis.path,
                    label=analysis.role,
                    strength="runtime",
                    reasons=(analysis.code_evidence + analysis.graph_evidence)[:5],
                )
            )
            continue
        if not any(token in evidence for token in ("workflow", "orchestration", "handoff", "phase", "worker", "queue", "tooling", "scheduler", "control loop")):
            continue
        strength = "prompt-defined"
        if analysis.role in {"runtime_entrypoint", "runtime_module", "state_or_storage"} and analysis.code_evidence:
            strength = "runtime"
        elif analysis.role == "config_or_manifest":
            strength = "tool-assisted"
        items.append(
            EvidenceItem(
                path=analysis.path,
                label=analysis.role,
                strength=strength,
                reasons=(analysis.code_evidence + analysis.text_evidence + analysis.graph_evidence)[:5],
            )
        )
    strength_rank = {"runtime": 4, "tool-assisted": 3, "prompt-defined": 2}
    return sorted(items, key=lambda item: (-strength_rank.get(item.strength, 0), item.path))[:10]


def build_prompt_runtime_links(file_analyses: list[FileAnalysis]) -> list[PromptRuntimeLink]:
    links: list[PromptRuntimeLink] = []
    for analysis in file_analyses:
        if analysis.role not in {"runtime_entrypoint", "runtime_module", "state_or_storage"}:
            continue
        for evidence in analysis.graph_evidence:
            if not evidence.startswith("links:"):
                continue
            target = evidence.split(":", 1)[1]
            links.append(
                PromptRuntimeLink(
                    source_path=analysis.path,
                    target_path=target,
                    kind="runtime-loads-asset",
                    strength="linked",
                    reasons=(analysis.code_evidence + [evidence])[:4],
                )
            )
    seen: set[tuple[str, str]] = set()
    deduped: list[PromptRuntimeLink] = []
    for link in links:
        key = (link.source_path, link.target_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
    return deduped[:20]
