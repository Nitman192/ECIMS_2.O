from __future__ import annotations

import atexit
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ecims_agent.device_adapter import set_device_state_file
from ecims_agent.offline_store import configure_store_paths
from ecims_agent.storage import set_state_file

_RUNTIME_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_runtime_id(raw: str) -> str:
    candidate = _RUNTIME_SAFE_CHARS.sub("-", raw.strip()).strip(".-")
    return candidate or "default"


@dataclass(frozen=True)
class AgentRuntimeContext:
    runtime_id: str
    runtime_root: Path
    state_file: Path
    tokens_file: Path
    event_queue_file: Path
    device_state_file: Path
    lock_file: Path


def build_runtime_context(state_dir: str, runtime_id: str) -> AgentRuntimeContext:
    safe_runtime_id = _sanitize_runtime_id(runtime_id)
    runtime_root = Path(state_dir).expanduser().resolve() / safe_runtime_id
    runtime_root.mkdir(parents=True, exist_ok=True)
    return AgentRuntimeContext(
        runtime_id=safe_runtime_id,
        runtime_root=runtime_root,
        state_file=runtime_root / "agent_state.json",
        tokens_file=runtime_root / "agent_tokens.json",
        event_queue_file=runtime_root / "agent_event_queue.json",
        device_state_file=runtime_root / "device_adapter_state.json",
        lock_file=runtime_root / "runtime.lock",
    )


def configure_runtime_storage(runtime: AgentRuntimeContext) -> None:
    set_state_file(runtime.state_file)
    configure_store_paths(tokens_path=runtime.tokens_file, eventq_path=runtime.event_queue_file)
    set_device_state_file(runtime.device_state_file)


class RuntimeLock:
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self._active = False
        self._cleanup_registered = False

    def acquire(self) -> None:
        if self._active:
            return
        while True:
            try:
                with self.lock_file.open("x", encoding="utf-8") as handle:
                    handle.write(
                        json.dumps(
                            {
                                "pid": os.getpid(),
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            },
                            ensure_ascii=True,
                        )
                    )
                self._active = True
                if not self._cleanup_registered:
                    atexit.register(self.release)
                    self._cleanup_registered = True
                return
            except FileExistsError:
                if not self._clear_stale_lock():
                    raise RuntimeError(
                        f"Runtime '{self.lock_file.parent.name}' already running. "
                        f"Lock file: {self.lock_file}"
                    ) from None

    def release(self) -> None:
        if not self._active:
            return
        try:
            self.lock_file.unlink(missing_ok=True)
        finally:
            self._active = False

    def _clear_stale_lock(self) -> bool:
        try:
            payload = json.loads(self.lock_file.read_text(encoding="utf-8"))
        except Exception:
            self.lock_file.unlink(missing_ok=True)
            return True

        pid = payload.get("pid")
        if not isinstance(pid, int):
            self.lock_file.unlink(missing_ok=True)
            return True

        if _pid_alive(pid):
            return False
        self.lock_file.unlink(missing_ok=True)
        return True


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
