#!/usr/bin/env bash
set -euo pipefail

# Build ECIMS offline wheel bundle on an internet-connected machine.
# - Regenerates lock files from clean resolver environments
# - Downloads all locked wheels into offline_bundle/wheelhouse

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${ROOT_DIR}/offline_bundle"
WHEELHOUSE_DIR="${BUNDLE_DIR}/wheelhouse"
LOCK_SERVER="${BUNDLE_DIR}/requirements_server.lock.txt"
LOCK_AGENT="${BUNDLE_DIR}/requirements_agent.lock.txt"
TMP_DIR="${BUNDLE_DIR}/.tmp_build"

PYTHON_BIN="${PYTHON_BIN:-python3}"

resolve_lock() {
  local req_file="$1"
  local out_lock="$2"
  local env_dir="$3"

  rm -rf "${env_dir}"
  "${PYTHON_BIN}" -m venv "${env_dir}"
  # shellcheck disable=SC1090
  source "${env_dir}/bin/activate"
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -r "${req_file}"
  python -m pip freeze --exclude-editable | sort > "${out_lock}"
  deactivate
}

echo "[1/4] Cleaning wheelhouse and temp directories"
rm -rf "${WHEELHOUSE_DIR}" "${TMP_DIR}"
mkdir -p "${WHEELHOUSE_DIR}" "${TMP_DIR}"

echo "[2/4] Resolving and pinning server lock file"
resolve_lock "${ROOT_DIR}/server/requirements.txt" "${LOCK_SERVER}" "${TMP_DIR}/venv_server"

echo "[3/4] Resolving and pinning agent lock file"
resolve_lock "${ROOT_DIR}/agent/requirements.txt" "${LOCK_AGENT}" "${TMP_DIR}/venv_agent"

echo "[4/4] Downloading wheels into ${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: -r "${ROOT_DIR}/server/requirements.txt" -d "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: -r "${ROOT_DIR}/agent/requirements.txt" -d "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: -r "${LOCK_SERVER}" -d "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: -r "${LOCK_AGENT}" -d "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: pip setuptools wheel -d "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip download --only-binary=:all: PyYAML -d "${WHEELHOUSE_DIR}"

rm -rf "${TMP_DIR}"
echo "Done. Wheelhouse and lock files are ready in ${BUNDLE_DIR}."
