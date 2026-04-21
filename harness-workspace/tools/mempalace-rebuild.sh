#!/usr/bin/env bash
set -uo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd -- "${script_dir}/.." && pwd)"
unix_venv_python="${workspace_root}/mempalace-github-code/.venv/bin/python3"
windows_venv_python="${workspace_root}/mempalace-github-code/.venv/Scripts/python.exe"

print_command() {
  printf 'Running:'
  for arg in "$@"; do
    printf ' %q' "${arg}"
  done
  printf '\n'
}

if [[ -n "${MEMPALACE_PYTHON:-}" ]]; then
  python_exe="${MEMPALACE_PYTHON}"
elif [[ -f "${unix_venv_python}" ]]; then
  python_exe="${unix_venv_python}"
elif command -v python3 >/dev/null 2>&1; then
  python_exe="python3"
elif command -v python >/dev/null 2>&1; then
  python_exe="python"
elif [[ -f "${windows_venv_python}" ]]; then
  echo "Found Windows venv at '${windows_venv_python}', but this shell cannot execute it directly." >&2
  echo "Set MEMPALACE_PYTHON to a Unix Python executable." >&2
  exit 1
else
  echo "Missing Python executable." >&2
  echo "Run mempalace-setup.sh first or set MEMPALACE_PYTHON." >&2
  exit 1
fi

if [[ "${python_exe}" == */* ]]; then
  if [[ ! -f "${python_exe}" ]]; then
    echo "Missing Python executable '${python_exe}'." >&2
    echo "Run mempalace-setup.sh first or set MEMPALACE_PYTHON." >&2
    exit 1
  fi
elif ! command -v "${python_exe}" >/dev/null 2>&1; then
  echo "Missing Python executable '${python_exe}'." >&2
  echo "Run mempalace-setup.sh first or set MEMPALACE_PYTHON." >&2
  exit 1
fi

command=( "${python_exe}" "${script_dir}/mempalace_tools.py" rebuild "$@" )
print_command "${command[@]}"
"${command[@]}"
exit_code=$?
printf '\nExit code: %s\n' "${exit_code}"
if [[ "${MEMPALACE_NO_PAUSE:-}" != "1" && -t 0 ]]; then
  read -r -p "Press Enter to close..." _
fi
exit "${exit_code}"
