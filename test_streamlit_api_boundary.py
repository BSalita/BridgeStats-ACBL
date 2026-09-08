"""Streamlit must reach BridgeStats data only through the REST API client."""

from __future__ import annotations

import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
STREAMLIT_FILES = (
    ROOT / "bridgestats.py",
    ROOT / "handstats.py",
    ROOT / "player_sidebar.py",
    ROOT / "bridgestats_charts.py",
    ROOT / "Home.py",
    ROOT / "pages" / "Club_Lookup.py",
    ROOT / "pages" / "Player_Lookup.py",
    ROOT / "pages" / "Club_Player_Statistics.py",
    ROOT / "pages" / "Club_Player_Session_Statistics.py",
    ROOT / "pages" / "Club_Pair_Statistics.py",
    ROOT / "pages" / "Club_Pair_Session_Statistics.py",
    ROOT / "pages" / "Club_Hand_Record_Statistics.py",
    ROOT / "pages" / "Tournament_Player_Statistics.py",
    ROOT / "pages" / "Tournament_Player_Session_Statistics.py",
    ROOT / "pages" / "Tournament_Pair_Statistics.py",
    ROOT / "pages" / "Tournament_Pair_Session_Statistics.py",
    ROOT / "pages" / "Tournament_Hand_Record_Statistics.py",
)
FORBIDDEN_MODULES = {
    "bridgestatslib",
}
CLIENT_FILES = {
    "bridgestats.py",
    "handstats.py",
    "player_sidebar.py",
    "Club_Lookup.py",
    "Player_Lookup.py",
}


class StreamlitApiBoundaryTests(unittest.TestCase):
    def test_streamlit_does_not_import_the_library(self) -> None:
        for path in STREAMLIT_FILES:
            with self.subTest(file=path.name):
                self.assertTrue(path.is_file(), f"Missing Streamlit file: {path}")
                source = path.read_text(encoding="utf-8-sig")
                tree = ast.parse(source)
                modules: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        modules.add(node.module)
                violations = {module for module in modules if module in FORBIDDEN_MODULES}
                self.assertFalse(
                    violations,
                    f"{path.name} bypasses the REST API: {sorted(violations)}",
                )
                if path.name in CLIENT_FILES:
                    self.assertIn("bridgestats_api_client", modules)


if __name__ == "__main__":
    unittest.main()
