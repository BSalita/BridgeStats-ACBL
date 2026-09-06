"""Render BridgeStats chart payloads in Streamlit. Does not import the lib."""

from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd
import streamlit as st


def render_chart_payloads(payloads: Iterable[Dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    figsize = (26, 2)
    for chart in payloads:
        kind = chart.get("kind")
        title = chart.get("title") or ""
        if kind == "info":
            st.info(title)
            continue
        if kind == "empty":
            st.info(title or "No data available for charts.")
            continue
        if kind == "heatmap":
            index = chart.get("index") or []
            x_labels = chart.get("x_labels") or []
            values = chart.get("values") or []
            if not values:
                st.info(f"No data to plot for chart: {title}")
                continue
            frame = pd.DataFrame(values, index=index, columns=x_labels)
            fig, ax = plt.subplots(figsize=(10, 4))
            image = ax.imshow(frame.to_numpy(), aspect="auto")
            ax.set_xticks(range(len(frame.columns)), list(frame.columns), rotation=45)
            ax.set_yticks(range(len(frame.index)), list(frame.index))
            ax.set_title(title)
            fig.colorbar(image, ax=ax, label=chart.get("zlabel") or "")
            st.pyplot(fig, clear_figure=True)
            plt.close(fig)
            continue
        series = chart.get("series") or {}
        if not series:
            st.info(f"No data available for chart: {title}")
            continue
        try:
            df_to_plot = pd.DataFrame(series)
            if df_to_plot.empty:
                st.info(f"No data to plot for chart: {title}")
                continue
            ax = df_to_plot.plot(
                kind="bar",
                figsize=figsize,
                title=title,
                ylabel="Percentage Frequency",
            )
            if kind == "bar" and any("(" in name for name in series):
                ax.legend(title="(Player Number, Player Name)")
            st.pyplot(plt, clear_figure=True)
            plt.close("all")
        except Exception as exc:
            st.warning(f"Failed to create chart for {title}: {exc}")
