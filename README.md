# Prompt-xray

**See what an AI repo actually does.**

Prompt-xray scans or compares GitHub repos and local folders, then reports where the behavior of an AI system is really defined. It is built for repos where prompts, skills, rules, docs, integrations, and runtime code are mixed together.

It uses deterministic heuristics only:

- no API keys
- no LLM calls
- no GitHub API

Typical output:

```text
agency-agents   -> Prompt pack, not agent runtime.
claude-code     -> Real runtime with visible prompt layers.
mcp-inspector   -> Not a prompt-centric repo.
```

## What it does

For a single repo, Prompt-xray tells you:

- what the repo most likely is
- which files shape behavior
- whether orchestration is implemented or only described
- whether memory is runtime-backed or only documented
- what looks like implementation versus packaging

For two repos, it shows the differences side by side.

## Install

```bash
pip install -e .
```

## Quick start

Scan one repo:

```bash
prompt-xray scan https://github.com/msitarzewski/agency-agents
prompt-xray scan ../agency-agents --html
```

Compare two repos:

```bash
prompt-xray compare \
  https://github.com/msitarzewski/agency-agents \
  https://github.com/anthropics/claude-code --html
```

Serve the web UI:

```bash
prompt-xray serve --host 127.0.0.1 --port 8765
```

Then open [http://127.0.0.1:8765/](http://127.0.0.1:8765/).

By default, generated files are written under `.prompt-xray/<repo-slug>/`.

## Web UI

The included web app exposes the same functionality as the CLI:

- scan a local path or GitHub repo
- compare two local paths or GitHub repos
- inspect the repo call, behavior sources, orchestration, and memory classification
- browse saved sample scans and comparisons

## Command reference

```bash
prompt-xray scan <target> [--out <dir>] [--format markdown|json|both] [--html]
prompt-xray compare <left> <right> [--out <dir>] [--format markdown|json|both] [--html]
prompt-xray serve [--host 127.0.0.1] [--port 8765]
```

Useful scan examples:

```bash
prompt-xray scan https://github.com/msitarzewski/agency-agents
prompt-xray scan ../agency-agents --out reports/agency-agents
prompt-xray scan ../agency-agents --format json
prompt-xray scan https://github.com/msitarzewski/agency-agents --html
```

Useful compare examples:

```bash
prompt-xray compare https://github.com/msitarzewski/agency-agents https://github.com/anthropics/claude-code
prompt-xray compare https://github.com/browser-use/browser-use https://github.com/langchain-ai/langgraph --html
```

## Output

Each scan can write:

- `report.md`
- `report.json`
- `report.html` when `--html` is passed

Each comparison can write:

- `compare.md`
- `compare.json`
- `compare.html` when `--html` is passed

The Markdown report uses this structure:

```md
# Prompt-xray Report: <repo>

## What This Repo Is
## Prompt Surface Map
## Behavior Sources
## Tooling And Integrations
## Orchestration And Memory
## Real Versus Packaging
## Missing Pieces
## Artifact Inventory
## Verdict
```

## Example results

### `agency-agents`

```text
Archetype: prompt-library
Orchestration: prompt-defined
Memory: documented-only
Call: Prompt pack, not agent runtime.
```

### `claude-code`

```text
Archetype: mixed
Orchestration: runtime-implemented
Memory: documented-only
Call: Real runtime with visible prompt layers.
```

### `browser-use`

```text
Archetype: mixed
Orchestration: runtime-implemented
Memory: none
Call: Real runtime with visible prompt layers.
```

## Comparison snapshot

Generated from Prompt-xray runs on March 11, 2026.

| Repo | Archetype | Orchestration | Memory | Artifacts | Summary |
| --- | --- | --- | --- | ---: | --- |
| `msitarzewski/agency-agents` | `prompt-library` | `prompt-defined` | `documented-only` | 416 | Prompt-heavy library with packaging logic, not a runtime agent system. |
| `anthropics/claude-code` | `mixed` | `runtime-implemented` | `documented-only` | 90 | Real product/runtime with visible skill and prompt layers. |
| `browser-use/browser-use` | `mixed` | `runtime-implemented` | `none` | 32 | Runtime-first repo with prompt files that still shape behavior. |
| `openai/openai-agents-python` | `mixed` | `runtime-implemented` | `implemented-runtime` | 302 | Framework/runtime plus strong internal skill and instruction surfaces. |
| `crewAIInc/crewAI` | `mixed` | `runtime-implemented` | `implemented-runtime` | 317 | Large runtime framework with a lot of prompt and doc-level behavior clues. |
| `langchain-ai/langgraph` | `mixed` | `runtime-implemented` | `none` | 2 | Mostly runtime from Prompt-xray's perspective with very little prompt surface. |
| `modelcontextprotocol/servers` | `mixed` | `runtime-implemented` | `implemented-runtime` | 9 | Implementation repo with limited prompt surface and clear MCP/runtime signals. |
| `modelcontextprotocol/inspector` | `unclear` | `runtime-implemented` | `none` | 1 | Useful negative control for non prompt-centric AI tooling. |

## How it works

Prompt-xray runs a static analysis pipeline:

1. resolve a local folder or clone a GitHub repo with `git clone --depth 1`
2. collect candidate prompt, rule, config, and documentation files
3. extract prompt-like artifacts and file-level signals
4. classify the repo using deterministic heuristics
5. render Markdown, JSON, and optional HTML reports

It looks for signals such as:

- agent and prompt files
- skills and rule files
- tool-specific integrations like Cursor, Claude Code, Copilot, Windsurf, and Gemini CLI
- orchestration markers such as handoff, phases, gates, and retry loops
- memory markers in docs, config, and runtime paths
- runtime code that suggests actual implementation rather than documentation alone

## Limitations

Prompt-xray is useful as a first-pass analysis tool, not as a formal verifier.

- it relies on heuristics rather than execution
- large mixed repos are harder to classify cleanly than prompt-heavy repos
- runtime and memory detection are directional, not guaranteed
- generated, vendored, binary, and oversized files are skipped

## Development

Run tests:

```bash
python -m pytest -q
```

Launch copy for GitHub, X, Reddit, and HN is in [docs/launch-copy.md](docs/launch-copy.md).
