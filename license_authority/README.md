# ECIMS License Authority (Offline)

This folder contains offline tools for generating RSA keys and signed ECIMS license files.

## 1) Generate keypair

```bash
cd license_authority
python generate_keys.py
```

Outputs:
- `private_key.pem` (keep secret; never commit)
- `public_key.pem` (copy to server verify path)

Copy public key to:
- `ecims2/server/app/license/public_key.pem`

## 2) Generate a signed license (RSA-PSS default)

```bash
cd license_authority
python generate_license.py \
  --org-name "ACME Corp" \
  --max-agents 25 \
  --expiry-date 2027-12-31 \
  --ai-enabled true \
  --license-id "LIC-2027-0001" \
  --customer-name "ACME Corp" \
  --out ../ecims2/configs/license.ecims
```

Optional machine binding:

```bash
python generate_license.py \
  --org-name "ACME Corp" \
  --max-agents 25 \
  --expiry-date 2027-12-31 \
  --ai-enabled true \
  --machine-fingerprint <sha256-hex> \
  --out ../ecims2/configs/license.ecims
```

Legacy compatibility (PKCS1v15 signing):

```bash
python generate_license.py ... --scheme pkcs1v15
```

License schema:

```json
{
  "payload": {
    "org_name": "ACME Corp",
    "max_agents": 25,
    "expiry_date": "2027-12-31",
    "ai_enabled": true,
    "machine_fingerprint": "optional-sha256-hex",
    "license_id": "optional-id",
    "customer_name": "optional-customer"
  },
  "signature_b64": "..."
}
```

## Phase 6: Offline mTLS Provisioning

> **Security warning:** Never distribute `mtls_ca.key`. Keep CA private keys only on the offline authority machine.

### 1) Generate mTLS CA

```bash
python generate_mtls_ca.py --out-dir ./out/ca --common-name "ECIMS mTLS Root CA"
```

Outputs:
- `out/ca/mtls_ca.key` (private, authority-only)
- `out/ca/mtls_ca.crt` (public trust anchor)

### 2) Agent generates CSR locally

```bash
python ../ecims2/agent/ecims_agent/agent_generate_csr.py --agent-id 101 --out-dir ./out/agent101
```

Outputs:
- `agent_101.key` (stays on endpoint)
- `agent_101.csr` (transfer to authority)

### 3) Authority signs agent CSR

```bash
python sign_agent_csr.py \
  --ca-key ./out/ca/mtls_ca.key \
  --ca-cert ./out/ca/mtls_ca.crt \
  --csr ./out/agent101/agent_101.csr \
  --agent-id 101 \
  --out-cert ./out/agent101/agent_101.crt
```

### 4) Optional Windows PFX bundle

```bash
python generate_agent_bundle.py \
  --cert ./out/agent101/agent_101.crt \
  --key ./out/agent101/agent_101.key \
  --password "ChangeThisStrongPassword" \
  --out ./out/agent101/agent_101.pfx
```
