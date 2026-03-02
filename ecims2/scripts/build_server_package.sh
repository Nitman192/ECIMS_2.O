#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/dist/ecims_server"
INCLUDE_PRIVATE_KEYS="${ECIMS_INCLUDE_PRIVATE_KEYS:-false}"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

cp -R "${ROOT_DIR}/server/app" "${OUT_DIR}/app"
mkdir -p "${OUT_DIR}/configs"

cp "${ROOT_DIR}/configs/security.policy.json" "${OUT_DIR}/configs/"
cp "${ROOT_DIR}/configs/security.policy.sig" "${OUT_DIR}/configs/"
cp "${ROOT_DIR}/configs/security.policy.public.pem" "${OUT_DIR}/configs/"
cp "${ROOT_DIR}/configs/device_allow_token_public.pem" "${OUT_DIR}/configs/"
cp "${ROOT_DIR}/configs/server.yaml.template" "${OUT_DIR}/configs/"
cp "${ROOT_DIR}/.env.production.template" "${OUT_DIR}/"
cp "${ROOT_DIR}/server/requirements.txt" "${OUT_DIR}/"

if [[ "${INCLUDE_PRIVATE_KEYS}" == "true" ]]; then
  cp "${ROOT_DIR}/configs/device_allow_token_private.pem" "${OUT_DIR}/configs/"
fi

cat > "${OUT_DIR}/README-OPS.md" <<'MD'
# ECIMS Server Ops Package

## Contents
- `app/` server application code
- `configs/` signed policy artifacts + allow-token public key
- `.env.production.template` required production env variables

## Security Notes
- Private keys are NOT packaged by default.
- Provision `ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH` from secure host secrets.
- In prod, startup fails closed on weak JWT, invalid policy artifacts, missing required encryption keys, or missing allow-token private key.
MD

echo "Built server package at ${OUT_DIR}"
