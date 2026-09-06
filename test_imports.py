from __future__ import annotations

import importlib
import sys
import unittest


class ImportTests(unittest.TestCase):
    def test_bridgestatslib_imports_without_acbllib_or_mlbridge(self) -> None:
        sys.modules.pop("acbllib", None)
        sys.modules.pop("mlBridge", None)
        sys.modules.pop("mlBridge.mlBridgeLib", None)
        importlib.invalidate_caches()

        import bridgestatslib

        self.assertTrue(hasattr(bridgestatslib, "resolve_data_path"))
        self.assertNotIn("acbllib", sys.modules)
        self.assertNotIn("mlBridge", sys.modules)
        self.assertNotIn("mlBridge.mlBridgeLib", sys.modules)

    def test_bridgestats_imports_without_acbllib_or_mlbridge(self) -> None:
        sys.modules.pop("acbllib", None)
        sys.modules.pop("mlBridge", None)
        sys.modules.pop("mlBridge.mlBridgeLib", None)
        importlib.invalidate_caches()

        import bridgestats

        self.assertTrue(hasattr(bridgestats, "Stats"))
        self.assertTrue(hasattr(bridgestats, "api"))
        self.assertNotIn("acbllib", sys.modules)
        self.assertNotIn("mlBridge", sys.modules)
        self.assertNotIn("mlBridge.mlBridgeLib", sys.modules)


if __name__ == "__main__":
    unittest.main()
