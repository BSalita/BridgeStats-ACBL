# todo:
# 1. Replace Club, and Player entry with delux code in bridgestats.

import pathlib
import sys
import time

import altair as alt
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

st.header("Lookup Player Information")
st.sidebar.header("Settings for Player Lookup")
st.sidebar.header("Settings")

key_prefix = "Player_Lookup"
clubs = st.sidebar.text_input(
    "Narrow search to these ACBL club numbers. Enter one or more 6 digit ACBL club numbers (empty means all):",
    placeholder="Enter list of ACBL club numbers",
    key=key_prefix + "-Club",
    help="Example: 108571 (Fort Lauderdale Bridge Club",
)
player_numbers = st.sidebar.text_input(
    "Narrow search to these ACBL player numbers. Enter one or more 7 digit numbers (empty means all):",
    placeholder="Enter list of ACBL numbers",
    key=key_prefix + "-ACBL_number",
)
player_names = st.sidebar.text_input(
    "Narrow search to these last names. Enter one or more last names (empty means all):",
    placeholder="Enter list of last names",
    key=key_prefix + "-Last_Name",
)

with st.spinner(text="Reading data ..."):
    start_time = time.time()
    try:
        payload = api.player_lookup(
            clubs=clubs,
            numbers=player_numbers,
            names=player_names,
            limit=2000,
        )
    except api.BridgeStatsApiClientError as exc:
        st.error(str(exc))
        st.stop()
    selected_df = api.table_to_frame(payload)
    st.caption(
        f"Data read completed in {round(time.time() - start_time, 2)} seconds. "
        f"{payload.get('total', selected_df.height)} rows read."
    )

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
    with st.spinner(text="Creating charts ..."):
        start_time = time.time()
        if "rank_description" in selected_df.columns:
            chart_df = selected_df.to_pandas()
            col = "rank_description"
            c = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    alt.X(f"count({col}):Q", title="Count"),
                    alt.Y(f"{col}:N", title=col.replace("_", " ").title(), sort="-x"),
                )
                .properties(width=1000, height=500, title=f"Frequency of {col.replace('_', ' ').title()}")
                .configure_axis(labelFontSize=14, titleFontSize=20, labelLimit=200, titleFontWeight="bold")
                .configure_title(fontSize=20, offset=5, orient="top", anchor="middle")
            )
            st.altair_chart(c)
        st.caption(f"Charts created in {round(time.time() - start_time, 2)} seconds.")
