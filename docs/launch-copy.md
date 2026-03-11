# Launch Copy

## GitHub metadata

**Title**

`prompt-xray`

**Subtitle**

`See what an AI repo actually does.`

**One-line description**

`Scan or compare GitHub repos and get a blunt call: prompt pack, real runtime, mixed system, or not prompt-centric.`

## README hero copy

Use this framing at the top of the repo:

> Prompt-xray scans or compares GitHub repos and local folders, then tells you where the real behavior comes from.
>
> `agency-agents   -> Prompt pack, not agent runtime.`
> `claude-code     -> Real runtime with visible prompt layers.`
> `mcp-inspector   -> Not a prompt-centric repo.`

## X post

Built `prompt-xray`.

Paste any AI repo and it tells you what it actually is:

- prompt pack
- real runtime
- mixed system
- not prompt-centric

No LLM calls. No API keys. Just deterministic prompt archaeology.

Best demo:

`agency-agents -> Prompt pack, not agent runtime.`
`claude-code -> Real runtime with visible prompt layers.`

Repo: `<repo-link>`
Demo: `<app-link>`

## Reddit post

**Title**

I built Prompt-xray: a tool that tells you what an AI repo actually does

**Body**

I kept running into AI repos that were hard to evaluate quickly.

Some are mostly prompt packs.
Some are real runtimes with prompt layers.
Some barely have prompt surfaces at all.

So I built `prompt-xray`.

It scans or compares a GitHub repo and gives a blunt first-pass call:

- `Prompt pack, not agent runtime.`
- `Real runtime with visible prompt layers.`
- `Not a prompt-centric repo.`

It also shows:

- which files actually shape behavior
- whether orchestration is real or just prompt-defined
- whether memory is implemented or only documented
- what is implementation versus packaging

It is deterministic and costless to run locally:

- no API keys
- no LLM calls
- no GitHub API

Best comparison so far:

- `agency-agents` vs `claude-code`

That one makes the product click immediately.

Repo: `<repo-link>`
Demo: `<app-link>`

Would be useful to know where the calls feel wrong or too soft.

## Hacker News post

**Title**

Show HN: Prompt-xray - see what an AI repo actually does

**Body**

Prompt-xray is a deterministic scanner for AI repos.

Give it a GitHub repo or compare two repos and it tries to answer:

- what this repo really is
- which files shape behavior
- whether orchestration is implemented or just described
- whether memory is real or doc-level
- what is real implementation versus packaging

The core idea is prompt archaeology rather than generic repo analysis.

Example:

- `agency-agents -> Prompt pack, not agent runtime.`
- `claude-code -> Real runtime with visible prompt layers.`
- `mcp-inspector -> Not a prompt-centric repo.`

There are no LLM calls or API dependencies in the analysis path right now. It is all deterministic heuristics over the repo contents.

Repo: `<repo-link>`
Demo: `<app-link>`
