#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/dist/ecims_agent_windows"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}/ecims_agent" "${OUT_DIR}/windows_service"

cp -R "${ROOT_DIR}/agent/ecims_agent" "${OUT_DIR}/"
cp "${ROOT_DIR}/configs/agent.yaml" "${OUT_DIR}/agent.yaml.template"
cp "${ROOT_DIR}/configs/device_allow_token_public.pem" "${OUT_DIR}/device_allow_token_public.pem"
cp "${ROOT_DIR}/agent/windows_service/install_service.ps1" "${OUT_DIR}/windows_service/"
cp "${ROOT_DIR}/agent/windows_service/uninstall_service.ps1" "${OUT_DIR}/windows_service/"

cat > "${OUT_DIR}/README-OPS.md" <<'MD'
# ECIMS Agent Windows Package

## Installer Safety
- Installer backs up existing config before applying new one.
- Installer preserves token/local state files.
- Uninstall removes service registration only; runtime state can be preserved.

## Service
Use `windows_service/install_service.ps1` with configurable service name, runtime account, and log directory.
MD

echo "Built agent package at ${OUT_DIR}"
