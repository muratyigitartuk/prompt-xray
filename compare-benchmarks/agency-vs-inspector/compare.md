# Prompt-xray Compare: agency-agents vs inspector

## Calls

- **agency-agents**: Prompt pack, not agent runtime.
- **inspector**: Not a prompt-centric repo.

## Headline Difference

- Archetypes: `prompt-library` vs `unclear`
- Orchestration: `prompt-defined` vs `runtime-implemented`
- Memory: `documented-only` vs `implemented-runtime`
- Artifact count: `416` vs `1`

## Tooling Overlap

- Shared tooling: MCP
- agency-agents only: Aider, Claude Code, Copilot, Cursor, Gemini CLI, OpenCode, Windsurf
- inspector only: None

## Top Behavior Sources

### agency-agents
- `specialized/specialized-model-qa.md`
- `specialized/agents-orchestrator.md`
- `project-management/project-management-jira-workflow-steward.md`
- `integrations/mcp-memory/backend-architect-with-memory.md`
- `support/support-legal-compliance-checker.md`

### inspector
- `.mcp.json`

## Verdict

- agency-agents: This is best understood as a prompt-library with prompt-defined orchestration and documented-only memory, not a full runtime-implemented agent system.
- inspector: No major prompt surface was found. This does not look like a prompt-centric agent repo.
