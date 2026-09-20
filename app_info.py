"""Build datetime captions used at the top of every Streamlit page."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_SOURCE = Path(__file__).resolve()


def app_datetime() -> str:
    if "app_datetime" not in st.session_state:
        st.session_state.app_datetime = datetime.fromtimestamp(
            _SOURCE.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S %Z")
    return st.session_state.app_datetime


def show_app_datetime() -> None:
    stamp = app_datetime()
    st.caption(
        f"App:{stamp} Streamlit:{st.__version__} "
        f"Query Params:{st.query_params.to_dict()} "
        f"Environment:{os.getenv('STREAMLIT_ENV', '')}"
    )
    st.sidebar.caption(f"Build:{stamp}")
