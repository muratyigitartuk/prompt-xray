from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass, field
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=r"Language\(path, name\) is deprecated\. Use Language\(ptr, name\) instead\.",
    category=FutureWarning,
    module="tree_sitter",
)

from tree_sitter_languages import get_parser

PROMPT_ASSET_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
_TS_PARSERS = {
    "javascript": get_parser("javascript"),
    "typescript": get_parser("typescript"),
}


@dataclass
class ASTSignals:
    code_signals: list[str] = field(default_factory=list)
    graph_targets: list[str] = field(default_factory=list)
    prompt_links: list[str] = field(default_factory=list)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _resolve_relative_import(base: Path, target: str, repo_rel_paths: set[str]) -> str | None:
    raw = (base.parent / target).as_posix()
    candidates = [raw]
    for suffix in (".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml", ".md", ".txt"):
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


def _resolve_asset_path(base: Path, value: str, repo_rel_paths: set[str]) -> str | None:
    if not value:
        return None
    if value.startswith(("./", "../")):
        return _resolve_relative_import(base, value, repo_rel_paths)
    direct = value.replace("\\", "/").lstrip("/")
    if direct in repo_rel_paths:
        return direct
    by_name = {Path(item).name: item for item in repo_rel_paths}
    return by_name.get(Path(value).name)


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return ""


def _constant_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _path_call_string(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    call_name = _dotted_name(node.func).lower()
    if call_name not in {"path", "pathlib.path", "purepath", "pathlib.purepath"}:
        return ""
    if not node.args:
        return ""
    return _constant_string(node.args[0])


def analyze_python_ast(rel_path: Path, text: str, repo_rel_paths: set[str]) -> ASTSignals:
    result = ASTSignals()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and test.comparators
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                result.code_signals.append("ast:entrypoint")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                target = _resolve_python_module(rel_path, node.module if node.level == 0 else f"{'.' * node.level}{node.module}", repo_rel_paths)
                if target:
                    result.graph_targets.append(target)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_python_module(rel_path, alias.name, repo_rel_paths)
                if target:
                    result.graph_targets.append(target)
        elif isinstance(node, ast.Call):
            call_name = _dotted_name(node.func).lower()
            if call_name in {"fastapi", "apirouter", "flask", "django.setup", "get_wsgi_application"}:
                result.code_signals.append("ast:web-service")
                result.code_signals.append("ast:entrypoint")
            if call_name in {"typer.typer", "click.command", "click.group", "argumentparser"}:
                result.code_signals.append("ast:cli")
                result.code_signals.append("ast:entrypoint")
            if any(token in call_name for token in ("celery", "apscheduler", "backgroundtasks", "create_task")):
                result.code_signals.append("ast:worker")
            if any(token in call_name for token in ("sqlite3.connect", "redis", "sqlalchemy", "create_engine", "sessionlocal")):
                result.code_signals.append("ast:storage")
                result.code_signals.append("ast:state")
            if call_name.endswith(("read_text", "read_bytes", "open")) and node.args:
                path_value = _constant_string(node.args[0])
                if Path(path_value).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                    target = _resolve_asset_path(rel_path, path_value, repo_rel_paths)
                    if target:
                        result.prompt_links.append(target)
            elif call_name.endswith(("read_text", "read_bytes")) and isinstance(node.func, ast.Attribute):
                path_value = _path_call_string(node.func.value)
                if Path(path_value).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                    target = _resolve_asset_path(rel_path, path_value, repo_rel_paths)
                    if target:
                        result.prompt_links.append(target)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                name = _dotted_name(target).lower()
                if any(token in name for token in ("checkpoint", "history", "session", "store", "memory", "state")):
                    result.code_signals.append("ast:state")
        elif isinstance(node, ast.ClassDef):
            class_name = node.name.lower()
            if any(token in class_name for token in ("checkpoint", "history", "session", "store", "memory", "state")):
                result.code_signals.append("ast:state")

    result.code_signals = _dedupe(result.code_signals)
    result.graph_targets = _dedupe(result.graph_targets)
    result.prompt_links = _dedupe(result.prompt_links)
    return result


def _iter_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def analyze_ts_ast(language: str, rel_path: Path, text: str, repo_rel_paths: set[str]) -> ASTSignals:
    parser = _TS_PARSERS[language]
    source_bytes = text.encode("utf-8")
    tree = parser.parse(source_bytes)
    result = ASTSignals()

    for node in _iter_nodes(tree.root_node):
        node_type = node.type
        snippet = _node_text(node, source_bytes)
        snippet_lower = snippet.lower()

        if node_type in {"import_statement", "export_statement"}:
            for quote in ("'", '"'):
                if quote in snippet:
                    parts = snippet.split(quote)
                    for candidate in parts[1::2]:
                        if candidate.startswith(("./", "../")):
                            resolved = _resolve_relative_import(rel_path, candidate, repo_rel_paths)
                            if resolved:
                                result.graph_targets.append(resolved)
                        elif Path(candidate).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                            resolved = _resolve_asset_path(rel_path, candidate, repo_rel_paths)
                            if resolved:
                                result.prompt_links.append(resolved)
        elif node_type in {"call_expression", "new_expression"}:
            if any(token in snippet_lower for token in ("express(", "fastify(", "nestfactory.create", "nextresponse", "nextrequest")):
                result.code_signals.extend(["ast:web-service", "ast:entrypoint"])
            if any(token in snippet_lower for token in ("commander", "yargs", "cac")):
                result.code_signals.extend(["ast:cli", "ast:entrypoint"])
            if any(token in snippet_lower for token in ("bullmq", "worker", "agenda", "setinterval", "queuemicrotask")):
                result.code_signals.append("ast:worker")
            if any(token in snippet_lower for token in ("redis", "prisma", "typeorm", "sequelize", "checkpoint", "session", "history", "store")):
                result.code_signals.extend(["ast:storage", "ast:state"])
            for quote in ("'", '"'):
                if quote in snippet:
                    parts = snippet.split(quote)
                    for candidate in parts[1::2]:
                        if candidate.startswith(("./", "../")):
                            resolved = _resolve_relative_import(rel_path, candidate, repo_rel_paths)
                            if resolved:
                                if Path(candidate).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                                    result.prompt_links.append(resolved)
                                else:
                                    result.graph_targets.append(resolved)
                        elif Path(candidate).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                            resolved = _resolve_asset_path(rel_path, candidate, repo_rel_paths)
                            if resolved:
                                result.prompt_links.append(resolved)
        elif node_type == "string":
            literal = snippet.strip("\"'")
            if Path(literal).suffix.lower() in PROMPT_ASSET_EXTENSIONS:
                resolved = _resolve_asset_path(rel_path, literal, repo_rel_paths)
                if resolved:
                    result.prompt_links.append(resolved)

    if result.prompt_links:
        result.code_signals.append("ast:loads-prompt-asset")
    result.code_signals = _dedupe(result.code_signals)
    result.graph_targets = _dedupe(result.graph_targets)
    result.prompt_links = _dedupe(result.prompt_links)
    return result
