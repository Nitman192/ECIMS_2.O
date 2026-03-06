from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import requests

from ecims_agent.api_client import ApiClient, TLSClientConfig
from ecims_agent.config import load_config
from ecims_agent.device_adapter import USBDevice, select_adapter
from ecims_agent.device_control import DeviceControlManager
from ecims_agent.discovery import resolve_server_url
from ecims_agent.runtime import build_runtime_context


class ClientGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ECIMS Client GUI (Local Dev)")
        self.root.geometry("1020x720")
        self.root.minsize(860, 620)

        self.process: subprocess.Popen[str] | None = None
        self._stream_thread: threading.Thread | None = None
        self._last_server_status: dict | None = None

        self.config_path = tk.StringVar(value="configs/agent.local.dev.yaml")
        self.runtime_id = tk.StringVar(value=os.environ.get("ECIMS_CLIENT_GUI_RUNTIME_ID", "endpoint-local-dev"))
        self.state_dir = tk.StringVar(value=".ecims_agent_runtime")
        self.runtime_root = tk.StringVar(value="-")
        self.last_health = tk.StringVar(value="-")
        self.last_server_sync = tk.StringVar(value="-")
        self.agent_proc = tk.StringVar(value="stopped")
        self.unlock_key = tk.StringVar(value="")

        self._build_layout()
        self.refresh_state()
        self._poll_process_state()

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        controls = ttk.LabelFrame(frame, text="Runtime Controls", padding=12)
        controls.pack(fill=tk.X, pady=(0, 10))

        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text="Config path").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.config_path).grid(row=0, column=1, sticky="ew", padx=(8, 14))

        ttk.Label(controls, text="Runtime ID").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.runtime_id).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(controls, text="State dir").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.state_dir).grid(row=1, column=1, sticky="ew", padx=(8, 14), pady=(8, 0))

        button_row = ttk.Frame(controls)
        button_row.grid(row=1, column=2, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(button_row, text="Refresh State", command=self.refresh_state).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Health Check", command=self.check_health).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Sync Server Status", command=self.sync_server_status).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Start Agent", command=self.start_agent).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Stop Agent", command=self.stop_agent).pack(side=tk.LEFT)

        ttk.Label(controls, text="Secure key").grid(row=2, column=0, sticky="w", pady=(10, 0))
        key_row = ttk.Frame(controls)
        key_row.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(10, 0))
        key_row.columnconfigure(0, weight=1)
        ttk.Entry(key_row, textvariable=self.unlock_key).grid(row=0, column=0, sticky="ew")
        ttk.Button(key_row, text="Apply Secure Key", command=self.apply_secure_key).grid(row=0, column=1, padx=(8, 0))

        summary = ttk.LabelFrame(frame, text="Runtime Summary", padding=12)
        summary.pack(fill=tk.X, pady=(0, 10))
        summary.columnconfigure(1, weight=1)

        ttk.Label(summary, text="Process").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.agent_proc).grid(row=0, column=1, sticky="w")
        ttk.Label(summary, text="Runtime root").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.runtime_root).grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Label(summary, text="Last health").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.last_health).grid(row=2, column=1, sticky="w", pady=(4, 0))
        ttk.Label(summary, text="Last server sync").grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.last_server_sync).grid(row=3, column=1, sticky="w", pady=(4, 0))

        state_group = ttk.LabelFrame(frame, text="Local Runtime Files", padding=12)
        state_group.pack(fill=tk.BOTH, expand=True)
        self.state_view = scrolledtext.ScrolledText(state_group, wrap=tk.WORD, height=14)
        self.state_view.pack(fill=tk.BOTH, expand=True)
        self.state_view.configure(state=tk.DISABLED)

        logs = ttk.LabelFrame(frame, text="Agent Output", padding=12)
        logs.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_view = scrolledtext.ScrolledText(logs, wrap=tk.WORD, height=12)
        self.log_view.pack(fill=tk.BOTH, expand=True)
        self.log_view.configure(state=tk.DISABLED)

    def _resolve_runtime(self) -> tuple[str, str, str, Path]:
        config_path = self.config_path.get().strip() or "configs/agent.local.dev.yaml"
        config = load_config(config_path)
        runtime_id = self.runtime_id.get().strip() or config.runtime_id or config.agent_name
        state_dir = self.state_dir.get().strip() or config.state_dir
        runtime = build_runtime_context(state_dir=state_dir, runtime_id=runtime_id)
        return config_path, config.server_url, runtime.runtime_id, runtime.runtime_root

    def _load_agent_state(self, runtime_root: Path) -> dict:
        state_path = runtime_root / "agent_state.json"
        if not state_path.exists():
            return {}
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _mask_token(token: str) -> str:
        if len(token) <= 10:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"

    def _set_state_text(self, payload: str) -> None:
        self.state_view.configure(state=tk.NORMAL)
        self.state_view.delete("1.0", tk.END)
        self.state_view.insert(tk.END, payload)
        self.state_view.configure(state=tk.DISABLED)

    def _append_log(self, text: str) -> None:
        def _write() -> None:
            self.log_view.configure(state=tk.NORMAL)
            self.log_view.insert(tk.END, text + "\n")
            self.log_view.see(tk.END)
            self.log_view.configure(state=tk.DISABLED)

        self.root.after(0, _write)

    def refresh_state(self) -> None:
        try:
            _, _, runtime_id, runtime_root = self._resolve_runtime()
            self.runtime_root.set(str(runtime_root))
            snapshot = {"runtime_id": runtime_id, "runtime_root": str(runtime_root), "files": {}}
            files = {
                "agent_state": runtime_root / "agent_state.json",
                "tokens": runtime_root / "agent_tokens.json",
                "event_queue": runtime_root / "agent_event_queue.json",
                "device_adapter_state": runtime_root / "device_adapter_state.json",
                "runtime_lock": runtime_root / "runtime.lock",
            }
            for label, path in files.items():
                if not path.exists():
                    snapshot["files"][label] = {"path": str(path), "exists": False}
                    continue
                if path.suffix == ".json":
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except Exception as exc:  # noqa: BLE001
                        data = {"error": f"Invalid JSON: {exc}"}
                else:
                    data = path.read_text(encoding="utf-8", errors="replace")
                if label == "agent_state" and isinstance(data, dict):
                    token = data.get("token")
                    if isinstance(token, str):
                        data = dict(data)
                        data["token_masked"] = self._mask_token(token)
                        data["token"] = "<redacted>"
                snapshot["files"][label] = {"path": str(path), "exists": True, "data": data}
            if self._last_server_status is not None:
                snapshot["server_status"] = self._last_server_status
            self._set_state_text(json.dumps(snapshot, indent=2))
            self._append_log("[INFO] Local runtime state refreshed")
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[ERROR] Refresh failed: {exc}")

    def check_health(self) -> None:
        try:
            config_path = self.config_path.get().strip() or "configs/agent.local.dev.yaml"
            cfg = load_config(config_path)
            server_url = resolve_server_url(cfg)
            response = requests.get(f"{server_url}/health", timeout=6)
            response.raise_for_status()
            self.last_health.set(f"{server_url}/health -> {response.status_code}")
            self._append_log(f"[INFO] Health check OK ({response.status_code})")
        except Exception as exc:  # noqa: BLE001
            self.last_health.set(f"failed ({exc})")
            self._append_log(f"[ERROR] Health check failed: {exc}")

    def sync_server_status(self) -> None:
        try:
            config_path = self.config_path.get().strip() or "configs/agent.local.dev.yaml"
            cfg = load_config(config_path)
            server_url = resolve_server_url(cfg)
            _, _, _, runtime_root = self._resolve_runtime()
            state = self._load_agent_state(runtime_root)
            agent_id = state.get("agent_id")
            token = state.get("token")
            if not isinstance(agent_id, int) or not isinstance(token, str) or not token:
                self._append_log("[WARN] Cannot sync server status: local agent_id/token not available yet")
                return

            response = requests.get(
                f"{server_url}/api/v1/agents/{agent_id}/self/status",
                headers={"X-ECIMS-TOKEN": token},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            self._last_server_status = payload

            counts = payload.get("command_counts") or {}
            pending = counts.get("pending", 0)
            self.last_server_sync.set(f"ok (pending={pending})")
            self._append_log(f"[INFO] Server status synced for agent_id={agent_id}, pending_commands={pending}")
            self.refresh_state()
        except Exception as exc:  # noqa: BLE001
            self.last_server_sync.set(f"failed ({exc})")
            self._append_log(f"[ERROR] Server status sync failed: {exc}")

    def apply_secure_key(self) -> None:
        allow_token = self.unlock_key.get().strip()
        if not allow_token:
            self._append_log("[WARN] Secure key is empty")
            return

        try:
            config_path, _, _, runtime_root = self._resolve_runtime()
            cfg = load_config(config_path)
            state = self._load_agent_state(runtime_root)
            agent_id = state.get("agent_id")
            if not isinstance(agent_id, int):
                self._append_log("[WARN] Agent must be enrolled before secure key can be applied")
                return

            manager = DeviceControlManager(
                enforcement_mode=cfg.device_enforcement_mode,
                failsafe_offline_minutes=cfg.failsafe_offline_minutes,
                token_public_key_path=cfg.token_public_key_path,
                local_event_queue_retention_hours=cfg.local_event_queue_retention_hours,
                enforcement_grace_seconds=cfg.enforcement_grace_seconds,
            )
            accepted, reason = manager.consume_manual_allow_token(agent_id=agent_id, allow_token=allow_token)
            if not accepted:
                self._append_log(f"[ERROR] Secure key rejected: {reason}")
                messagebox.showerror("ECIMS Secure Key", f"Secure key rejected: {reason}")
                return

            adapter = select_adapter()
            unblocked = adapter.unblock_device(USBDevice(device_id="manual-secure-key", vid="", pid=""), None)
            if not unblocked:
                self._append_log("[ERROR] Secure key accepted but USB unblock failed")
                messagebox.showerror(
                    "ECIMS Secure Key",
                    "Secure key accepted but unblock failed. Run client as administrator and retry.",
                )
                return

            # Best-effort event submission to backend for admin-side timeline.
            agent_token = state.get("token")
            if isinstance(agent_token, str) and agent_token:
                try:
                    server_url = resolve_server_url(cfg)
                    api_client = ApiClient(
                        server_url,
                        TLSClientConfig(
                            cert_path=cfg.agent_client_cert_path,
                            key_path=cfg.agent_client_key_path,
                            pfx_path=cfg.agent_pfx_path,
                            pfx_password=cfg.agent_pfx_password,
                            ca_bundle_path=cfg.server_ca_bundle_path,
                            server_cert_pin_sha256=cfg.server_cert_pin_sha256,
                            pinning_required=cfg.pinning_required,
                            allow_plain_https=cfg.allow_plain_https,
                        ),
                    )
                    try:
                        api_client.consume_allow_token(agent_id, agent_token, allow_token)
                    except Exception as exc:  # noqa: BLE001
                        self._append_log(f"[WARN] Secure key consumed locally; server consume sync failed: {exc}")
                    api_client.post_events(
                        agent_id,
                        agent_token,
                        [
                            {
                                "schema_version": "1.0",
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "event_type": "device.usb.unblock_applied",
                                "file_path": "device://manual-secure-key",
                                "sha256": None,
                                "file_size_bytes": None,
                                "mtime_epoch": None,
                                "user": None,
                                "process_name": None,
                                "host_ip": None,
                                "details_json": {
                                    "event_id": uuid.uuid4().hex,
                                    "device_id": "manual-secure-key",
                                    "result": "manual_secure_key",
                                    "source": "client_gui",
                                },
                            }
                        ],
                    )
                except Exception as exc:  # noqa: BLE001
                    self._append_log(f"[WARN] Secure key applied locally; event sync failed: {exc}")

            self.unlock_key.set("")
            self._append_log(f"[INFO] Secure key accepted; USB mass-storage block released for agent_id={agent_id}")
            messagebox.showinfo(
                "ECIMS Secure Key",
                "Secure key accepted. USB mass-storage block released on this client.",
            )
            self.refresh_state()
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[ERROR] Secure key flow failed: {exc}")

    def start_agent(self) -> None:
        if self.process and self.process.poll() is None:
            self._append_log("[WARN] Agent process already running")
            return
        try:
            config_path, _, runtime_id, _ = self._resolve_runtime()
            state_dir = self.state_dir.get().strip() or ".ecims_agent_runtime"
            env = os.environ.copy()
            if getattr(sys, "frozen", False):
                workdir = Path(sys.executable).resolve().parent
                agent_exe = workdir / "ecims_agent.exe"
                if not agent_exe.exists():
                    raise RuntimeError(f"Missing agent executable: {agent_exe}")
                cmd = [
                    str(agent_exe),
                    "--config",
                    config_path,
                    "--runtime-id",
                    runtime_id,
                    "--state-dir",
                    state_dir,
                ]
            else:
                cmd = [
                    sys.executable,
                    "-m",
                    "ecims_agent.main",
                    "--config",
                    config_path,
                    "--runtime-id",
                    runtime_id,
                    "--state-dir",
                    state_dir,
                ]
                env["PYTHONPATH"] = "agent"
                workdir = Path(__file__).resolve().parents[2]
            self.process = subprocess.Popen(
                cmd,
                cwd=str(workdir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.agent_proc.set(f"running (pid={self.process.pid})")
            self._append_log(f"[INFO] Started agent: {' '.join(cmd)}")
            self._stream_thread = threading.Thread(target=self._stream_agent_output, daemon=True)
            self._stream_thread.start()
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[ERROR] Start failed: {exc}")

    def _stream_agent_output(self) -> None:
        proc = self.process
        if not proc or not proc.stdout:
            return
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self._append_log(line)

    def stop_agent(self) -> None:
        if not self.process or self.process.poll() is not None:
            self._append_log("[WARN] No running agent process")
            self.agent_proc.set("stopped")
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.agent_proc.set("stopped")
        self._append_log("[INFO] Agent process stopped")

    def _poll_process_state(self) -> None:
        if self.process and self.process.poll() is not None:
            code = self.process.returncode
            self._append_log(f"[INFO] Agent exited with code {code}")
            self.agent_proc.set(f"stopped (exit={code})")
            self.process = None
        self.root.after(1000, self._poll_process_state)

    def on_close(self) -> None:
        try:
            self.stop_agent()
        finally:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = ClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
