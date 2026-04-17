# Memory Cache

This directory is the shared source of truth for project memory.

Workflow:

1. Add or update curated Markdown under the appropriate wing directory.
2. Run `harness-workspace/tools/Refresh-MemPalace.ps1`.
3. Query memory through the project MemPalace MCP.

Layout:

- `game_design/` - design and feature docs
- `game_server/` - server-side notes and specs
- `game_client/` - client-side notes and specs
- `game_shared/` - shared architecture, workflows, and cross-cutting docs

Conventions:

- Keep file names stable. Prefer updating an existing file over creating `v2` or `final_final`.
- Put hand-edited knowledge under `manual/`.
- `generated/` is refreshed by `harness-workspace/tools/Sync-MemoryCache.ps1`.
- Do not commit `.mempalace_local/` or local `.codex/` state.
