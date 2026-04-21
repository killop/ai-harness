# Memory Cache

This directory is the shared source of truth for project memory.

Workflow:

1. Add or update curated Markdown under the appropriate wing directory.
2. Run `python harness-workspace/tools/mempalace_tools.py daemon --run-once`.
3. Query memory through the project MemPalace MCP.

Refresh behavior:

- The managed palace now uses blue-green incremental refresh.
- Only changed wings are re-mined on normal runs.
- Deleted files are purged from the copied active version before cutover.
- If a wing's `mempalace.yaml` changes, that wing is reset and re-mined.
- The first run after introducing this mechanism may still do one full refresh to create `source_snapshot.json`.

Layout:

- `game_design/` - design and feature docs
- `game_server/` - server-side notes and specs
- `game_client/` - client-side notes and specs
- `game_shared/` - shared architecture, workflows, and cross-cutting docs

Conventions:

- Keep file names stable. Prefer updating an existing file over creating `v2` or `final_final`.
- Put hand-edited knowledge under `manual/`.
- The daemon and refresh commands now watch this directory directly instead of rebuilding from external sync maps.
- For live-safe palace updates, prefer `daemon --run-once` over writing directly into the managed palace root.
- Do not commit `.mempalace_local/` or local `.codex/` state.
