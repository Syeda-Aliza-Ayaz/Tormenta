"""Altair charts in the dashboard's theme. Each returns an unconfigured layer chart; pages call show_chart()."""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src import config

from .data import FC_SERIES, HISTORY_DAYS, SWEEPS
from .theme import TOKENS, style_chart

OBSERVED = "Observed (GFZ)"


def show_chart(chart, theme: str, height: int = None):
    st.altair_chart(style_chart(chart, theme, height), width="stretch", theme=None)


def forecast_long(latest: pd.DataFrame, recent: pd.DataFrame, noaa: pd.DataFrame, col: str,
                  history_days: int = HISTORY_DAYS) -> pd.DataFrame:
    """Observed history + every model's forecast + NOAA's outlook for the same days, as (time, series, value)."""
    obs = recent[col].tail(history_days).rename("value").rename_axis("time").reset_index().assign(series=OBSERVED)
    fc = latest.assign(series=latest["model"].map(FC_SERIES).fillna(latest["model"]))
    fc = fc.rename(columns={"target_date": "time", col: "value"})[["time", "series", "value"]]
    parts = [obs, fc]
    outlook = noaa[noaa["product"] == "27do"] if len(noaa) else noaa
    if len(outlook):
        outlook = outlook[outlook["issued"] == outlook["issued"].max()]
        outlook = outlook[outlook["target_date"].isin(latest["target_date"])]
        parts.append(outlook.rename(columns={"target_date": "time", col: "value"})[["time", "value"]]
                     .assign(series=FC_SERIES["noaa"]))
    return pd.concat(parts, ignore_index=True).dropna(subset=["value"])


