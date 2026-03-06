from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

import requests

from ecims_agent.config import load_config
from ecims_agent.runtime import build_runtime_context


class ClientGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ECIMS Client GUI (Local Dev)")
        self.root.geometry("1020x720")
        self.root.minsize(860, 620)

        self.process: subprocess.Popen[str] | None = None
        self._stream_thread: threading.Thread | None = None

        self.config_path = tk.StringVar(value="configs/agent.local.dev.yaml")
        self.runtime_id = tk.StringVar(value=os.environ.get("ECIMS_CLIENT_GUI_RUNTIME_ID", "endpoint-local-dev"))
        self.state_dir = tk.StringVar(value=".ecims_agent_runtime")
        self.runtime_root = tk.StringVar(value="-")
        self.last_health = tk.StringVar(value="-")
        self.agent_proc = tk.StringVar(value="stopped")

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
        ttk.Button(button_row, text="Start Agent", command=self.start_agent).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Stop Agent", command=self.stop_agent).pack(side=tk.LEFT)

        summary = ttk.LabelFrame(frame, text="Runtime Summary", padding=12)
        summary.pack(fill=tk.X, pady=(0, 10))
        summary.columnconfigure(1, weight=1)

        ttk.Label(summary, text="Process").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.agent_proc).grid(row=0, column=1, sticky="w")
        ttk.Label(summary, text="Runtime root").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.runtime_root).grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Label(summary, text="Last health").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.last_health).grid(row=2, column=1, sticky="w", pady=(4, 0))

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
                snapshot["files"][label] = {"path": str(path), "exists": True, "data": data}
            self._set_state_text(json.dumps(snapshot, indent=2))
            self._append_log("[INFO] Local runtime state refreshed")
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[ERROR] Refresh failed: {exc}")

    def check_health(self) -> None:
        try:
            config_path = self.config_path.get().strip() or "configs/agent.local.dev.yaml"
            cfg = load_config(config_path)
            response = requests.get(f"{cfg.server_url}/health", timeout=6)
            response.raise_for_status()
            self.last_health.set(f"{cfg.server_url}/health -> {response.status_code}")
            self._append_log(f"[INFO] Health check OK ({response.status_code})")
        except Exception as exc:  # noqa: BLE001
            self.last_health.set(f"failed ({exc})")
            self._append_log(f"[ERROR] Health check failed: {exc}")

    def start_agent(self) -> None:
        if self.process and self.process.poll() is None:
            self._append_log("[WARN] Agent process already running")
            return
        try:
            config_path, _, runtime_id, _ = self._resolve_runtime()
            state_dir = self.state_dir.get().strip() or ".ecims_agent_runtime"
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
            env = os.environ.copy()
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
