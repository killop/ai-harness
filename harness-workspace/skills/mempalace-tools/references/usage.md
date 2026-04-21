# MemPalace Tools Usage

This reference describes the local MemPalace workflow for `harness-workspace/`.

## Canonical Python Paths

After setup, treat the repo-local `.venv` as the default runner.

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3
```

Use system `python` or `python3` only for the first `setup` when `.venv` does not exist yet.

## Command Matrix

All commands below assume the current directory is `harness-workspace/`.

### Setup

Windows:

```powershell
python .\tools\mempalace_tools.py setup
```

macOS / Linux:

```bash
python3 ./tools/mempalace_tools.py setup
```

### Refresh Once In Foreground

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py refresh
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py refresh
```

### Install Local Codex MCP

This writes or updates the MemPalace server entry in the current project's `.codex/config.toml`.
Current stage only supports the local Codex config. It does not install Claude, Cursor, or other agent hosts yet.

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py install-agent-mcp
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py install-agent-mcp
```

Behavior:

- creates `.codex/config.toml` if it does not exist
- upserts the `mcp_servers.mempalace` section instead of replacing the whole file
- keeps other unrelated `.codex/config.toml` sections intact

### Run The Daemon

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py daemon
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py daemon
```

With the current repo defaults, a common command is:

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py daemon --debounce-seconds 3 --keep-versions 3
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py daemon --debounce-seconds 3 --keep-versions 3
```

### Run One Daemon Pass

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py daemon --run-once
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py daemon --run-once
```

### Start MCP

Windows:

```powershell
.\mempalace-github-code\.venv\Scripts\python.exe .\tools\mempalace_tools.py start-mcp
```

macOS / Linux:

```bash
./mempalace-github-code/.venv/bin/python3 ./tools/mempalace_tools.py start-mcp
```

## Managed Palace Design

- Logical root: `harness-workspace/.mempalace_local/palace`
- Active pointer: `harness-workspace/.mempalace_local/palace/current.json`
- Version store: `harness-workspace/.mempalace_local/palace/versions/`
- Daemon state: `harness-workspace/.mempalace_local/refresh-daemon/state.json`
- Daemon log: `harness-workspace/.mempalace_local/refresh-daemon/daemon.log`

Normal refresh behavior:

1. Detect changes under `knowledges-cache/`.
2. Copy the current active palace as a seed when possible.
3. Re-mine only changed wings.
4. Purge deleted files from the staged version.
5. Update `current.json` after the staged version is ready.

## Troubleshooting

### `start-mcp` fails before startup

Check:

- `.venv` exists under `harness-workspace/mempalace-github-code/.venv`
- `.codex/config.toml` points to the repo-local `.venv` Python
- `harness-workspace/tools/mempalace_tools.py start-mcp` is the configured entrypoint
- rerun `install-agent-mcp` if the local Codex config drifted

### `daemon` says another process is running

Check:

- `harness-workspace/.mempalace_local/refresh-daemon/daemon.lock`
- `harness-workspace/.mempalace_local/refresh-daemon/state.json`
- whether the pid in the lock file is still alive

### Refresh appears to do nothing

Check:

- the changed file is under a wing directory that has `mempalace.yaml`
- the file was actually saved to disk
- daemon debounce has elapsed
- the change appears in `daemon.log`
- `refresh` or `daemon --run-once` reports a changed wing instead of `No knowledge changes detected`