def forecast_band(latest: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = latest[latest["model"] == "histgb"]
    if not len(rows) or f"{col}_lo" not in rows or rows[f"{col}_lo"].isna().all():
        return pd.DataFrame()
    return rows.rename(columns={"target_date": "time", f"{col}_lo": "lo", f"{col}_hi": "hi"})[["time", "lo", "hi"]]


def forecast_chart(long: pd.DataFrame, origin: pd.Timestamp, col: str, unit: str, theme: str,
                   band: pd.DataFrame = None):
    """Observed values in ink, forecasts in their own colours, issue day marked, per-day hover columns (D-57)."""
    t = TOKENS[theme]
    names = {v: k for k, v in FC_SERIES.items()}
    present = [s for s in [OBSERVED, *FC_SERIES.values()] if s in set(long["series"])]
    colours = [t["text"] if s == OBSERVED else t["series"].get(names.get(s, ""), t["muted"]) for s in present]
    df = long.assign(time=long["time"].dt.tz_localize("UTC"), label=long["time"].dt.strftime("%a %d %b"))
    colour = alt.Color("series:N", scale=alt.Scale(domain=present, range=colours),
                       legend=alt.Legend(orient="top", title=None, symbolStrokeWidth=3))
    top = 9 if col == "kpmax" else max(40.0, float(df["value"].max()) * 1.1)
    y = alt.Y("value:Q", scale=alt.Scale(domain=[0, top]), title=unit,
              axis=alt.Axis(grid=True, tickCount=10 if col == "kpmax" else 8, titlePadding=10))
    x = alt.X("time:T", scale=alt.Scale(type="utc"), title=None,
              axis=alt.Axis(format="%d %b", labelAngle=0, grid=False, tickCount={"interval": "day", "step": 2},
                            labelOverlap=True, labelPadding=8))
    lines = alt.Chart(df).mark_line(strokeWidth=2.2, point=alt.OverlayMarkDef(size=30, filled=True)).encode(
        x=x, y=y, color=colour, detail="series:N")
    start = origin + pd.Timedelta(hours=12)
    ahead = pd.DataFrame({"start": [start.tz_localize("UTC")], "end": [df["time"].max() + pd.Timedelta(hours=12)],
                          "text": ["FORECAST →"]})
    shade = alt.Chart(ahead).mark_rect(color=t["primary"], opacity=0.05).encode(x="start:T", x2="end:T")
    shade_text = alt.Chart(ahead).mark_text(align="left", dx=8, y=10, color=t["muted"], fontSize=11).encode(
        x="start:T", text="text:N")
    wide = df.pivot_table(index=["time", "label"], columns="series", values="value").reset_index()
    keys = {s: f"s{i}" for i, s in enumerate(present)}
    wide = wide.rename(columns=keys)
    wide = wide.assign(start=wide["time"] - pd.Timedelta(hours=12), end=wide["time"] + pd.Timedelta(hours=12))
    is_past = wide["time"] <= origin.tz_localize("UTC")
    rules, hovers = [], []
    for region, name in [(wide[is_past], "hover_past"), (wide[~is_past], "hover_forecast")]:
        if not len(region):
            continue
        shown = [(s, k) for s, k in keys.items() if k in region and region[k].notna().all()]
        tips = [alt.Tooltip("label:N", title="Day")] + [
            alt.Tooltip(f"{k}:Q", title=s, format=".1f" if col == "kpmax" else ".0f") for s, k in shown]
        hover = alt.selection_point(name=name, on="pointerover", fields=["time"], empty=False, clear="pointerout")
        hovers.append(hover)
        data = region[["time", "start", "end", "label"] + [k for _, k in shown]]
        rules.append(alt.Chart(data).mark_rect(color=t["primary"]).encode(
            x=alt.X("start:T", scale=alt.Scale(type="utc")), x2="end:T",
            opacity=alt.condition(hover, alt.value(0.08), alt.value(0.001)), tooltip=tips).add_params(hover))
        rules.append(alt.Chart(data).mark_rule(color=t["muted"], strokeWidth=1).encode(
            x="time:T", opacity=alt.condition(hover, alt.value(0.8), alt.value(0))))
    any_hover = hovers[0] if len(hovers) == 1 else hovers[0] | hovers[1]
    dots = alt.Chart(df).mark_point(filled=True, size=80).encode(
        x=x, y=y, color=colour, opacity=alt.condition(any_hover, alt.value(1), alt.value(0)))
    values = alt.Chart(df).mark_text(align="left", dx=9, dy=-9, fontSize=11, fontWeight=600).encode(
        x=x, y=y, color=colour, text=alt.Text("value:Q", format=".1f" if col == "kpmax" else ".0f"),
        opacity=alt.condition(any_hover, alt.value(1), alt.value(0)))
    layers = [shade, shade_text, lines, dots, values, *rules]
    if band is not None and len(band):
        b = band.assign(time=band["time"].dt.tz_localize("UTC"))
        layers.insert(2, alt.Chart(b).mark_area(opacity=t["band"], color=t["primary"]).encode(
            x=alt.X("time:T", scale=alt.Scale(type="utc")), y="lo:Q", y2="hi:Q"))
    if col == "kpmax":
        storm = alt.Chart(pd.DataFrame({"v": [config.STORM_THRESHOLD], "text": ["STORM LEVEL · KP 5−"]}))
        layers.insert(2, storm.mark_rule(strokeDash=[6, 4], color=t["alert"]).encode(y="v:Q"))
        layers.insert(3, storm.mark_text(align="left", dx=4, dy=-7, color=t["alert_text"], fontSize=11).encode(
            y="v:Q", text="text:N", x=alt.value(0)))
    return alt.layer(*layers).properties(height=340)


def _utc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    pk = out.index + pd.Timedelta(hours=5)                 # shown in Pakistan time (UTC+5)
    out["label"] = pk.strftime("%d %b %H:00 PKT")
    out["time"] = pk.tz_localize("UTC")                     # a UTC axis over shifted times prints PKT
    return out.reset_index(drop=True)


def live_chart(live: pd.DataFrame, theme: str):
    """Nowcast line + 80% band vs observed Kp steps, crosshair tooltip, ahead-of-now shading."""
    t = TOKENS[theme]
    df = _utc(live)
    cols = {"kp_pred": "Tormenta nowcast", "kp_gfz": "GFZ quick-look Kp", "kp_swpc": "NOAA estimated Kp"}
    colours = {"kp_pred": t["primary"], "kp_gfz": t["text"], "kp_swpc": t["series"]["noaa"]}
    present = [c for c in cols if c in df]
    long = df.melt(id_vars=["time"], value_vars=present, var_name="col", value_name="kp").dropna()
    long["series"] = long["col"].map(cols)
    colour = alt.Color("series:N", scale=alt.Scale(domain=[cols[c] for c in present], range=[colours[c] for c in present]),
                       legend=alt.Legend(orient="top", title=None))
    x = alt.X("time:T", scale=alt.Scale(type="utc"), title=None,
              axis=alt.Axis(format="%d %b %H:00", labelAngle=0, grid=False, tickCount=6, labelOverlap=True, labelPadding=8))
    y = alt.Y("kp:Q", scale=alt.Scale(domain=[0, 9]), title="Kp", axis=alt.Axis(tickCount=10, grid=True, titlePadding=10))
    band = alt.Chart(df).mark_area(opacity=t["band"], color=t["primary"]).encode(
        x=x, y=alt.Y("kp_lo:Q", scale=alt.Scale(domain=[0, 9])), y2="kp_hi:Q")
    pred = alt.Chart(long[long["col"] == "kp_pred"]).mark_line(strokeWidth=2.2).encode(x=x, y=y, color=colour)
    obs = alt.Chart(long[long["col"] != "kp_pred"]).mark_line(strokeWidth=2, interpolate="step-after").encode(x=x, y=y, color=colour)
    storm = alt.Chart(pd.DataFrame({"kp": [config.STORM_THRESHOLD], "text": ["STORM LEVEL"]}))
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["time"], empty=False, clear="pointerout")
    tips = [alt.Tooltip("label:N", title="Hour"), alt.Tooltip("kp_pred:Q", title="Tormenta", format=".1f"),
            alt.Tooltip("kp_lo:Q", title="80% low", format=".1f"), alt.Tooltip("kp_hi:Q", title="80% high", format=".1f")]
    tips += [alt.Tooltip(f"{c}:Q", title=cols[c].split(" ")[0], format=".2f") for c in present[1:]]
    rule = alt.Chart(df).mark_rule(color=t["muted"], strokeWidth=1).encode(
        x=x, opacity=alt.condition(hover, alt.value(0.8), alt.value(0)), tooltip=tips).add_params(hover)
    dots = alt.Chart(long).mark_point(filled=True, size=70).encode(
        x=x, y=y, color=colour, opacity=alt.condition(hover, alt.value(1), alt.value(0)))
    layers = [band, storm.mark_rule(strokeDash=[6, 4], color=t["alert"]).encode(y="kp:Q"),
              storm.mark_text(align="left", dx=4, dy=-7, color=t["alert_text"], fontSize=11).encode(y="kp:Q", text="text:N", x=alt.value(0)),
              pred, obs, dots,
              alt.Chart(long).mark_text(align="left", dx=9, dy=-9, fontSize=11, fontWeight=600).encode(
                  x=x, y=y, color=colour, text=alt.Text("kp:Q", format=".1f"),
                  opacity=alt.condition(hover, alt.value(1), alt.value(0))),
              rule]
    if df["ahead"].any():
        ahead = pd.DataFrame({"start": [df.loc[df["ahead"], "time"].min()], "end": [df["time"].max()]})
        layers.insert(0, alt.Chart(ahead).mark_rect(color=t["primary"], opacity=0.06).encode(
            x=alt.X("start:T", scale=alt.Scale(type="utc")), x2="end:T"))
    return alt.layer(*layers).properties(height=320)


