#!/usr/bin/env bash
set -euo pipefail

# Standard startup (no TLS offload)
PYTHONPATH=server uvicorn app.main:app --host 0.0.0.0 --port 8000
