from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def find_project_root() -> Path:
    root = Path.cwd().resolve()
    while root != root.parent:
        if (root / "data_processed").exists() or (root / "data_raw").exists():
            return root
        root = root.parent
    return Path.cwd().resolve()


@st.cache_data(show_spinner=False)
def load_data(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    data_dir = root / "data_processed"
    df = pd.read_parquet(data_dir / "fact_batches.parquet")
    dt_long = pd.read_parquet(data_dir / "fact_downtime_long.parquet")

    # normalize types
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Batch"] = pd.to_numeric(df["Batch"], errors="coerce").astype("Int64")

    dt_long = dt_long.copy()
    dt_long["Batch"] = pd.to_numeric(dt_long["Batch"], errors="coerce").astype("Int64")
    return df, dt_long


def make_pareto(df_reasons: pd.DataFrame) -> go.Figure:
    d = df_reasons.sort_values("downtime_min", ascending=False).copy()
    total = d["downtime_min"].sum()
    d["cum_pct"] = d["downtime_min"].cumsum() / total if total else 0

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=d["Description"],
            y=d["downtime_min"],
            name="Downtime (min)",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=d["Description"],
            y=d["cum_pct"],
            name="Cumulative %",
            yaxis="y2",
            mode="lines+markers",
        )
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(title="Downtime Reason", tickangle=-25),
        yaxis=dict(title="Minutes"),
        yaxis2=dict(
            title="Cumulative %",
            overlaying="y",
            side="right",
            tickformat=".0%",
            range=[0, 1.05],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="Manufacturing KPI Overview", layout="wide")
    st.title("Manufacturing KPI Overview")

    root = find_project_root()
    st.caption(f"Project root: `{root}`")

    try:
        df, dt_long = load_data(root)
    except FileNotFoundError:
        st.error(
            "Parquet files not found:\n"
            "- data_processed/fact_batches.parquet\n"
            "- data_processed/fact_downtime_long.parquet"
        )
        st.stop()

    dt_join = dt_long.merge(
        df[["Batch", "Date", "Product", "Operator"]],
        on="Batch",
        how="left",
    )

    # Sidebar filters 
    st.sidebar.header("Filters")

    # date range
    min_date = df["Date"].min()
    max_date = df["Date"].max()

    if pd.isna(min_date) or pd.isna(max_date):
        st.error("Kolom Date tidak terbaca dengan benar.")
        st.stop()

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    else:
        start_date = pd.to_datetime(min_date.date())
        end_date = pd.to_datetime(max_date.date())

    products = ["All"] + sorted([p for p in df["Product"].dropna().unique().tolist()])
    operators = ["All"] + sorted([o for o in df["Operator"].dropna().unique().tolist()])

    selected_product = st.sidebar.selectbox("Product", products, index=0)
    selected_operator = st.sidebar.selectbox("Operator", operators, index=0)

    # apply filters
    mask = (df["Date"] >= start_date) & (df["Date"] <= end_date)
    if selected_product != "All":
        mask &= df["Product"] == selected_product
    if selected_operator != "All":
        mask &= df["Operator"] == selected_operator

    dff = df.loc[mask].copy()

    mask_dt = (dt_join["Date"] >= start_date) & (dt_join["Date"] <= end_date)
    if selected_product != "All":
        mask_dt &= dt_join["Product"] == selected_product
    if selected_operator != "All":
        mask_dt &= dt_join["Operator"] == selected_operator

    dtf = dt_join.loc[mask_dt].copy()

    if dff.empty:
        st.warning("Tidak ada data untuk filter yang dipilih.")
        st.stop()

    # KPI cards 
    total_downtime = float(dff["downtime_total_min"].sum())
    avg_downtime_rate = float(dff["downtime_rate"].mean())
    avg_run_ratio = (
        float(dff["run_ratio"].mean())
        if "run_ratio" in dff.columns
        else float((dff["actual_run_min"] / dff["duration_min"]).mean())
    )
    total_batches = int(dff["Batch"].nunique())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Downtime (min)", f"{total_downtime:,.0f}")
    c2.metric("Avg Downtime Rate", f"{avg_downtime_rate:.1%}")
    c3.metric("Avg Run Ratio", f"{avg_run_ratio:.1%}")
    c4.metric("Batches", f"{total_batches:,}")

    st.divider()

    # Daily trend 
    daily = dff.copy()
    daily["day"] = pd.to_datetime(daily["Date"], errors="coerce").dt.date

    daily = daily.groupby("day", as_index=False).agg(
        total_downtime=("downtime_total_min", "sum"),
        avg_downtime_rate=("downtime_rate", "mean"),
        avg_duration=("duration_min", "mean"),
    ).sort_values("day")

    left, right = st.columns(2)

    with left:
        fig1 = px.line(daily, x="day", y="total_downtime", markers=True, title="Daily Total Downtime (min)")
        fig1.update_layout(margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig1, use_container_width=True)

    with right:
        fig2 = px.line(daily, x="day", y="avg_downtime_rate", markers=True, title="Daily Avg Downtime Rate")
        fig2.update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis_tickformat=".0%")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    st.subheader("Top Downtime Reasons (Pareto)")

    reasons = (
        dtf.groupby("Description", as_index=False)["downtime_min"]
        .sum()
        .sort_values("downtime_min", ascending=False)
        .head(12)
    )

    if reasons.empty:
        st.info("Tidak ada downtime reasons di filter ini.")
    else:
        pareto_fig = make_pareto(reasons)
        st.plotly_chart(pareto_fig, use_container_width=True)

    st.divider()

    # Worst batches table 
    st.subheader("Worst Batches (Highest Downtime)")
    worst = (
        dff.sort_values("downtime_total_min", ascending=False)
        .loc[:, ["Date", "Batch", "Product", "Operator", "duration_min", "downtime_total_min", "downtime_rate", "actual_run_min"]]
        .head(15)
    )
    st.dataframe(worst, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
