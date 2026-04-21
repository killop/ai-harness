#!/usr/bin/env python3
"""Cross-platform MemPalace workspace tools."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence


@dataclass(frozen=True)
class FileStamp:
    mtime_ns: int
    size: int


@dataclass(frozen=True)
class Change:
    path: str
    kind: str


class StdoutLogger:
    def log(self, message: str, level: str = "INFO") -> None:
        if not message:
            print("")
            return
        if level in {"INFO", "STDOUT"}:
            print(message)
            return
        print(f"[{level}] {message}")


class DaemonLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level.upper()}] {message}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


class LockFile:
    def __init__(self, lock_path: Path, payload_factory) -> None:
        self.lock_path = lock_path
        self.payload_factory = payload_factory
        self.acquired = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale_lock()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.lock_path), flags)
        except FileExistsError as exc:
            raise RuntimeError(f"refresh daemon already running: {self.lock_path}") from exc

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(self.payload_factory(), handle, ensure_ascii=False)

        self.acquired = True
        atexit.register(self.release)

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.lock_path.unlink(missing_ok=True)
        finally:
            self.acquired = False

    def _clear_stale_lock(self) -> None:
        if not self.lock_path.exists():
            return

        try:
            payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
            pid = int(payload.get("pid", 0))
        except Exception:
            pid = 0

        if pid > 0 and pid_exists(pid):
            return

        self.lock_path.unlink(missing_ok=True)


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def default_workspace_root() -> Path:
    return script_dir().parent


def default_repo_root() -> Path:
    return default_workspace_root() / "mempalace-github-code"


def default_knowledge_cache_root() -> Path:
    return default_workspace_root() / "knowledges-cache"


def default_palace_path() -> Path:
    return default_workspace_root() / ".mempalace_local" / "palace"


CURRENT_POINTER_FILENAME = "current.json"
VERSIONS_DIRECTORY_NAME = "versions"
PALACE_DB_FILENAME = "chroma.sqlite3"
PALACE_SNAPSHOT_FILENAME = "source_snapshot.json"


def path_within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def ensure_safe_target(path: Path, allowed_root: Path, label: str) -> Path:
    resolved_path = path.resolve()
    resolved_root = allowed_root.resolve()
    if not path_within(resolved_root, resolved_path):
        raise RuntimeError(f"Refusing to touch {label} outside {resolved_root}: {resolved_path}")
    return resolved_path


def remove_tree_if_exists(path: Path, allowed_root: Path, label: str) -> None:
    resolved_path = ensure_safe_target(path, allowed_root, label)
    if resolved_path.exists():
        shutil.rmtree(resolved_path)


def palace_pointer_path(palace_root: Path) -> Path:
    return palace_root / CURRENT_POINTER_FILENAME


def palace_versions_root(palace_root: Path) -> Path:
    return palace_root / VERSIONS_DIRECTORY_NAME


def palace_snapshot_path(palace_path: Path) -> Path:
    return palace_path / PALACE_SNAPSHOT_FILENAME


def has_palace_database(path: Path) -> bool:
    return (path / PALACE_DB_FILENAME).is_file()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_current_pointer(palace_root: Path) -> dict | None:
    pointer_path = palace_pointer_path(palace_root)
    if not pointer_path.is_file():
        return None

    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid palace pointer file: {pointer_path}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid palace pointer payload: {pointer_path}")
    return payload


def resolve_pointer_target(palace_root: Path, pointer_payload: dict) -> Path:
    raw_path = pointer_payload.get("active_relative_path") or pointer_payload.get("active_path")
    if not raw_path:
        raise RuntimeError(f"Palace pointer missing active path: {palace_pointer_path(palace_root)}")

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = palace_root / candidate
    return ensure_safe_target(candidate, palace_root, "active palace path")


def resolve_active_palace_path(palace_root: Path) -> Path:
    resolved_root = palace_root.expanduser().resolve()
    pointer_payload = load_current_pointer(resolved_root)
    if pointer_payload is None:
        return resolved_root

    active_path = resolve_pointer_target(resolved_root, pointer_payload)
    if not active_path.exists():
        raise FileNotFoundError(f"Active palace path not found: {active_path}")
    return active_path


def write_current_pointer(palace_root: Path, active_path: Path, active_name: str) -> dict:
    resolved_root = palace_root.expanduser().resolve()
    resolved_active = ensure_safe_target(active_path, resolved_root, "active palace path")

    if resolved_active == resolved_root:
        relative_path = "."
    else:
        relative_path = resolved_active.relative_to(resolved_root).as_posix()

    payload = {
        "strategy": "blue-green",
        "palace_root": str(resolved_root),
        "active_name": active_name,
        "active_relative_path": relative_path,
        "active_path": str(resolved_active),
        "updated_at": iso_utc(time.time()),
    }
    write_json_atomic(palace_pointer_path(resolved_root), payload)
    return payload


def bootstrap_current_pointer_if_needed(palace_root: Path, logger) -> Path | None:
    resolved_root = palace_root.expanduser().resolve()
    pointer_payload = load_current_pointer(resolved_root)
    if pointer_payload is not None:
        return resolve_active_palace_path(resolved_root)

    if has_palace_database(resolved_root):
        write_current_pointer(resolved_root, resolved_root, "legacy-root")
        logger.log(f"Bootstrapped current palace pointer -> {resolved_root}")
        return resolved_root

    return None


def create_versioned_palace_dir(palace_root: Path) -> Path:
    versions_root = palace_versions_root(palace_root.expanduser().resolve())
    versions_root.mkdir(parents=True, exist_ok=True)

    while True:
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        suffix = f"{os.getpid()}-{time.time_ns() % 1_000_000:06d}"
        version_name = f"{timestamp}-{suffix}"
        version_path = versions_root / version_name
        try:
            version_path.mkdir(parents=False, exist_ok=False)
            return version_path
        except FileExistsError:
            continue


def load_source_snapshot(palace_path: Path) -> Dict[str, FileStamp] | None:
    snapshot_path = palace_snapshot_path(palace_path.expanduser().resolve())
    if not snapshot_path.is_file():
        return None

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid palace source snapshot: {snapshot_path}") from exc

    raw_files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(raw_files, dict):
        raise RuntimeError(f"Invalid palace source snapshot payload: {snapshot_path}")

    snapshot: Dict[str, FileStamp] = {}
    for source_file, raw_stamp in raw_files.items():
        if not isinstance(raw_stamp, dict):
            continue
        try:
            snapshot[source_file] = FileStamp(
                mtime_ns=int(raw_stamp["mtime_ns"]),
                size=int(raw_stamp["size"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return snapshot


def write_source_snapshot(palace_path: Path, snapshot: Dict[str, FileStamp]) -> None:
    payload = {
        "captured_at": iso_utc(time.time()),
        "files": {
            source_file: {
                "mtime_ns": stamp.mtime_ns,
                "size": stamp.size,
            }
            for source_file, stamp in snapshot.items()
        },
    }
    write_json_atomic(palace_snapshot_path(palace_path.expanduser().resolve()), payload)


def copy_palace_contents(source_path: Path, target_path: Path, palace_root: Path, logger) -> None:
    resolved_source = source_path.expanduser().resolve()
    resolved_target = target_path.expanduser().resolve()
    resolved_root = palace_root.expanduser().resolve()

    if not resolved_source.exists():
        raise FileNotFoundError(f"Seed palace path not found: {resolved_source}")

    logger.log(f"Seeding new palace version from active palace: {resolved_source}")
    for child in resolved_source.iterdir():
        if resolved_source == resolved_root and child.name in {CURRENT_POINTER_FILENAME, VERSIONS_DIRECTORY_NAME}:
            continue
        destination = resolved_target / child.name
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)
    logger.log(f"Seed copy complete: {resolved_target}")


def iter_versioned_palaces(palace_root: Path) -> list[Path]:
    versions_root = palace_versions_root(palace_root.expanduser().resolve())
    if not versions_root.is_dir():
        return []
    return sorted((path for path in versions_root.iterdir() if path.is_dir()), key=lambda item: item.name, reverse=True)


def prune_old_versions(palace_root: Path, keep_versions: int, active_path: Path, logger) -> None:
    if keep_versions < 0:
        raise ValueError("--keep-versions must be 0 or greater")

    active_resolved = active_path.expanduser().resolve()
    kept = 0
    for version_path in iter_versioned_palaces(palace_root):
        resolved_version = version_path.resolve()
        if resolved_version == active_resolved:
            kept += 1
            continue
        if kept < keep_versions:
            kept += 1
            continue
        shutil.rmtree(resolved_version)
        logger.log(f"Removed old palace version: {resolved_version}")


def ensure_unmanaged_palace_path(palace_path: Path) -> None:
    if palace_pointer_path(palace_path.expanduser().resolve()).is_file():
        raise RuntimeError(
            "Palace path is managed by blue-green cutover. "
            "Use 'daemon' to refresh the managed root, or point --palace-path to a concrete version directory."
        )


def is_managed_palace_root(palace_path: Path) -> bool:
    return palace_pointer_path(palace_path.expanduser().resolve()).is_file()


def command_exists(name: str) -> str | None:
    return shutil.which(name)


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout.strip()
        if not output or "No tasks are running" in output:
            return False
        return f'"{pid}"' in output
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def resolve_requested_python(requested_python: str | None) -> str:
    if requested_python:
        requested_path = Path(requested_python).expanduser()
        if requested_path.exists():
            return str(requested_path.resolve())
        requested_command = command_exists(requested_python)
        if requested_command:
            return requested_command
        raise FileNotFoundError(f"Python executable not found: {requested_python}")

    if os.name == "nt":
        launcher = command_exists("py")
        if launcher:
            result = subprocess.run(
                [launcher, "-0p"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                preferred_versions = ("3.11", "3.10", "3.9", "3.12", "3.13")
                for version in preferred_versions:
                    for line in result.stdout.splitlines():
                        if f"-V:{version}" not in line:
                            continue
                        resolved = re.sub(r"^\s*-V:[^\s]+\s+\*?\s*", "", line).strip()
                        if resolved:
                            return resolved

    for candidate in ("python3", "python"):
        resolved = command_exists(candidate)
        if resolved:
            return resolved

    raise FileNotFoundError("No supported Python interpreter found. Install Python 3.9+ or pass --python-exe.")


def query_python_version(python_exe: str) -> tuple[int, int]:
    result = subprocess.run(
        [python_exe, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not query Python version from {python_exe}")

    raw = result.stdout.strip()
    major_str, minor_str = raw.split(".", 1)
    return int(major_str), int(minor_str)


def resolve_venv_python(mempalace_repo: Path) -> Path:
    candidates = [
        mempalace_repo / ".venv" / "Scripts" / "python.exe",
        mempalace_repo / ".venv" / "bin" / "python3",
        mempalace_repo / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"MemPalace venv python not found under {mempalace_repo / '.venv'}")


def run_command(command: Sequence[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")


def ensure_required_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} not found: {resolved}")
    return resolved


def iter_wing_dirs(knowledge_cache_root: Path) -> list[Path]:
    if not knowledge_cache_root.exists():
        return []
    return sorted(
        path
        for path in knowledge_cache_root.iterdir()
        if path.is_dir() and (path / "mempalace.yaml").is_file()
    )


def count_wing_files(wing_dir: Path) -> int:
    return sum(
        1 for path in wing_dir.rglob("*") if path.is_file() and path.name != "mempalace.yaml"
    )


def derive_refresh_scope(
    knowledge_cache_root: Path,
    changes: Sequence[Change],
) -> tuple[list[str] | None, list[str], list[str]]:
    resolved_root = knowledge_cache_root.expanduser().resolve()
    selected_wings: set[str] = set()
    deleted_files: set[str] = set()
    reset_wings: set[str] = set()

    for change in changes:
        if change.path.startswith("<"):
            return None, [], []

        try:
            relative_path = Path(change.path).resolve().relative_to(resolved_root)
        except ValueError:
            return None, [], []

        if not relative_path.parts:
            return None, [], []

        wing_name = relative_path.parts[0]
        selected_wings.add(wing_name)

        if len(relative_path.parts) >= 2 and relative_path.parts[1] == "mempalace.yaml":
            reset_wings.add(wing_name)

        if change.kind == "deleted":
            deleted_files.add(str(Path(change.path).resolve()))

    deleted_config_files = {source_file for source_file in deleted_files if Path(source_file).name == "mempalace.yaml"}
    deleted_files.difference_update(deleted_config_files)
    return sorted(selected_wings), sorted(deleted_files), sorted(reset_wings)


def stream_command_output(command: Sequence[str], *, cwd: Path, logger, level: str = "STDOUT") -> None:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None
    try:
        for line in process.stdout:
            logger.log(line.rstrip("\r\n"), level)
    finally:
        process.stdout.close()

    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"Command failed ({returncode}): {' '.join(command)}")


def refresh_palace(
    palace_path: Path,
    mempalace_repo: Path,
    knowledge_cache_root: Path,
    logger,
    wing_names: Sequence[str] | None = None,
) -> None:
    python_exe = resolve_venv_python(mempalace_repo)
    palace_path.mkdir(parents=True, exist_ok=True)

    all_wing_dirs = iter_wing_dirs(knowledge_cache_root)
    if wing_names is None:
        wing_dirs = all_wing_dirs
    else:
        requested_names = {name for name in wing_names}
        wing_dirs = [wing_dir for wing_dir in all_wing_dirs if wing_dir.name in requested_names]
        missing_wings = sorted(requested_names - {wing_dir.name for wing_dir in wing_dirs})
        if missing_wings:
            logger.log(f"Skipping missing wing(s): {', '.join(missing_wings)}")

    total_wings = len(wing_dirs)

    logger.log(f"Refresh plan: {total_wings} wing(s) -> {palace_path}")

    if total_wings == 0:
        logger.log("No wings selected for mining.")
        logger.log("MemPalace refresh complete.")
        logger.log(f"Palace path: {palace_path}")
        logger.log(f"Knowledge cache: {knowledge_cache_root}")
        return

    for index, wing_dir in enumerate(wing_dirs, 1):
        wing_file_count = count_wing_files(wing_dir)
        logger.log(
            f"[{index}/{total_wings}] Mining wing '{wing_dir.name}' ({wing_file_count} file(s)) -> {palace_path}"
        )
        command = [
            str(python_exe),
            "-u",
            "-m",
            "mempalace.cli",
            "--palace",
            str(palace_path),
            "mine",
            str(wing_dir),
        ]
        stream_command_output(command, cwd=mempalace_repo, logger=logger)
        logger.log(f"[{index}/{total_wings}] Wing '{wing_dir.name}' complete.")

    logger.log("MemPalace refresh complete.")
    logger.log(f"Palace path: {palace_path}")
    logger.log(f"Knowledge cache: {knowledge_cache_root}")


def build_refresh_paths(args: argparse.Namespace) -> dict[str, Path]:
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    palace_path = Path(args.palace_path).expanduser().resolve()
    mempalace_repo = Path(args.mempalace_repo).expanduser().resolve()
    knowledge_cache_root = Path(args.knowledge_cache_root).expanduser().resolve()
    return {
        "workspace_root": workspace_root,
        "palace_path": palace_path,
        "mempalace_repo": mempalace_repo,
        "knowledge_cache_root": knowledge_cache_root,
    }


def prepare_refresh_context(args: argparse.Namespace) -> dict[str, Path]:
    paths = build_refresh_paths(args)
    ensure_required_path(paths["workspace_root"], "Workspace root")
    ensure_required_path(paths["knowledge_cache_root"], "Knowledge cache")
    ensure_required_path(paths["mempalace_repo"], "MemPalace repo")
    return paths


def run_refresh_core(args: argparse.Namespace, logger) -> None:
    paths = prepare_refresh_context(args)
    ensure_unmanaged_palace_path(paths["palace_path"])
    paths["palace_path"].mkdir(parents=True, exist_ok=True)
    refresh_palace(paths["palace_path"], paths["mempalace_repo"], paths["knowledge_cache_root"], logger)


def purge_deleted_sources(
    palace_path: Path,
    mempalace_repo: Path,
    deleted_files: Sequence[str],
    logger,
) -> None:
    unique_files = sorted({source_file for source_file in deleted_files})
    if not unique_files:
        return

    python_exe = resolve_venv_python(mempalace_repo)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(unique_files, handle, ensure_ascii=False)
        manifest_path = Path(handle.name)

    script = (
        "import json, sys\n"
        "from mempalace.palace import get_collection, get_closets_collection\n"
        "palace_path = sys.argv[1]\n"
        "manifest_path = sys.argv[2]\n"
        "with open(manifest_path, 'r', encoding='utf-8') as handle:\n"
        "    source_files = json.load(handle)\n"
        "drawers = get_collection(palace_path)\n"
        "closets = get_closets_collection(palace_path)\n"
        "for source_file in source_files:\n"
        "    try:\n"
        "        drawers.delete(where={'source_file': source_file})\n"
        "    except Exception:\n"
        "        pass\n"
        "    try:\n"
        "        closets.delete(where={'source_file': source_file})\n"
        "    except Exception:\n"
        "        pass\n"
        "print(f'Purged {len(source_files)} deleted source file(s).')\n"
    )

    try:
        logger.log(f"Purging {len(unique_files)} deleted source file(s) from copied palace state.")
        stream_command_output(
            [str(python_exe), "-u", "-c", script, str(palace_path), str(manifest_path)],
            cwd=mempalace_repo,
            logger=logger,
        )
    finally:
        manifest_path.unlink(missing_ok=True)


def purge_reset_wings(
    palace_path: Path,
    mempalace_repo: Path,
    wing_names: Sequence[str],
    logger,
) -> None:
    unique_wings = sorted({wing_name for wing_name in wing_names})
    if not unique_wings:
        return

    python_exe = resolve_venv_python(mempalace_repo)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(unique_wings, handle, ensure_ascii=False)
        manifest_path = Path(handle.name)

    script = (
        "import json, sys\n"
        "from mempalace.palace import get_collection, get_closets_collection\n"
        "palace_path = sys.argv[1]\n"
        "manifest_path = sys.argv[2]\n"
        "with open(manifest_path, 'r', encoding='utf-8') as handle:\n"
        "    wings = json.load(handle)\n"
        "drawers = get_collection(palace_path)\n"
        "closets = get_closets_collection(palace_path)\n"
        "for wing_name in wings:\n"
        "    try:\n"
        "        drawers.delete(where={'wing': wing_name})\n"
        "    except Exception:\n"
        "        pass\n"
        "    try:\n"
        "        closets.delete(where={'wing': wing_name})\n"
        "    except Exception:\n"
        "        pass\n"
        "print(f'Reset {len(wings)} wing(s).')\n"
    )

    try:
        logger.log(f"Resetting {len(unique_wings)} wing(s) before re-mine: {', '.join(unique_wings)}")
        stream_command_output(
            [str(python_exe), "-u", "-c", script, str(palace_path), str(manifest_path)],
            cwd=mempalace_repo,
            logger=logger,
        )
    finally:
        manifest_path.unlink(missing_ok=True)


def run_blue_green_refresh_core(
    args: argparse.Namespace,
    logger,
    changes: Sequence[Change] | None = None,
) -> Path:
    paths = prepare_refresh_context(args)
    palace_root = paths["palace_path"]
    palace_root.mkdir(parents=True, exist_ok=True)
    active_before = bootstrap_current_pointer_if_needed(palace_root, logger)
    current_snapshot = build_snapshot(paths["knowledge_cache_root"])

    previous_snapshot = load_source_snapshot(active_before) if active_before is not None else None
    effective_changes: list[Change]
    if changes:
        explicit_changes = [change for change in changes if not change.path.startswith("<")]
        if explicit_changes:
            effective_changes = explicit_changes
        elif previous_snapshot is not None:
            effective_changes = diff_snapshots(previous_snapshot, current_snapshot)
        elif active_before is None:
            effective_changes = [Change(path="<bootstrap>", kind="initial-refresh")]
        else:
            effective_changes = [Change(path="<bootstrap>", kind="full-refresh")]
    elif previous_snapshot is not None:
        effective_changes = diff_snapshots(previous_snapshot, current_snapshot)
    elif active_before is None:
        effective_changes = [Change(path="<bootstrap>", kind="initial-refresh")]
    else:
        effective_changes = [Change(path="<bootstrap>", kind="full-refresh")]

    if not effective_changes and active_before is not None:
        if previous_snapshot is None:
            write_source_snapshot(active_before, current_snapshot)
            logger.log(f"Backfilled source snapshot for active palace: {active_before}")
        logger.log("No knowledge changes detected. Keeping current active palace.")
        return active_before

    selected_wings, deleted_files, reset_wings = derive_refresh_scope(
        paths["knowledge_cache_root"],
        effective_changes,
    )
    can_seed_from_active = active_before is not None and has_palace_database(active_before)
    version_path = create_versioned_palace_dir(palace_root)

    try:
        seeded_from_active = False
        if can_seed_from_active and selected_wings is not None:
            try:
                copy_palace_contents(active_before, version_path, palace_root, logger)
                seeded_from_active = True
            except Exception as exc:
                logger.log(f"Seed copy failed, falling back to full rebuild: {exc}", "WARN")
                shutil.rmtree(version_path, ignore_errors=True)
                version_path.mkdir(parents=True, exist_ok=True)

        if seeded_from_active:
            logger.log(
                "Incremental refresh scope: "
                f"{len(selected_wings)} wing(s), "
                f"{len(reset_wings)} wing reset(s), "
                f"{len(deleted_files)} deleted file(s)"
            )
            purge_reset_wings(version_path, paths["mempalace_repo"], reset_wings, logger)
            resolved_cache_root = paths["knowledge_cache_root"].resolve()
            reset_wing_set = set(reset_wings)
            filtered_deleted_files: list[str] = []
            for source_file in deleted_files:
                try:
                    relative_path = Path(source_file).resolve().relative_to(resolved_cache_root)
                except ValueError:
                    filtered_deleted_files.append(source_file)
                    continue
                if relative_path.parts and relative_path.parts[0] in reset_wing_set:
                    continue
                filtered_deleted_files.append(source_file)
            purge_deleted_sources(version_path, paths["mempalace_repo"], filtered_deleted_files, logger)
            refresh_palace(
                version_path,
                paths["mempalace_repo"],
                paths["knowledge_cache_root"],
                logger,
                wing_names=selected_wings,
            )
        else:
            logger.log("Falling back to full refresh for blue-green cutover.")
            refresh_palace(version_path, paths["mempalace_repo"], paths["knowledge_cache_root"], logger)
        write_source_snapshot(version_path, current_snapshot)
    except Exception:
        shutil.rmtree(version_path, ignore_errors=True)
        raise

    write_current_pointer(palace_root, version_path, version_path.name)
    logger.log(f"Activated palace version: {version_path}")
    if active_before is not None and active_before != version_path:
        logger.log(f"Previous active palace: {active_before}")

    prune_old_versions(palace_root, getattr(args, "keep_versions", 3), version_path, logger)
    return version_path


def build_snapshot(knowledge_cache_root: Path) -> Dict[str, FileStamp]:
    snapshot: Dict[str, FileStamp] = {}

    for wing_dir in iter_wing_dirs(knowledge_cache_root):
        for file_path in wing_dir.rglob("*"):
            if not file_path.is_file():
                continue
            stat = file_path.stat()
            snapshot[str(file_path.resolve())] = FileStamp(stat.st_mtime_ns, stat.st_size)

    return snapshot


def diff_snapshots(previous: Dict[str, FileStamp], current: Dict[str, FileStamp]) -> list[Change]:
    changes: list[Change] = []
    previous_keys = set(previous)
    current_keys = set(current)

    for path in sorted(current_keys - previous_keys):
        changes.append(Change(path=path, kind="created"))

    for path in sorted(previous_keys - current_keys):
        changes.append(Change(path=path, kind="deleted"))

    for path in sorted(previous_keys & current_keys):
        if previous[path] != current[path]:
            changes.append(Change(path=path, kind="modified"))

    return changes


def iso_utc(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


def change_summary(changes: Iterable[Change], limit: int = 8) -> str:
    rendered = []
    for index, change in enumerate(changes):
        if index >= limit:
            rendered.append("...")
            break
        rendered.append(f"{change.path} [{change.kind}]")
    return "; ".join(rendered) if rendered else "no captured paths"


def write_state(
    state_path: Path,
    args: argparse.Namespace,
    snapshot: Dict[str, FileStamp],
    pending_changes: Dict[str, Change],
    last_change_at_wall: float | None,
    last_refresh_at: float | None,
    last_refresh_status: str,
    last_error: str | None,
) -> None:
    payload = {
        "pid": os.getpid(),
        "workspace_root": args.workspace_root,
        "palace_path": args.palace_path,
        "knowledge_cache_root": args.knowledge_cache_root,
        "debounce_seconds": args.debounce_seconds,
        "poll_seconds": args.poll_seconds,
        "tracked_files": len(snapshot),
        "pending_count": len(pending_changes),
        "last_change_at": iso_utc(last_change_at_wall),
        "last_refresh_at": iso_utc(last_refresh_at),
        "last_refresh_status": last_refresh_status,
        "last_error": last_error,
    }
    if hasattr(args, "keep_versions"):
        payload["keep_versions"] = args.keep_versions
        payload["cutover_mode"] = "blue-green"
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def install_signal_handlers(lock_file: LockFile, logger: DaemonLogger) -> None:
    def handle_signal(signum, _frame):
        logger.log(f"Received signal {signum}, stopping daemon.")
        lock_file.release()
        raise SystemExit(0)

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, handle_signal)
        except (ValueError, AttributeError):
            continue


def run_setup(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    mempalace_repo = Path(args.mempalace_repo).expanduser().resolve()
    venv_path = Path(args.venv_path).expanduser().resolve()

    ensure_required_path(workspace_root, "Workspace root")
    ensure_required_path(mempalace_repo, "MemPalace repo")

    setup_python = resolve_requested_python(args.python_exe)
    major, minor = query_python_version(setup_python)
    if major < 3 or (major == 3 and minor < 9):
        raise RuntimeError(
            f"Unsupported Python version {major}.{minor} at {setup_python}. MemPalace requires Python 3.9+."
        )

    if args.force_recreate:
        remove_tree_if_exists(venv_path, mempalace_repo, "MemPalace venv")

    try:
        venv_python = resolve_venv_python(mempalace_repo if venv_path == mempalace_repo / ".venv" else venv_path.parent)
        if not path_within(venv_path, venv_python):
            raise FileNotFoundError
    except FileNotFoundError:
        print(f"Creating MemPalace venv with Python {major}.{minor} at {setup_python}")
        run_command([setup_python, "-m", "venv", str(venv_path)])
        venv_python = resolve_venv_python(venv_path.parent if venv_path.name == ".venv" else venv_path.parent)
        if not path_within(venv_path, venv_python):
            venv_python = next(
                candidate.resolve()
                for candidate in (
                    venv_path / "Scripts" / "python.exe",
                    venv_path / "bin" / "python3",
                    venv_path / "bin" / "python",
                )
                if candidate.exists()
            )

    print(f"Using venv python: {venv_python}")
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=mempalace_repo)
    run_command([str(venv_python), "-m", "pip", "install", "-e", "."], cwd=mempalace_repo)
    run_command(
        [
            str(venv_python),
            "-c",
            "import chromadb, yaml, mempalace.mcp_server; print('MemPalace setup ok')",
        ],
        cwd=mempalace_repo,
    )

    print("MemPalace setup complete.")
    print(f"Repo: {mempalace_repo}")
    print(f"Venv: {venv_path}")
    return 0


def run_refresh(args: argparse.Namespace) -> int:
    logger = StdoutLogger()
    palace_path = Path(args.palace_path).expanduser().resolve()
    if is_managed_palace_root(palace_path):
        logger.log(f"Detected managed palace root, using blue-green refresh: {palace_path}")
        version_path = run_blue_green_refresh_core(args, logger)
        logger.log(f"Blue-green cutover complete. Active palace: {version_path}")
        return 0

    run_refresh_core(args, logger)
    return 0


def run_rebuild(args: argparse.Namespace) -> int:
    paths = build_refresh_paths(args)
    ensure_required_path(paths["workspace_root"], "Workspace root")
    ensure_unmanaged_palace_path(paths["palace_path"])
    remove_tree_if_exists(paths["palace_path"], paths["workspace_root"], "Palace path")
    run_refresh_core(args, StdoutLogger())
    return 0


def run_start_mcp(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    mempalace_repo = Path(args.mempalace_repo).expanduser().resolve()
    palace_path = Path(args.palace_path).expanduser().resolve()

    ensure_required_path(workspace_root, "Workspace root")
    ensure_required_path(mempalace_repo, "MemPalace repo")
    ensure_required_path(
        mempalace_repo / "mempalace" / "mcp_server.py",
        "MemPalace MCP entrypoint",
    )

    try:
        python_exe = resolve_venv_python(mempalace_repo)
    except FileNotFoundError as exc:
        setup_hint = script_dir() / "mempalace_tools.py"
        raise RuntimeError(
            f"MemPalace venv not found under {mempalace_repo / '.venv'}\nRun setup first. Example: python \"{setup_hint}\" setup"
        ) from exc

    palace_path.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(python_exe), "-m", "mempalace.mcp_server", "--palace", str(palace_path)],
        cwd=str(mempalace_repo),
    )
    return result.returncode


def run_daemon(args: argparse.Namespace) -> int:
    if args.run_once and args.no_initial_refresh:
        raise ValueError("--run-once cannot be combined with --no-initial-refresh")
    if args.keep_versions < 0:
        raise ValueError("--keep-versions must be 0 or greater")

    paths = build_refresh_paths(args)
    ensure_required_path(paths["workspace_root"], "Workspace root")
    ensure_required_path(paths["knowledge_cache_root"], "Knowledge cache")
    ensure_required_path(paths["mempalace_repo"], "MemPalace repo")

    daemon_root = paths["workspace_root"] / ".mempalace_local" / "refresh-daemon"
    daemon_root.mkdir(parents=True, exist_ok=True)
    logger = DaemonLogger(daemon_root / "daemon.log")
    lock_file = LockFile(
        daemon_root / "daemon.lock",
        lambda: {
            "pid": os.getpid(),
            "started_at": iso_utc(time.time()),
            "palace_path": str(paths["palace_path"]),
        },
    )
    lock_file.acquire()
    install_signal_handlers(lock_file, logger)

    logger.log(f"MemPalace refresh daemon starting. Palace root: {paths['palace_path']}")

    snapshot = build_snapshot(paths["knowledge_cache_root"])
    pending_changes: Dict[str, Change] = {}
    last_change_at_wall: float | None = None
    last_change_at_monotonic: float | None = None
    last_refresh_at: float | None = None
    last_refresh_status = "idle"
    last_error: str | None = None

    if not args.no_initial_refresh:
        pending_changes["<startup>"] = Change(path="<startup>", kind="initial-refresh")
        last_change_at_wall = time.time()
        last_change_at_monotonic = time.monotonic()

    write_state(
        daemon_root / "state.json",
        args,
        snapshot,
        pending_changes,
        last_change_at_wall,
        last_refresh_at,
        last_refresh_status,
        last_error,
    )

    if args.run_once:
        logger.log(f"Refresh started. Changes: {change_summary(pending_changes.values())}")
        version_path = run_blue_green_refresh_core(args, logger, list(pending_changes.values()))
        snapshot = build_snapshot(paths["knowledge_cache_root"])
        logger.log(f"Blue-green cutover complete. Active palace: {version_path}")
        write_state(
            daemon_root / "state.json",
            args,
            snapshot,
            {},
            last_change_at_wall,
            time.time(),
            "ok",
            None,
        )
        return 0

    logger.log(f"Daemon ready. Poll={args.poll_seconds}s, debounce={args.debounce_seconds}s")

    while True:
        time.sleep(args.poll_seconds)
        current_snapshot = build_snapshot(paths["knowledge_cache_root"])
        detected_changes = diff_snapshots(snapshot, current_snapshot)
        if detected_changes:
            snapshot = current_snapshot
            for change in detected_changes:
                pending_changes[change.path] = change
            last_change_at_wall = time.time()
            last_change_at_monotonic = time.monotonic()
            logger.log(f"Detected changes: {change_summary(detected_changes)}")
            write_state(
                daemon_root / "state.json",
                args,
                snapshot,
                pending_changes,
                last_change_at_wall,
                last_refresh_at,
                last_refresh_status,
                last_error,
            )

        if not pending_changes or last_change_at_monotonic is None:
            continue

        if time.monotonic() - last_change_at_monotonic < args.debounce_seconds:
            continue

        changes_for_run = list(pending_changes.values())
        pending_changes.clear()
        refresh_base_snapshot = snapshot
        last_refresh_status = "running"
        last_error = None
        write_state(
            daemon_root / "state.json",
            args,
            snapshot,
            pending_changes,
            last_change_at_wall,
            last_refresh_at,
            last_refresh_status,
            last_error,
        )

        try:
            logger.log(f"Refresh started. Changes: {change_summary(changes_for_run)}")
            version_path = run_blue_green_refresh_core(args, logger, changes_for_run)
            last_refresh_status = "ok"
            logger.log(f"Blue-green cutover complete. Active palace: {version_path}")
        except Exception as exc:
            last_refresh_status = "failed"
            last_error = str(exc)
            logger.log(f"Refresh failed: {exc}", "ERROR")

        last_refresh_at = time.time()
        snapshot = build_snapshot(paths["knowledge_cache_root"])
        follow_up_changes = diff_snapshots(refresh_base_snapshot, snapshot)
        if follow_up_changes:
            for change in follow_up_changes:
                pending_changes[change.path] = change
            last_change_at_wall = time.time()
            last_change_at_monotonic = time.monotonic()
            logger.log(
                "Detected new changes while refresh was running: "
                + change_summary(follow_up_changes)
            )

        write_state(
            daemon_root / "state.json",
            args,
            snapshot,
            pending_changes,
            last_change_at_wall,
            last_refresh_at,
            last_refresh_status,
            last_error,
        )


def add_shared_refresh_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--palace-path", default=str(default_palace_path()))
    parser.add_argument("--mempalace-repo", default=str(default_repo_root()))
    parser.add_argument("--knowledge-cache-root", default=str(default_knowledge_cache_root()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-platform MemPalace workspace tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Create/update the dedicated MemPalace venv.")
    setup_parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    setup_parser.add_argument("--mempalace-repo", default=str(default_repo_root()))
    setup_parser.add_argument("--venv-path", default=str(default_repo_root() / ".venv"))
    setup_parser.add_argument("--python-exe", default="")
    setup_parser.add_argument("--force-recreate", action="store_true")
    setup_parser.set_defaults(func=run_setup)

    refresh_parser = subparsers.add_parser("refresh", help="Mine all wings from knowledges-cache into the palace.")
    add_shared_refresh_arguments(refresh_parser)
    refresh_parser.add_argument("--keep-versions", type=int, default=3)
    refresh_parser.set_defaults(func=run_refresh)

    rebuild_parser = subparsers.add_parser("rebuild", help="Delete the palace and rebuild it from scratch.")
    add_shared_refresh_arguments(rebuild_parser)
    rebuild_parser.set_defaults(func=run_rebuild)

    mcp_parser = subparsers.add_parser("start-mcp", help="Start the local MemPalace MCP server.")
    mcp_parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    mcp_parser.add_argument("--mempalace-repo", default=str(default_repo_root()))
    mcp_parser.add_argument("--palace-path", default=str(default_palace_path()))
    mcp_parser.set_defaults(func=run_start_mcp)

    daemon_parser = subparsers.add_parser("daemon", help="Run the MemPalace refresh daemon.")
    add_shared_refresh_arguments(daemon_parser)
    daemon_parser.add_argument("--debounce-seconds", type=float, default=3.0)
    daemon_parser.add_argument("--poll-seconds", type=float, default=2.0)
    daemon_parser.add_argument("--no-initial-refresh", action="store_true")
    daemon_parser.add_argument("--run-once", action="store_true")
    daemon_parser.add_argument("--keep-versions", type=int, default=3)
    daemon_parser.set_defaults(func=run_daemon)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
