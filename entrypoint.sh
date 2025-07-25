#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${GITHUB_WORKSPACE:-}" && -d "${GITHUB_WORKSPACE}" ]]; then
  chown -R nbconvert:nbconvert "${GITHUB_WORKSPACE}"
fi

if [[ -n "${INPUT_OUTPUT_DIR:-}" ]]; then
  install -d -o nbconvert -g nbconvert "${GITHUB_WORKSPACE}/${INPUT_OUTPUT_DIR}"
fi

exec gosu nbconvert /usr/local/bin/python /home/nbconvert/executor.py "$@"
