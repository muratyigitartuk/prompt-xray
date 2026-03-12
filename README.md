# Prompt-xray

**See what an AI repo actually does.**

Prompt-xray scans or compares GitHub repos and local folders, then reports where the behavior of an AI system is really defined. It is built for repos where prompts, skills, rules, docs, integrations, and runtime code are mixed together.

It now includes a pinned benchmark corpus, parser-backed Python and TS/JS analysis, confidence scoring, contradiction detection, and prompt/runtime linkage reporting.

It uses deterministic heuristics only:

- no API keys
- no LLM calls
- no GitHub API

Typical output:

```text
agency-agents          -> Prompt pack, not agent runtime.
claude-code            -> Real runtime with visible prompt layers.
openai-agents-python   -> Real runtime with visible prompt layers.
```

## What it does

For a single repo, Prompt-xray tells you:

- what the repo most likely is
- which files shape behavior
- whether orchestration is implemented or only described
- whether memory is runtime-backed or only documented
- what looks like implementation versus packaging
- how confident the classifier is
- where claims and implementation diverge
- whether runtime code actually loads prompt/config assets

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
- inspect the repo family, confidence, contradictions, orchestration, and memory classification
- browse a small curated set of sample scans and comparisons

## Command reference

```bash
prompt-xray scan <target> [--out <dir>] [--format markdown|json|both] [--html]
prompt-xray compare <left> <right> [--out <dir>] [--format markdown|json|both] [--html]
prompt-xray bench run [--cases-dir <dir>] [--split calibration|holdout|all] [--out <dir>]
prompt-xray bench diff <left-benchmark.json> <right-benchmark.json> [--out <dir>]
prompt-xray bench report <benchmark.json>
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

Benchmark examples:

```bash
prompt-xray bench run --split calibration --out .prompt-xray/bench/calibration
prompt-xray bench run --split holdout --out .prompt-xray/bench/holdout
prompt-xray bench run --split holdout --subset --out .prompt-xray/bench/reduced-holdout
prompt-xray bench report .prompt-xray/bench/holdout/benchmark.json
prompt-xray bench diff .prompt-xray/bench/before/benchmark.json .prompt-xray/bench/after/benchmark.json
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

Each benchmark run can write:

- `benchmark.md`
- `benchmark.json`

Each benchmark diff can write:

- `benchmark-diff.md`
- `benchmark-diff.json`

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
## Confidence And Uncertainty
## Evidence Summary
## Artifact Inventory
## Verdict
```

## Example results

### `agency-agents`

```text
Family: prompt-pack
Archetype: prompt-library
Orchestration: prompt-defined
Memory: none
Call: Prompt pack, not agent runtime.
```

### `claude-code`

```text
Family: plugin-ecosystem
Archetype: agent-framework
Orchestration: runtime-implemented
Memory: tool-assisted
Call: Real runtime with visible prompt layers.
```

### `openai-agents-python`

```text
Family: runtime-framework
Archetype: agent-framework
Orchestration: runtime-implemented
Memory: implemented-runtime
Call: Real runtime with visible prompt layers.
```

## Benchmark corpus

The repo ships with a pinned corpus under [`benchmarks/cases`](./benchmarks/cases):

- 49 public repos
- 34 calibration repos and 15 frozen holdout repos
- prompt packs, workflow packs, runtime frameworks, SDKs, plugin ecosystems, infra/tooling, docs/examples, and negative controls
- expected repo family, archetype, orchestration, memory, confidence tier, split, ambiguity policy, and optional allowed labels per case

Calibration cases are for tuning. Holdout cases are for honesty on unseen shapes.

Checked-in baselines live under [`benchmarks/baselines`](./benchmarks/baselines):

- `calibration/benchmark.json` and `calibration/benchmark.md`
- `holdout/benchmark.json` and `holdout/benchmark.md`
- `full/benchmark.json` and `full/benchmark.md`
- `reduced-calibration/benchmark.json` and `reduced-calibration/benchmark.md`
- `reduced-holdout/benchmark.json` and `reduced-holdout/benchmark.md`

The reduced calibration and reduced holdout baselines are the fast CI gates. The split full baselines and combined full baseline are the slower `main` and manual benchmark gates.

## Confidence and contradictions

Prompt-xray now reports:

- confidence per family, archetype, orchestration, memory, and overall call
- claim/implementation contradictions
- runtime-to-prompt/config linkage
- provisional labels, constraint adjustments, and a final decision trace

Interpretation:

- `high` confidence means multiple evidence classes agree on the same call
- `medium` confidence means the direction is useful but still mixed
- `low` confidence means the repo should be treated as ambiguous
- contradictions are the fastest way to spot "claims X, implements less than X"

## How it works

Prompt-xray runs a static analysis pipeline:

1. resolve a local folder or clone a GitHub repo with `git clone --depth 1`
2. collect candidate prompt, rule, config, and documentation files
3. build file-role, evidence, and lightweight graph models
4. parse Python and TS/JS structure to detect entrypoints, services, storage/state, workers, and asset loads
5. assign provisional labels, resolve family-policy and confidence constraints, then score the final state
6. render Markdown, JSON, and optional HTML reports

It looks for signals such as:

- agent and prompt files
- skills and rule files
- tool-specific integrations like Cursor, Claude Code, Copilot, Windsurf, and Gemini CLI
- orchestration markers such as handoff, phases, gates, and retry loops
- memory markers in docs, config, and runtime paths
- runtime code that suggests actual implementation rather than documentation alone
- links where runtime modules actually load prompt/config assets

## Limitations

Prompt-xray is useful as a first-pass analysis tool, not as a formal verifier.

- it relies on heuristics rather than execution
- non-Python/non-TS repos still rely more on heuristic than parser-backed analysis
- large mixed repos are harder to classify cleanly than prompt-heavy repos
- benchmark expectations are curated and may need revision as repos evolve
- generated, vendored, binary, and oversized files are skipped

## Development

Run tests:

```bash
python -m pytest -q
```

Maintainer workflow:

```bash
prompt-xray bench run --split calibration --out .prompt-xray/bench/calibration
prompt-xray bench run --split holdout --out .prompt-xray/bench/holdout
prompt-xray bench diff benchmarks/baselines/holdout/benchmark.json .prompt-xray/bench/holdout/benchmark.json
prompt-xray scan https://github.com/msitarzewski/agency-agents --out samples/reports/agency-agents --format json
```

Only refresh `samples/` or `benchmarks/baselines/` when:

- benchmark metrics improve, or
- benchmark expectations/calibration notes were intentionally updated
