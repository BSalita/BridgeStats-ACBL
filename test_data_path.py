from __future__ import annotations

import os
import pathlib
import tempfile
import unittest

import bridgestatslib


class DataPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous = os.environ.pop(bridgestatslib.DATA_DIR_ENV, None)

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop(bridgestatslib.DATA_DIR_ENV, None)
        else:
            os.environ[bridgestatslib.DATA_DIR_ENV] = self._previous

    def test_default_is_repo_data_dir(self) -> None:
        expected = pathlib.Path(bridgestatslib.__file__).resolve().parent / "data"
        self.assertEqual(bridgestatslib.resolve_data_path(), expected)

    def test_env_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[bridgestatslib.DATA_DIR_ENV] = tmp
            self.assertEqual(bridgestatslib.resolve_data_path(), pathlib.Path(tmp))

    def test_does_not_auto_select_e_drive(self) -> None:
        resolved = bridgestatslib.resolve_data_path()
        self.assertNotEqual(resolved, pathlib.Path("e:/bridge/data"))
        self.assertNotEqual(resolved, pathlib.Path("e:/bridge/data/acbl"))
        self.assertFalse(str(resolved).lower().startswith("e:\\bridge\\data"))


if __name__ == "__main__":
    unittest.main()
