# prompts/ -- AI System Prompts

Runtime prompt files loaded by `src/prompt_loader.py`. Changes to these files take effect on the next API call -- no server restart needed.

## Files

| File | Used by | Purpose |
|------|---------|---------|
| companion.md | endpoints/companion.py | HUGINN persona, tier enforcement, tool discipline |
| tools.yaml | ai_tools.py | Per-tool descriptions, response_guidance, no_result strings |
| huginn_news.md | huginn_news_task.py | System prompt for Signal broadcast generation |
| TOOLS_YAML_GUIDE.md | (reference) | How to add or edit tools in tools.yaml |

## Editing Tools

Read `TOOLS_YAML_GUIDE.md` before modifying `tools.yaml`. It covers the field reference, tool call sequence, and the procedure for adding new tools.

## How Prompts Are Used

`companion.md` is the system prompt for all AI chat. `tools.yaml` provides per-tool descriptions and guidance injected into the Claude API call alongside the tool schemas. See `docs/ARCHITECTURE.md` -> Prompt Layer for the full flow.