def sweep_chart(values: dict, label: str, predict, theme: str):
    """What-if: Kp (+ 80% range) as one input varies, the others held at the entered values."""
    t = TOKENS[theme]
    col, grid = SWEEPS[label]
    rows = []
    for v in grid:
        x = {**values, col: float(v)}
        x["b_scalar"] = max(x["b_scalar"], float(np.sqrt(x["bx"] ** 2 + x["by_gsm"] ** 2 + x["bz_gsm"] ** 2)))
        out = predict(x)
        rows.append({"x": float(v), "kp": out["kp_pred"], "lo": out["kp_lo"], "hi": out["kp_hi"]})
    df = pd.DataFrame(rows)
    xs = alt.X("x:Q", title=label, axis=alt.Axis(grid=False))
    ys = alt.Y("kp:Q", scale=alt.Scale(domain=[0, 9]), title="predicted Kp")
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["x"], empty=False, clear="pointerout")
    band = alt.Chart(df).mark_area(opacity=t["band"], color=t["primary"]).encode(x=xs, y=alt.Y("lo:Q"), y2="hi:Q")
    line = alt.Chart(df).mark_line(strokeWidth=2.5, color=t["primary"]).encode(x=xs, y=ys)
    pts = alt.Chart(df).mark_point(filled=True, size=70, color=t["primary"]).encode(
        x=xs, y=ys, opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("x:Q", title=label, format=".1f"), alt.Tooltip("kp:Q", title="Kp", format=".1f"),
                 alt.Tooltip("lo:Q", title="80% low", format=".1f"), alt.Tooltip("hi:Q", title="80% high", format=".1f")]
    ).add_params(hover)
    you = alt.Chart(pd.DataFrame({"x": [values[col]], "t": ["your input"]}))
    storm = alt.Chart(pd.DataFrame({"kp": [config.STORM_THRESHOLD]})).mark_rule(strokeDash=[6, 4], color=t["alert"]).encode(y="kp:Q")
    return alt.layer(band, storm, you.mark_rule(color=t["muted"], strokeDash=[3, 3]).encode(x="x:Q"),
                     you.mark_text(align="left", dx=4, y=8, color=t["muted"], fontSize=11).encode(x="x:Q", text="t:N"),
                     line, pts).properties(height=300)


