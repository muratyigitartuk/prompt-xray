from __future__ import annotations

from pathlib import Path

TEXT_EXTENSIONS = {".md", ".mdc", ".txt", ".yaml", ".yml", ".json", ".toml"}
SPECIAL_FILENAMES = {
    "agents.md",
    "skill.md",
    "soul.md",
    ".windsurfrules",
    ".clinerules",
    "copilot-instructions.md",
}
SPECIAL_PREFIXES = ("readme", "system", "prompt")
SPECIAL_PATH_PARTS = {
    "agents",
    "prompts",
    "instructions",
    "integrations",
    "workflows",
}
NOISE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}
NOISE_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
}
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".sh",
}


def _is_binary(file_path: Path) -> bool:
    try:
        chunk = file_path.read_bytes()[:1024]
    except OSError:
        return True
    return b"\x00" in chunk


def _should_include(rel_path: Path, file_path: Path) -> bool:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    parts = {part.lower() for part in rel_path.parts}

    if name in NOISE_FILES:
        return False
    if suffix in TEXT_EXTENSIONS:
        return True
    if name in SPECIAL_FILENAMES:
        return True
    if any(name.startswith(prefix) for prefix in SPECIAL_PREFIXES):
        return True
    if SPECIAL_PATH_PARTS.intersection(parts):
        return True
    if rel_path.parts[:2] == (".cursor", "rules"):
        return True
    if rel_path.as_posix() == ".github/copilot-instructions.md":
        return True
    return False


def discover_candidate_files(repo_path: Path, max_file_size_kb: int) -> list[Path]:
    max_bytes = max_file_size_kb * 1024
    candidates: list[Path] = []

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(repo_path)
        parts_lower = {part.lower() for part in rel_path.parts}
        if NOISE_DIRS.intersection(parts_lower):
            continue

        if not _should_include(rel_path, file_path):
            continue

        try:
            if file_path.stat().st_size > max_bytes:
                continue
        except OSError:
            continue

        if _is_binary(file_path):
            continue

        candidates.append(file_path)

    return sorted(candidates)


def discover_runtime_markers(repo_path: Path, max_scan_files: int = 5000) -> list[str]:
    markers: list[str] = []
    scanned = 0

    for file_path in repo_path.rglob("*"):
        if scanned >= max_scan_files:
            break
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(repo_path)
        parts_lower = {part.lower() for part in rel_path.parts}
        if NOISE_DIRS.intersection(parts_lower):
            continue

        scanned += 1
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()
        rel_posix = rel_path.as_posix().lower()

        if name == "dockerfile":
            markers.append(rel_path.as_posix())
            continue

        if suffix not in CODE_EXTENSIONS and name not in {"package.json", "pyproject.toml"}:
            continue

        if any(part in rel_posix for part in ("src/", "server/", "backend/", "api/", "app/")):
            markers.append(rel_path.as_posix())
            continue

        if name.startswith(("main.", "app.", "server.")):
            markers.append(rel_path.as_posix())

    return sorted(set(markers))
