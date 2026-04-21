#!/usr/bin/env bash
set -uo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

print_command() {
  printf 'Running:'
  for arg in "$@"; do
    printf ' %q' "${arg}"
  done
  printf '\n'
}

if [[ -n "${MEMPALACE_SETUP_PYTHON:-}" ]]; then
  python_exe="${MEMPALACE_SETUP_PYTHON}"
elif [[ -n "${MEMPALACE_PYTHON:-}" ]]; then
  python_exe="${MEMPALACE_PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
  python_exe="python3"
elif command -v python >/dev/null 2>&1; then
  python_exe="python"
else
  echo "Missing Python executable. Set MEMPALACE_SETUP_PYTHON or install Python first." >&2
  exit 1
fi

command=( "${python_exe}" "${script_dir}/mempalace_tools.py" setup "$@" )
print_command "${command[@]}"
"${command[@]}"
exit_code=$?
printf '\nExit code: %s\n' "${exit_code}"
if [[ "${MEMPALACE_NO_PAUSE:-}" != "1" && -t 0 ]]; then
  read -r -p "Press Enter to close..." _
fi
exit "${exit_code}"
