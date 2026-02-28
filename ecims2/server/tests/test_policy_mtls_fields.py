from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
except Exception as _dep_exc:  # noqa: BLE001
    _DEPS_ERR = _dep_exc
else:
    _DEPS_ERR = None



class TestPolicyMTLSFields(unittest.TestCase):
    def setUp(self) -> None:
        if _DEPS_ERR is not None:
            raise unittest.SkipTest(f"cryptography unavailable: {_DEPS_ERR}")

    def test_default_policy_enforces_mtls_and_pinning(self) -> None:
        from app.licensing_core.policy import DEFAULT_POLICY

        self.assertTrue(DEFAULT_POLICY.mtls_required)
        self.assertTrue(DEFAULT_POLICY.pinning_required)
        self.assertFalse(DEFAULT_POLICY.allow_tls12)
        self.assertFalse(DEFAULT_POLICY.allow_plain_https)

    def test_invalid_strict_policy_with_tls12_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            policy = {
                "mode": "STRICT",
                "mtls_required": True,
                "pinning_required": True,
                "allow_tls12": True,
                "allow_plain_https": False,
            }
            payload = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
            sig = key.sign(payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
            pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

            p = tmp / "policy.json"
            s = tmp / "policy.sig"
            pub_path = tmp / "pub.pem"
            p.write_text(json.dumps(policy), encoding="utf-8")
            s.write_text(base64.b64encode(sig).decode("ascii"), encoding="utf-8")
            pub_path.write_bytes(pub)

            from app.licensing_core.policy import load_security_policy

            res = load_security_policy(str(p), str(s), public_key_override=str(pub_path))
            self.assertEqual(res.reason, "POLICY_INVALID_JSON")


if __name__ == "__main__":
    unittest.main()
