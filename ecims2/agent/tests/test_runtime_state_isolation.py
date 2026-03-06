from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import ecims_agent.device_adapter as device_adapter
import ecims_agent.offline_store as offline_store
import ecims_agent.storage as storage
from ecims_agent.offline_store import save_event_queue, save_tokens
from ecims_agent.runtime import RuntimeLock, build_runtime_context, configure_runtime_storage
from ecims_agent.storage import save_state


class TestRuntimeStateIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self._orig_state_file = storage.STATE_FILE
        self._orig_tokens = offline_store.TOKENS
        self._orig_eventq = offline_store.EVENTQ
        self._orig_used_tokens = offline_store.USED_ALLOW_TOKENS
        self._orig_device_state = device_adapter._STATE

    def tearDown(self) -> None:
        storage.set_state_file(self._orig_state_file)
        offline_store.configure_store_paths(
            tokens_path=self._orig_tokens,
            eventq_path=self._orig_eventq,
            used_tokens_path=self._orig_used_tokens,
        )
        device_adapter.set_device_state_file(self._orig_device_state)
        self.temp_dir.cleanup()

    def test_runtime_paths_are_isolated(self) -> None:
        runtime_a = build_runtime_context(str(self.root), "client-a")
        runtime_b = build_runtime_context(str(self.root), "client:b")

        configure_runtime_storage(runtime_a)
        save_state({"agent_id": 101, "token": "tok-a"})
        save_tokens(["token-a"])
        save_event_queue([{"event": "a"}])
        device_adapter._save_state({"blocked": True})  # noqa: SLF001

        configure_runtime_storage(runtime_b)
        save_state({"agent_id": 202, "token": "tok-b"})
        save_tokens(["token-b"])
        save_event_queue([{"event": "b"}])
        device_adapter._save_state({"blocked": False})  # noqa: SLF001

        state_a = json.loads(runtime_a.state_file.read_text(encoding="utf-8"))
        state_b = json.loads(runtime_b.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state_a["agent_id"], 101)
        self.assertEqual(state_b["agent_id"], 202)

        tokens_a = json.loads(runtime_a.tokens_file.read_text(encoding="utf-8"))
        tokens_b = json.loads(runtime_b.tokens_file.read_text(encoding="utf-8"))
        self.assertEqual(tokens_a, ["token-a"])
        self.assertEqual(tokens_b, ["token-b"])

        self.assertNotEqual(runtime_a.runtime_root, runtime_b.runtime_root)
        self.assertTrue(runtime_b.runtime_root.name.startswith("client-b"))

    def test_runtime_lock_blocks_duplicate_instance(self) -> None:
        runtime = build_runtime_context(str(self.root), "dup-client")
        lock_a = RuntimeLock(runtime.lock_file)
        lock_b = RuntimeLock(runtime.lock_file)
        lock_a.acquire()
        with self.assertRaises(RuntimeError):
            lock_b.acquire()
        lock_a.release()
        lock_b.acquire()
        lock_b.release()


if __name__ == "__main__":
    unittest.main()
