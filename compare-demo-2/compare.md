# Prompt-xray Compare: agency-agents vs claude-code

## Calls

- **agency-agents**: Prompt pack, not agent runtime.
- **claude-code**: Real runtime with visible prompt layers.

## Headline Difference

- Archetypes: `prompt-library` vs `mixed`
- Orchestration: `prompt-defined` vs `runtime-implemented`
- Memory: `documented-only` vs `documented-only`
- Artifact count: `416` vs `90`

## Tooling Overlap

- Shared tooling: Claude Code
- agency-agents only: Aider, Copilot, Cursor, Gemini CLI, MCP, OpenCode, Windsurf
- claude-code only: None

## Top Behavior Sources

### agency-agents
- `specialized/specialized-model-qa.md`
- `specialized/agents-orchestrator.md`
- `project-management/project-management-jira-workflow-steward.md`
- `integrations/mcp-memory/backend-architect-with-memory.md`
- `support/support-legal-compliance-checker.md`

### claude-code
- `plugins/plugin-dev/skills/agent-development/SKILL.md`
- `plugins/plugin-dev/skills/agent-development/references/system-prompt-design.md`
- `plugins/claude-opus-4-5-migration/skills/claude-opus-4-5-migration/SKILL.md`
- `plugins/plugin-dev/agents/agent-creator.md`
- `plugins/plugin-dev/agents/plugin-validator.md`

## Verdict

- agency-agents: This is best understood as a prompt-library with prompt-defined orchestration and documented-only memory, not a full runtime-implemented agent system.
- claude-code: This repo mixes real implementation with prompt/config behavior surfaces; it is not prompt-only.
