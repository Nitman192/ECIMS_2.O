from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hardened ECIMS licensing module with Nuitka")
    parser.add_argument("--python", default="python")
    parser.add_argument("--output-dir", default="build/hardened")
    parser.add_argument("--keep-source", action="store_true", help="Do not remove licensing_core .py from output package")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    module_entry = root / "server" / "app" / "licensing_core" / "__init__.py"
    run(
        [
            args.python,
            "-m",
            "nuitka",
            "--module",
            "--output-dir",
            str(output_dir),
            str(module_entry),
        ]
    )

    dist_app = output_dir / "app"
    if dist_app.exists():
        shutil.rmtree(dist_app)
    shutil.copytree(root / "server" / "app", dist_app)

    if not args.keep_source:
        lic_dir = dist_app / "licensing_core"
        for py in lic_dir.glob("*.py"):
            py.unlink()

    print(f"Hardened build artifacts created under: {output_dir}")


if __name__ == "__main__":
    main()
