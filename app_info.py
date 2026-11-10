"""Build datetime caption at the top of the sidebar on every Streamlit page."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Optional

import streamlit as st

_SOURCE = Path(__file__).resolve()
ASSISTANT_LOGO_URL = (
    "https://github.com/BSalita/BridgeStats-ACBL/blob/master/assets/logo_assistant.gif?raw=true"
)
SHOW_SQL_KEY = "show_sql_query"
_SHOW_SQL_WIDGET_KEY = "show_sql_query_checkbox"
_TITLE = "ACBL BridgeStats"


def app_datetime() -> str:
    if "app_datetime" not in st.session_state:
        st.session_state.app_datetime = datetime.fromtimestamp(
            _SOURCE.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S %Z")
    return st.session_state.app_datetime


def show_app_datetime() -> None:
    """Gif and short title at the top of the sidebar, as in MortyBridgeChatbot."""
    st.sidebar.markdown(
        (
            '<div style="display:flex;align-items:center;gap:0.6rem;margin:0 0 0.75rem 0;">'
            f'<img src="{ASSISTANT_LOGO_URL}" alt="Morty" width="40" height="40" '
            'style="width:2.5rem;height:2.5rem;border-radius:50%;flex:0 0 auto;">'
            f'<div style="font-size:1.05rem;font-weight:700;line-height:1.25;">{_TITLE}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"Build:{app_datetime()}")


def render_sql_toggle() -> bool:
    """Sidebar separator and "Show SQL query" checkbox, as in MortyBridgeChatbot.

    Call on every page. Streamlit drops widget state when switching pages, so
    the value is kept in st.session_state[SHOW_SQL_KEY] and seeds the widget.
    """
    st.sidebar.markdown("---")
    st.session_state[SHOW_SQL_KEY] = st.sidebar.checkbox(
        "Show SQL query",
        value=bool(st.session_state.get(SHOW_SQL_KEY, False)),
        key=_SHOW_SQL_WIDGET_KEY,
    )
    return st.session_state[SHOW_SQL_KEY]


def show_sql(table: Optional[Mapping[str, Any]]) -> None:
    """Show the SQL that produced an API table, when "Show SQL query" is checked.

    Call just before displaying the table. Requires render_sql_toggle() earlier
    in the run.
    """
    if not st.session_state[SHOW_SQL_KEY]:
        return
    sql = (table or {}).get("sql")
    if not sql:
        raise ValueError(
            "Show SQL query: table has no 'sql' key. Is the BridgeStats API older than this app?"
        )
    st.code(sql, language="sql")


# (label shown in footer, pip distribution name)
KEY_PACKAGES: tuple[tuple[str, str], ...] = (
    ("streamlit", "streamlit"),
    ("pandas", "pandas"),
    ("polars", "polars"),
    ("pyarrow", "pyarrow"),
    ("duckdb", "duckdb"),
    ("numpy", "numpy"),
    ("endplay", "endplay"),
    ("pytorch", "torch"),
    ("scikit-learn", "scikit-learn"),
)


def package_versions_line() -> str:
    """Python plus installed key package versions, e.g. 'Python:3.12.4 streamlit:1.40.0 ...'.

    Reads package metadata, so torch etc. are never imported just for the footer.
    Packages that are not installed are left out.
    """
    parts = [f"Python:{'.'.join(map(str, sys.version_info[:3]))}"]
    for label, dist in KEY_PACKAGES:
        try:
            parts.append(f"{label}:{importlib_metadata.version(dist)}")
        except importlib_metadata.PackageNotFoundError:
            continue
    return " ".join(parts)
