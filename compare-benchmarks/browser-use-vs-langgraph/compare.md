# Prompt-xray Compare: browser-use vs langgraph

## Calls

- **browser-use**: Runtime-first repo with prompt surfaces on top.
- **langgraph**: Real runtime with visible prompt layers.

## Headline Difference

- Archetypes: `mixed` vs `mixed`
- Orchestration: `runtime-implemented` vs `runtime-implemented`
- Memory: `none` vs `implemented-runtime`
- Artifact count: `32` vs `2`

## Tooling Overlap

- Shared tooling: None
- browser-use only: None
- langgraph only: Claude Code

## Top Behavior Sources

### browser-use
- `browser_use/agent/prompts.py`
- `browser_use/agent/system_prompts/system_prompt.md`
- `browser_use/agent/system_prompts/system_prompt_anthropic_flash.md`
- `browser_use/agent/system_prompts/system_prompt_browser_use.md`
- `browser_use/agent/system_prompts/system_prompt_browser_use_flash.md`

### langgraph
- `AGENTS.md`
- `libs/cli/js-examples/README.md`

## Verdict

- browser-use: This repo mixes real implementation with prompt/config behavior surfaces; it is not prompt-only.
- langgraph: This repo mixes real implementation with prompt/config behavior surfaces; it is not prompt-only.