def rmse_by_lead(period_leads: pd.DataFrame, theme: str):
    """Ap RMSE per lead day for the headline, NOAA, ARIMAX, Chronos and the 27-day average."""
    t = TOKENS[theme]
    keep = ["histgb", "noaa", "arimax", "chronos", "trailing27"]
    df = period_leads[(period_leads["target"] == "ap") & period_leads["model"].isin(keep)].copy()
    df["series"] = df["model"].map(FC_SERIES)
    domain = [FC_SERIES[m] for m in keep if m in set(df["model"])]
    rng = [t["series"][m] if m != "trailing27" else t["muted"] for m in keep if m in set(df["model"])]
    colour = alt.Color("series:N", scale=alt.Scale(domain=domain, range=rng), legend=alt.Legend(orient="top", title=None))
    lo, hi = float(df["rmse"].min()), float(df["rmse"].max())
    pad = (hi - lo) * 0.15 or 0.5
    base = alt.Chart(df).encode(
        x=alt.X("lead:O", title="Lead day", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("rmse:Q", title="Ap error (RMSE)", scale=alt.Scale(domain=[lo - pad, hi + pad], zero=False)),
        color=colour, tooltip=[alt.Tooltip("series:N", title="Model"), alt.Tooltip("lead:O", title="Lead day"),
                               alt.Tooltip("rmse:Q", title="RMSE", format=".2f"),
                               alt.Tooltip("skill_vs_trailing27:Q", title="Skill vs 27-day", format="+.3f")])
    width = alt.condition(alt.datum.model == "histgb", alt.value(3.2), alt.value(1.8))
    return alt.layer(base.mark_line().encode(strokeWidth=width),
                     base.mark_point(filled=True, size=60)).properties(height=300)


def monitor_chart(windows: pd.DataFrame, floor: float, theme: str):
    t = TOKENS[theme]
    df = windows.assign(time=pd.to_datetime(windows["window_end"]).dt.tz_localize("UTC"))
    x = alt.X("time:T", scale=alt.Scale(type="utc"), title=None,
              axis=alt.Axis(format="%Y", grid=False, tickCount={"interval": "year", "step": 1}, labelPadding=8))
    line = alt.Chart(df).mark_line(strokeWidth=2, color=t["primary"]).encode(
        x=x, y=alt.Y("skill:Q", title="56-day skill vs 27-day average"),
        tooltip=[alt.Tooltip("window_end:N", title="Window ends"), alt.Tooltip("skill:Q", format=".2f")])
    fl = alt.Chart(pd.DataFrame({"v": [floor], "t": [f"degraded below {floor:.2f}"]}))
    due = alt.Chart(df[df["retrain_due"]]).mark_point(filled=True, size=70, color=t["alert"]).encode(
        x=x, y="skill:Q", tooltip=[alt.Tooltip("window_end:N", title="Retrain would be due")])
    return alt.layer(fl.mark_rule(strokeDash=[6, 4], color=t["alert"]).encode(y="v:Q"),
                     fl.mark_text(align="left", dx=4, dy=-7, color=t["alert_text"], fontSize=11).encode(
                         y="v:Q", text="t:N", x=alt.value(0)), line, due).properties(height=260)


def nowcast_models_chart(table: pd.DataFrame, theme: str):
    t = TOKENS[theme]
    table = table.drop(index=[i for i in table.index if i.startswith("Ensemble")], errors="ignore")
    table = table.assign(model=table.index.str.replace(" (baseline)", "", regex=False),
                         role=np.where(table.index == "HistGB", "production model", "comparison"))
    bars = alt.Chart(table).mark_bar(cornerRadiusEnd=3, height=16).encode(
        x=alt.X("rmse:Q", title="RMSE (Kp units)", scale=alt.Scale(domain=[0, 0.95])),
        y=alt.Y("model:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220, labelPadding=8)),
        color=alt.Color("role:N", scale=alt.Scale(domain=["production model", "comparison"], range=[t["primary"], t["hair"]]),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("model:N", title="Model"), alt.Tooltip("rmse:Q", title="RMSE", format=".3f"),
                 alt.Tooltip("storm_rmse:Q", title="Storm RMSE", format=".3f"), alt.Tooltip("r2:Q", title="R²", format=".3f")])
    labels = bars.mark_text(align="left", dx=4, fontSize=11).encode(text=alt.Text("rmse:Q", format=".3f"), color=alt.value(t["muted"]))
    return alt.layer(bars, labels).properties(height=230, padding={"left": 8, "right": 8})
