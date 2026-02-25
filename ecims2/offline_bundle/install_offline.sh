#!/usr/bin/env bash
set -euo pipefail

# Install ECIMS server + agent dependencies from local wheelhouse only.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
WHEELHOUSE_DIR="${ROOT_DIR}/offline_bundle/wheelhouse"
LOCK_SERVER="${ROOT_DIR}/offline_bundle/requirements_server.lock.txt"
LOCK_AGENT="${ROOT_DIR}/offline_bundle/requirements_agent.lock.txt"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "${WHEELHOUSE_DIR}" ]]; then
  echo "wheelhouse directory not found: ${WHEELHOUSE_DIR}" >&2
  exit 1
fi

if [[ ! -f "${LOCK_SERVER}" || ! -f "${LOCK_AGENT}" ]]; then
  echo "lock files not found under offline_bundle/." >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

python -m pip install --no-index --find-links "${WHEELHOUSE_DIR}" --upgrade pip setuptools wheel
python -m pip install --no-index --find-links "${WHEELHOUSE_DIR}" -r "${LOCK_SERVER}"
python -m pip install --no-index --find-links "${WHEELHOUSE_DIR}" -r "${LOCK_AGENT}"

echo "Offline install complete."
