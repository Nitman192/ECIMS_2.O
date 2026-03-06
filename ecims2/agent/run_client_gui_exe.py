from __future__ import annotations

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

    from ecims_agent.client_gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()

