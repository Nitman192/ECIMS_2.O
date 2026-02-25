#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=server uvicorn app.main:app \
  --host 0.0.0.0 --port 8443 \
  --ssl-certfile "${ECIMS_SERVER_CERT_PATH:-configs/tls/server.crt}" \
  --ssl-keyfile "${ECIMS_SERVER_KEY_PATH:-configs/tls/server.key}" \
  --ssl-ca-certs "${ECIMS_CLIENT_CA_CERT_PATH:-configs/tls/client_ca.crt}" \
  --ssl-cert-reqs 2
