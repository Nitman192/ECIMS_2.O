from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding



def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_bool(value: str) -> bool:
    val = value.strip().lower()
    if val in {"true", "1", "yes"}:
        return True
    if val in {"false", "0", "no"}:
        return False
    raise ValueError("ai-enabled must be true/false")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate signed ECIMS offline license")
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--max-agents", required=True, type=int)
    parser.add_argument("--expiry-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--ai-enabled", required=True, help="true/false")
    parser.add_argument("--machine-fingerprint", default=None, help="Optional SHA256 hex fingerprint binding")
    parser.add_argument("--license-id", default=None)
    parser.add_argument("--customer-name", default=None)
    parser.add_argument("--scheme", choices=["pss", "pkcs1v15"], default="pss")
    parser.add_argument("--out", default="license.ecims")
    parser.add_argument("--private-key", default="private_key.pem")
    args = parser.parse_args()

    payload = {
        "org_name": args.org_name,
        "max_agents": int(args.max_agents),
        "expiry_date": args.expiry_date,
        "ai_enabled": _parse_bool(args.ai_enabled),
    }
    if args.machine_fingerprint:
        payload["machine_fingerprint"] = args.machine_fingerprint.strip().lower()
    if args.license_id:
        payload["license_id"] = args.license_id
    if args.customer_name:
        payload["customer_name"] = args.customer_name

    private_key_path = Path(args.private_key)
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)

    message = _canonical_payload_bytes(payload)
    if args.scheme == "pss":
        sig_padding = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    else:
        sig_padding = padding.PKCS1v15()

    signature = private_key.sign(message, sig_padding, hashes.SHA256())

    license_obj = {
        "payload": payload,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(license_obj, indent=2), encoding="utf-8")
    print(f"Wrote signed license: {out_path} (scheme={args.scheme})")


if __name__ == "__main__":
    main()
