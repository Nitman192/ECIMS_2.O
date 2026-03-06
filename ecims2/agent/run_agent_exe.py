from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = _runtime_root()
    os.chdir(root)
    if str(root / "agent") not in sys.path:
        sys.path.insert(0, str(root / "agent"))

    from ecims_agent.main import run

    parser = argparse.ArgumentParser(description="Run ECIMS agent executable")
    parser.add_argument("--config", default="configs/agent.local.dev.yaml")
    parser.add_argument("--runtime-id", default=None)
    parser.add_argument("--state-dir", default=None)
    args = parser.parse_args()
    run(args.config, runtime_id_override=args.runtime_id, state_dir_override=args.state_dir)


if __name__ == "__main__":
    main()

