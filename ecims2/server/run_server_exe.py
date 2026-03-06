from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _set_default_path(env_name: str, path: Path) -> None:
    if os.getenv(env_name):
        return
    if path.exists():
        os.environ[env_name] = str(path)


def _bootstrap_environment(root: Path, environment: str) -> None:
    os.environ.setdefault("ECIMS_ENVIRONMENT", environment)

    # For quick LAN deployment defaults. Override with env vars for hardened mode.
    if environment == "dev":
        os.environ.setdefault("ECIMS_MTLS_ENABLED", "0")
        os.environ.setdefault("ECIMS_MTLS_REQUIRED", "0")

    os.environ.setdefault("ECIMS_DB_PATH", str(root / "ecims2.db"))

    configs_dir = root / "configs"
    _set_default_path("ECIMS_LICENSE_PATH", configs_dir / "license.ecims")
    _set_default_path("ECIMS_LICENSE_PUBLIC_KEY_PATH", configs_dir / "license.public_key.pem")
    _set_default_path("ECIMS_SECURITY_POLICY_PATH", configs_dir / "security.policy.json")
    _set_default_path("ECIMS_SECURITY_POLICY_SIG_PATH", configs_dir / "security.policy.sig")
    _set_default_path("ECIMS_SECURITY_POLICY_PUBLIC_KEY_PATH", configs_dir / "security.policy.public.pem")
    _set_default_path("ECIMS_DEVICE_ALLOW_TOKEN_PUBLIC_KEY_PATH", configs_dir / "device_allow_token_public.pem")
    _set_default_path("ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH", configs_dir / "device_allow_token_private.pem")
    _set_default_path("ECIMS_DATA_KEY_PATH", configs_dir / "data_keys.json")


def _load_asgi_app(root: Path):
    server_path = root / "server"
    if server_path.exists() and str(server_path) not in sys.path:
        sys.path.insert(0, str(server_path))

    from app.main import app

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ECIMS server executable")
    parser.add_argument("--host", default=os.getenv("ECIMS_SERVER_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ECIMS_SERVER_PORT", "8010")))
    parser.add_argument("--environment", default=os.getenv("ECIMS_ENVIRONMENT", "dev"), choices=["dev", "test", "prod"])
    args = parser.parse_args()

    root = _runtime_root()
    os.chdir(root)
    _bootstrap_environment(root=root, environment=args.environment)

    asgi_app = _load_asgi_app(root)
    uvicorn.run(asgi_app, host=args.host, port=args.port, reload=False, loop="asyncio", http="h11")


if __name__ == "__main__":
    main()
