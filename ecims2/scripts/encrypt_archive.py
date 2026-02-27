from __future__ import annotations

import argparse
from pathlib import Path

from app.security.storage_crypto import encrypt_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt archive/blob with ECIMS archive key")
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    args = parser.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.write_bytes(encrypt_bytes("archive_export", src.read_bytes()))
    print(f"Encrypted archive written to {dst}")


if __name__ == "__main__":
    main()
