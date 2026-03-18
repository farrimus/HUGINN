# Documentation Manifest

Auto-maintained by doc-doctor protocol.

## Directory Structure

```
.claude/docs/
├── MANIFEST.md (this file)
├── modules/ (agent-facing module docs, ≤150 lines each)
│   ├── index.md (TOC and quick navigation)
│   ├── auth.md
│   ├── claude_client.md
│   ├── context_builder.md
│   ├── deal_store.md
│   ├── endpoints.md
│   ├── galaxy_db.md
│   ├── location_index.md
│   ├── log_buffer.md
│   ├── memory_store.md
│   ├── nova_client.md
│   ├── radius_search.md
│   ├── route_engine.md
│   ├── ship_profile.md
│   ├── ssu_poller.md
│   ├── structure_auth.md
│   ├── structure_client.md
│   ├── structure_profile.md
│   ├── token_manager.md
│   ├── type_names.md
│   └── world_api.md
├── references/ (detailed docs deferred from modules/)
│   └── (to be populated as needed)
└── assets/ (data formats, constants, diagrams)
    └── (to be populated as needed)
```

## Module Documentation Format

Each module doc (`modules/[name].md`) includes:

1. **When Should an Agent Use This Module?** — Decision tree to select correct module
2. **Public API** — Function/class signatures with brief descriptions
3. **Behavior** — Truth tables or sequential descriptions of operations
4. **Constants/Configuration** — Game-canonical values, tuning parameters
5. **Integration Points** — Data flow (input sources, output consumers, dependencies)

**Line limit:** ≤150 lines (≤180 hard max). Heavy content deferred to references/ or assets/.

## Maintenance

- **Change detection:** doc-doctor monitors MD5 checksums of module source files
- **Auto-generation:** Run `/doc-doctor` skill to detect new/changed/stale modules
- **Orphan cleanup:** doc-doctor deletes docs for modules that no longer exist
- **No manual editing:** Module docs are auto-generated; edit source files instead

## Related Documentation

- **Architecture:** `/opt/eve-frontier/docs/CODEBASE.md`
- **Log pipeline:** `/opt/eve-frontier/docs/log-pipeline.md`
- **Routing:** `/opt/eve-frontier/docs/ref/routing.md`
- **Ship AI:** `/opt/eve-frontier/docs/ref/ship-ai.md`
- **Structure AI:** `/opt/eve-frontier/docs/ref/structure-ai.md`
- **Lore & intent:** `/opt/eve-frontier/intent.md`

## Generated

- **Generated:** 2026-03-18 by doc-doctor protocol
- **Git hash:** c2ae7ff9dd74646b17cda8c076e3f9a5e47e5119
- **Total modules:** 20
- **Total docs:** 21 (20 modules + 1 index)
- **Quality:** All pass audit (line count, required sections, formatting)
