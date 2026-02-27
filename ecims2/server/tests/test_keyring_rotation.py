from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestKeyringRotationScripts(unittest.TestCase):
    def test_generate_and_rotate_keyring(self) -> None:
        generate_mod = _load_module(ROOT / "scripts" / "generate_data_key.py", "generate_data_key")
        rotate_mod = _load_module(ROOT / "scripts" / "rotate_data_key.py", "rotate_data_key")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "keyring.json"
            generated = generate_mod.generate_keyring(path, kid="k-old")
            self.assertEqual(generated["active_kid"], "k-old")

            rotated = rotate_mod.rotate_keyring(path, kid="k-new")
            self.assertEqual(rotated["active_kid"], "k-new")

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("k-old", data["keys"])
            self.assertIn("k-new", data["keys"])


if __name__ == "__main__":
    unittest.main()
