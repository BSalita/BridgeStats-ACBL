"""Build datetime caption at the top of the sidebar on every Streamlit page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_SOURCE = Path(__file__).resolve()
_LOGO_URL = (
    "https://github.com/BSalita/BridgeStats-ACBL/blob/master/assets/logo_assistant.gif?raw=true"
)
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
            f'<img src="{_LOGO_URL}" alt="Morty" width="40" height="40" '
            'style="width:2.5rem;height:2.5rem;border-radius:50%;flex:0 0 auto;">'
            f'<div style="font-size:1.05rem;font-weight:700;line-height:1.25;">{_TITLE}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"Build:{app_datetime()}")
