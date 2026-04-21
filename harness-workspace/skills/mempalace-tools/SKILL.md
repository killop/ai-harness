---
name: mempalace-tools
description: Use when operating the local MemPalace workspace under `harness-workspace/`, especially for setup, installing the local Codex MCP entry, refresh, daemon runs, MCP startup, or troubleshooting the project-local palace and repo-local `.venv` workflow.
metadata:
  short-description: Operate the local MemPalace workspace
---

# MemPalace Tools

Use this skill for the local MemPalace toolchain in `harness-workspace/`. It covers bootstrap, local Codex MCP installation, refresh, daemon, MCP startup, and troubleshooting for the managed palace at `harness-workspace/.mempalace_local/palace`.

## Quick Rules

- Use `harness-workspace/tools/mempalace_tools.py` as the single entrypoint.
- Prefer the repo-local Python in `harness-workspace/mempalace-github-code/.venv` for every command after setup.
- Use system `python` or `python3` only for the first `setup` on a machine where `.venv` does not exist yet.
- If the user wants the project agent to discover MemPalace automatically, run `install-agent-mcp` to update the local `.codex/config.toml`.
- The managed palace is blue-green: refresh writes a new version under `.mempalace_local/palace/versions/` and moves `current.json` on cutover.
- The daemon watches `harness-workspace/knowledges-cache/` directly. Do not reintroduce old sync-map assumptions.

## Workflow

### 1. Bootstrap

If `.venv` is missing, run `setup` once with the machine Python.

Windows:

```powershell
python .\tools\mempalace_tools.py setup
```

macOS / Linux:

```bash
python3 ./tools/mempalace_tools.py setup
```

### 2. Install The Local Codex MCP Entry

Current scope: this skill installs MemPalace into the current project's `.codex/config.toml`.

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py install-agent-mcp
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py install-agent-mcp
```

Use this whenever the user says the local agent should "see", "load", or "mount" the MemPalace MCP automatically.

### 3. Use The Repo Venv For Everything Else

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py <command>
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py <command>
```

### 4. Pick The Right Command

- `install-agent-mcp`: install or update the local Codex MCP entry in `.codex/config.toml`
- `refresh`: run a foreground refresh now
- `daemon`: keep polling `knowledges-cache/` and refresh after changes stabilize
- `daemon --run-once`: do one daemon-style pass without staying resident
- `start-mcp`: start the local MemPalace MCP server against the managed palace root
- `rebuild`: rebuild an unmanaged palace from scratch

## Default Operating Pattern

1. Run `setup` if `.venv` does not exist yet.
2. Run `install-agent-mcp` if the local Codex config is missing or drifted.
3. Update Markdown under `harness-workspace/knowledges-cache/`.
4. Run `daemon --run-once` or let the daemon pick up changes.
5. Start or restart MCP with `start-mcp` if needed.
6. Query memory through MCP tools.

## What To Load Next

- Load [references/usage.md](references/usage.md) for the concrete command matrix, important paths, and troubleshooting checks.
