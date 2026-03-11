# Prompt-xray Benchmark Run

- Generated at: 2026-03-11T21:27:17.617226+00:00
- Cases: 35
- Baseline name: full
- Family exact matches: 7/35
- Archetype exact matches: 8/35
- Orchestration exact matches: 19/35
- Memory exact matches: 10/35
- Low-confidence cases: 1

## Major regressions

- `anthropic-cookbook`
- `anthropic-sdk-python`
- `anthropic-sdk-typescript`
- `autogen`
- `autogpt`
- `browser-use`
- `chatdev`
- `dspy`
- `fastmcp`
- `gradio`
- `langchain`
- `langgraph`
- `litellm`
- `llama-index`
- `mcp-inspector`
- `mcp-python-sdk`
- `mcp-servers`
- `mcp-typescript-sdk`
- `open-interpreter`
- `openai-cookbook`
- `openai-node`
- `openai-python`
- `potpie`
- `promptsource`
- `semantic-kernel`
- `transformers`
- `vercel-ai`

## Case errors

- `openai-cookbook`: CalledProcessError: Command '['git', 'checkout', '--detach', 'c2d6fbe04fa19709ededb1e617d9a7fa5aec6cdb']' returned non-zero exit status 1.

## Family confusions

- `application-repo -> plugin-ecosystem`: 1
- `application-repo -> runtime-framework`: 5
- `docs-examples -> application-repo`: 1
- `docs-examples -> error`: 1
- `infra-tooling -> application-repo`: 2
- `infra-tooling -> runtime-framework`: 1
- `prompt-pack -> application-repo`: 1
- `runtime-framework -> application-repo`: 3
- `sdk-library -> application-repo`: 6
- `sdk-library -> plugin-ecosystem`: 2
- `sdk-library -> runtime-framework`: 5

## Archetype confusions

- `agent-framework -> mixed`: 3
- `mixed -> agent-framework`: 6
- `prompt-library -> mixed`: 1
- `unclear -> agent-framework`: 5
- `unclear -> error`: 1
- `unclear -> mixed`: 11

## Orchestration confusions

- `none -> error`: 1
- `none -> runtime-implemented`: 15

## Memory confusions

- `documented-only -> implemented-runtime`: 4
- `none -> error`: 1
- `none -> implemented-runtime`: 20
