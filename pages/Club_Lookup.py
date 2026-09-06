# todo:
# 1. put club lookup into bridgestats.py (and elsewhere?) to validate club entries.

import pathlib
import sys
import time

import streamlit as st

_APP_DIR = pathlib.Path(__file__).resolve().parent.parent
_SRC_DIR = _APP_DIR.parent
_streamlit = next(
    (p for p in (_APP_DIR / "streamlitlib", _SRC_DIR / "streamlitlib") if p.is_dir()),
    None,
)
if _streamlit is None:
    raise FileNotFoundError(f"streamlitlib not found under {_APP_DIR} or {_SRC_DIR}")
for _p in (_SRC_DIR, _streamlit):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.append(_s)
import streamlitlib  # must be placed after sys.path.append. vscode re-format likes to move this to the top

import bridgestats_api_client as api

st.header("Lookup Club Information")
st.sidebar.header("Settings for Club Lookup")
st.sidebar.header("Settings")

clubs = st.sidebar.text_input(
    "Narrow search to these ACBL club numbers. Enter one or more 6 digit numbers (empty means all):",
    placeholder="Enter list of ACBL club numbers",
    key="Club_Lookup-Club",
    help="Example: 108571 (Fort Lauderdale Bridge Club",
)
club_names = st.sidebar.text_input(
    "Narrow search to these club names. Enter one or more club names (empty means all):",
    placeholder="Enter list of club names",
    key="Club_Lookup-Club_Name",
)

with st.spinner(text="Reading data ..."):
    start_time = time.time()
    try:
        payload = api.club_lookup(clubs=clubs, names=club_names, limit=2000)
    except api.BridgeStatsApiClientError as exc:
        st.error(str(exc))
        st.stop()
    selected_df = api.table_to_frame(payload)
    st.caption(f"Data read completed in {round(time.time() - start_time, 2)} seconds.")

table, charts = st.tabs(["Data Table", "Charts"])
st.caption(
    f"Database has {payload.get('total', selected_df.height)} rows. {selected_df.height} rows selected."
)
if selected_df.height == 0:
    st.warning("No rows selected")
    st.stop()

with table:
    with st.spinner(text="Creating data table ..."):
        start_time = time.time()
        streamlitlib.ShowDataFrameTable(selected_df)
        st.caption(f"Data table created in {round(time.time() - start_time, 2)} seconds.")

with charts:
    pass
