"""Tormenta Streamlit dashboard: live Kp nowcast, what-if explorer, model card.

Local:  .venv\\Scripts\\streamlit run app\\streamlit_app.py
Cloud:  Streamlit Community Cloud, main file app/streamlit_app.py, Python 3.12, requirements.txt at repo root.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

from src import config, scoring  # noqa: E402  (numpy-only helpers, no scikit-learn)
from src.ingest import fetch_live  # noqa: E402
from src.predict import INPUT_LIMITS, load_bundle, nowcast, predict_steady, validate_inputs  # noqa: E402

st.set_page_config(page_title="Tormenta Kp Forecast", page_icon="🧲", layout="wide")

IN_BROWSER = sys.platform == "emscripten"           # Hugging Face static Space: stlite (Streamlit on Pyodide)
NETWORK_ERRORS = (requests.RequestException,)
if IN_BROWSER:
    from pyodide.ffi import JsException             # browser fetch failures surface as JS exceptions
    NETWORK_ERRORS += (JsException,)
LIVE_ERRORS = NETWORK_ERRORS + (ValueError, KeyError, IndexError)

# ── Look ─────────────────────────────────────────────────────────────────────
# Series colours: validated categorical slots 1–3 (light / dark steps). Level colours: fixed status palette,
# always shown with a label and icon so colour never carries meaning alone.
MODE = "dark" if st.context.theme.type == "dark" else "light"
SERIES = ["Tormenta nowcast", "GFZ quick-look Kp", "NOAA estimated Kp"]
SERIES_COLORS = {"light": ["#2a78d6", "#eb6834", "#1baf7a"], "dark": ["#3987e5", "#d95926", "#199e70"]}[MODE]
MUTED = {"light": "#8a8985", "dark": "#7d7c77"}[MODE]
_B = config.KP_BINS        # NOAA level edges used everywhere in the project: 3.5, 4.5, 5.5, 6.5
LEVELS = [  # (lower Kp, upper Kp, short, name, colour, icon, what it means)
    (_B[0], _B[1], "0–3", "Quiet", "#0ca30c", "🟢",
     "Quiet to unsettled. Aurora only near the poles; no effect on technology."),
    (_B[1], _B[2], "4", "Active", "#fab219", "🟡",
     "Active. Aurora possible at high latitudes (northern Scandinavia, Alaska, northern Canada)."),
    (_B[2], _B[3], "G1", "Minor storm", "#ec835a", "🟠",
     "Minor storm. Weak power-grid fluctuations possible; aurora visible around 60° geomagnetic latitude."),
    (_B[3], _B[4], "G2", "Moderate storm", "#d03b3b", "🔴",
     "Moderate storm. High-latitude power systems may see voltage alarms; aurora down to about 55°."),
    (_B[4], 9, "G3+", "Strong to extreme storm", "#d03b3b", "🚨",
     "Strong to extreme storm. GPS and HF radio disruption and power-grid problems possible; aurora can reach "
     "mid-latitudes."),
]
DEFAULTS = {"b_scalar": 5.0, "bx": 1.0, "by_gsm": 2.0, "bz_gsm": 0.0, "speed": 400.0, "density": 5.0,
            "temperature": 100000.0, "f107": 120.0}
PRESETS = {
    "🌤️ Quiet day": DEFAULTS,
    "💨 Fast solar wind": {**DEFAULTS, "b_scalar": 8.0, "bz_gsm": -4.0, "speed": 650.0, "density": 3.0,
                          "temperature": 250000.0},
    "☄️ CME arrival": {"b_scalar": 20.0, "bx": 3.0, "by_gsm": 5.0, "bz_gsm": -15.0, "speed": 600.0,
                       "density": 10.0, "temperature": 200000.0, "f107": 150.0},
    "🌌 May 2024 superstorm": {"b_scalar": 70.0, "bx": 3.0, "by_gsm": 20.0, "bz_gsm": -45.0, "speed": 800.0,
                              "density": 30.0, "temperature": 600000.0, "f107": 200.0},
}
STEPS = {"speed": 10.0, "temperature": 10000.0, "f107": 1.0}
SWEEPS = {"Bz GSM (nT)": ("bz_gsm", np.arange(-40, 15.1, 2.5)), "speed (km/s)": ("speed", np.arange(300, 1001, 50)),
          "density (cm⁻³)": ("density", np.arange(1, 41, 2))}

st.markdown("""<style>
.kp-chip { display: inline-block; padding: 2px 10px; border-radius: 99px; font-weight: 600; font-size: .9rem;
           border: 2px solid var(--chip); }
.kp-gauge { position: relative; margin: 14px 0 4px; }
.kp-track { display: flex; gap: 2px; height: 16px; }
.kp-seg { border-radius: 4px; opacity: .45; }
.kp-band { position: absolute; top: -4px; height: 24px; border: 2px solid currentColor; border-radius: 6px; }
.kp-mark { position: absolute; top: -8px; width: 4px; height: 32px; margin-left: -2px; background: currentColor;
           border-radius: 2px; }
.kp-ticks { display: flex; justify-content: space-between; font-size: .75rem; opacity: .7; margin-top: 6px; }
.kp-caption { font-size: .85rem; opacity: .8; }
</style>""", unsafe_allow_html=True)


def level_of(kp: float):
    kp = round(kp, 1)                                # level of the number shown on screen
    return next(lv for lv in LEVELS if kp < lv[1] or lv is LEVELS[-1])


def kp_card(kp: float, lo: float, hi: float, when: str):
    """Hero number + storm-level chip + 0–9 gauge with the 80% range + plain-language meaning."""
    _, _, short, name, colour, icon, meaning = level_of(kp)
    segs = "".join(f'<div class="kp-seg" style="flex:{b - a};background:{c}" title="{s}: {n}"></div>'
                   for a, b, s, n, c, *_ in LEVELS)
    st.markdown(f"""
<p class="kp-caption">{when}</p>
<div style="font-size:3.4rem;font-weight:700;line-height:1.05;margin:2px 0 8px">Kp {kp:.1f}</div>
<span class="kp-chip" style="--chip:{colour}">{icon} {short} · {name}</span>
<div class="kp-gauge">
  <div class="kp-track">{segs}</div>
  <div class="kp-band" style="left:{lo / 9:.2%};width:{max(hi - lo, 0.05) / 9:.2%}"
       title="80% range {lo:.1f}–{hi:.1f}"></div>
  <div class="kp-mark" style="left:{kp / 9:.2%}"></div>
  <div class="kp-ticks">{''.join(f'<span>{i}</span>' for i in range(10))}</div>
</div>
<p class="kp-caption">80% range <b>{lo:.1f}–{hi:.1f}</b> (the outlined box). {meaning}</p>
""", unsafe_allow_html=True)


def utc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["label"] = out.index.strftime("%d %b %H:00 UTC")
    out["time"] = out.index.tz_localize("UTC")
    return out.reset_index(drop=True)


def x_time(title=None):
    return alt.X("time:T", scale=alt.Scale(type="utc"), title=title,
                 axis=alt.Axis(format="%d %b", labelAngle=0, grid=False, tickCount=6))


def live_chart(live: pd.DataFrame) -> alt.LayerChart:
    """Nowcast line + 80% band vs observed Kp steps, hover crosshair with all values, ahead-of-now shading."""
    df = utc(live)
    cols = {"kp_pred": SERIES[0], "kp_gfz": SERIES[1], "kp_swpc": SERIES[2]}
    present = [c for c in cols if c in df]
    long = df.melt(id_vars=["time"], value_vars=present, var_name="col", value_name="kp").dropna()
    long["series"] = long["col"].map(cols)
    domain = [cols[c] for c in present]
    # colour follows the series, not its position: NOAA stays green even when GFZ is absent (browser app)
    colour = alt.Color("series:N", scale=alt.Scale(domain=domain, range=[SERIES_COLORS[SERIES.index(d)] for d in domain]),
                       legend=alt.Legend(orient="top", title=None, symbolStrokeWidth=3))
    y = alt.Y("kp:Q", scale=alt.Scale(domain=[0, 9]), title="Kp", axis=alt.Axis(tickCount=10))

    band = alt.Chart(df).mark_area(opacity=0.18, color=SERIES_COLORS[0]).encode(
        x=x_time(), y=alt.Y("kp_lo:Q", scale=alt.Scale(domain=[0, 9])), y2="kp_hi:Q")
    pred = alt.Chart(long[long["col"] == "kp_pred"]).mark_line(strokeWidth=2).encode(x=x_time(), y=y, color=colour)
    obs = alt.Chart(long[long["col"] != "kp_pred"]).mark_line(strokeWidth=2, interpolate="step-after").encode(
        x=x_time(), y=y, color=colour)
    storm = alt.Chart(pd.DataFrame({"kp": [config.STORM_THRESHOLD], "text": ["storm threshold (G1)"]}))
    storm_rule = storm.mark_rule(strokeDash=[4, 4], color=MUTED).encode(y="kp:Q")
    storm_text = storm.mark_text(align="left", dx=4, dy=-7, color=MUTED, fontSize=11).encode(
        y="kp:Q", text="text:N", x=alt.value(0))

    hover = alt.selection_point(nearest=True, on="pointerover", fields=["time"], empty=False, clear="pointerout")
    tips = [alt.Tooltip("label:N", title="Hour"), alt.Tooltip("kp_pred:Q", title="Tormenta", format=".1f"),
            alt.Tooltip("kp_lo:Q", title="80% low", format=".1f"), alt.Tooltip("kp_hi:Q", title="80% high", format=".1f")]
    tips += [alt.Tooltip(f"{c}:Q", title=cols[c].split(" ")[0], format=".2f") for c in present[1:]]
    rule = alt.Chart(df).mark_rule(color=MUTED, strokeWidth=1).encode(
        x=x_time(), opacity=alt.condition(hover, alt.value(0.8), alt.value(0)), tooltip=tips).add_params(hover)
    dots = alt.Chart(long).mark_point(filled=True, size=70, strokeWidth=2).encode(
        x=x_time(), y=y, color=colour, opacity=alt.condition(hover, alt.value(1), alt.value(0)))

    layers = [band, storm_rule, storm_text, pred, obs, dots, rule]
    if df["ahead"].any():
        ahead = pd.DataFrame({"start": [df.loc[df["ahead"], "time"].min()], "end": [df["time"].max()]})
        layers.insert(0, alt.Chart(ahead).mark_rect(color=MUTED, opacity=0.12).encode(
            x=alt.X("start:T", scale=alt.Scale(type="utc")), x2="end:T"))
    return alt.layer(*layers).properties(height=340)


def sparkline(hourly: pd.DataFrame, col: str, unit: str) -> alt.Chart:
    df = utc(hourly[[col]].dropna().tail(24))
    base = alt.Chart(df).encode(x=alt.X("time:T", scale=alt.Scale(type="utc"), axis=None),
                                y=alt.Y(f"{col}:Q", axis=None, scale=alt.Scale(zero=False)))
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["time"], empty=False, clear="pointerout")
    line = base.mark_line(strokeWidth=2, color=SERIES_COLORS[0])
    pts = base.mark_point(filled=True, size=60, color=SERIES_COLORS[0]).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("label:N", title="Hour"), alt.Tooltip(f"{col}:Q", title=unit, format=".1f")]
    ).add_params(hover)
    layers = [line, pts]
    if col == "bz_gsm":
        layers.insert(0, alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=MUTED, strokeDash=[3, 3]).encode(
            y=alt.Y("z:Q", axis=None)))
    return alt.layer(*layers).properties(height=56).configure_view(strokeWidth=0)


def sweep_chart(values: dict, label: str) -> alt.LayerChart:
    """What-if: Kp (+ 80% range) as one input varies, the others held at the entered values."""
    col, grid = SWEEPS[label]
    rows = []
    for v in grid:
        x = {**values, col: float(v)}
        x["b_scalar"] = max(x["b_scalar"], float(np.sqrt(x["bx"] ** 2 + x["by_gsm"] ** 2 + x["bz_gsm"] ** 2)))
        out = predict_steady(BUNDLE, x)
        rows.append({"x": float(v), "kp": out["kp_pred"], "lo": out["kp_lo"], "hi": out["kp_hi"]})
    df = pd.DataFrame(rows)
    xs = alt.X("x:Q", title=label, axis=alt.Axis(grid=False))
    ys = alt.Y("kp:Q", scale=alt.Scale(domain=[0, 9]), title="predicted Kp")
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["x"], empty=False, clear="pointerout")
    band = alt.Chart(df).mark_area(opacity=0.18, color=SERIES_COLORS[0]).encode(x=xs, y=alt.Y("lo:Q"), y2="hi:Q")
    line = alt.Chart(df).mark_line(strokeWidth=2, color=SERIES_COLORS[0]).encode(x=xs, y=ys)
    pts = alt.Chart(df).mark_point(filled=True, size=70, color=SERIES_COLORS[0]).encode(
        x=xs, y=ys, opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("x:Q", title=label, format=".1f"), alt.Tooltip("kp:Q", title="Kp", format=".1f"),
                 alt.Tooltip("lo:Q", title="80% low", format=".1f"), alt.Tooltip("hi:Q", title="80% high", format=".1f")]
    ).add_params(hover)
    you = alt.Chart(pd.DataFrame({"x": [values[col]], "t": ["your input"]}))
    you_rule = you.mark_rule(color=MUTED, strokeDash=[4, 4]).encode(x="x:Q")
    you_text = you.mark_text(align="left", dx=4, y=8, color=MUTED, fontSize=11).encode(x="x:Q", text="t:N")
    storm = alt.Chart(pd.DataFrame({"kp": [config.STORM_THRESHOLD]})).mark_rule(strokeDash=[2, 4], color=MUTED).encode(y="kp:Q")
    return alt.layer(band, storm, you_rule, you_text, line, pts).properties(height=300)


# ── 7-day forecast (v2) ──────────────────────────────────────────────────────
# One fixed categorical slot per entity (reference palette slots 1–6 in order, light / dark steps), so a series
# keeps its colour whatever else is shown. Observed values are neutral ink, not a series colour. New models take the
# next slot; at most 8 series (palette size), after that fold the baselines into one toggle.
FC_SERIES = {"histgb": "HistGB (machine learning)", "trailing27": "27-day average", "persistence": "Persistence",
             "recurrence27": "27-day recurrence", "climatology": "Climatology", "noaa": "NOAA 27-day outlook"}
FC_COLORS = {"light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"],
             "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]}[MODE]
FC_TRAINED = {"histgb"}
INK = {"light": "#3d3d3a", "dark": "#e0dfd9"}[MODE]
OBSERVED = "Observed (GFZ)"
FC_TARGETS = {"Daily Ap": ("ap", "Ap"), "Daily max Kp": ("kpmax", "max Kp")}
GFZ_FLAGS = {0: "nowcast", 1: "provisional", 2: "definitive"}
HISTORY_DAYS = 30


@st.cache_data(ttl=600)
def get_forecasts():
    """The daily job's files (src/issue.py): no network call, so this works in the browser Space too."""
    log = pd.read_csv(ROOT / "forecasts" / "log.csv", parse_dates=["issued_at", "origin", "target_date"])
    scores = pd.read_csv(ROOT / "forecasts" / "scores.csv", parse_dates=["issued_at", "origin", "target_date"])
    recent = pd.read_csv(ROOT / "forecasts" / "recent.csv", index_col="date", parse_dates=["date"])
    noaa = pd.read_csv(ROOT / "forecasts" / "noaa_live.csv", parse_dates=["issued", "origin", "target_date"])
    return log, scores, recent, noaa


def forecast_long(latest: pd.DataFrame, recent: pd.DataFrame, noaa: pd.DataFrame, col: str) -> pd.DataFrame:
    """Observed history + every model's forecast + NOAA's outlook for the same days, as (time, series, value)."""
    obs = recent[col].tail(HISTORY_DAYS).rename("value").rename_axis("time").reset_index().assign(series=OBSERVED)
    fc = latest.assign(series=latest["model"].map(FC_SERIES).fillna(latest["model"]))
    fc = fc.rename(columns={"target_date": "time", col: "value"})[["time", "series", "value"]]
    parts = [obs, fc]
    outlook = noaa[noaa["product"] == "27do"]
    if len(outlook):
        outlook = outlook[outlook["issued"] == outlook["issued"].max()]
        outlook = outlook[outlook["target_date"].isin(latest["target_date"])]
        parts.append(outlook.rename(columns={"target_date": "time", col: "value"})[["time", "value"]]
                     .assign(series=FC_SERIES["noaa"]))
    return pd.concat(parts, ignore_index=True).dropna(subset=["value"])


def forecast_chart(long: pd.DataFrame, origin: pd.Timestamp, col: str, unit: str) -> alt.LayerChart:
    """History in ink, forecasts in their own colours, issue day marked, crosshair tooltip with every value."""
    present = [s for s in [OBSERVED, *FC_SERIES.values()] if s in set(long["series"])]
    colours = [INK if s == OBSERVED else FC_COLORS[list(FC_SERIES.values()).index(s)] for s in present]
    df = long.assign(time=long["time"].dt.tz_localize("UTC"), label=long["time"].dt.strftime("%a %d %b"))
    colour = alt.Color("series:N", scale=alt.Scale(domain=present, range=colours),
                       legend=alt.Legend(orient="top", title=None, symbolStrokeWidth=3))
    top = 9 if col == "kpmax" else max(40.0, float(df["value"].max()) * 1.1)
    y = alt.Y("value:Q", scale=alt.Scale(domain=[0, top]), title=unit)
    x = alt.X("time:T", scale=alt.Scale(type="utc"), title=None,
              axis=alt.Axis(format="%d %b", labelAngle=0, grid=False, tickCount=8))
    lines = alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36, filled=True)).encode(
        x=x, y=y, color=colour, detail="series:N")

    start = origin + pd.Timedelta(hours=12)              # shade from the middle of the issue day onwards
    ahead = pd.DataFrame({"start": [start.tz_localize("UTC")], "end": [df["time"].max() + pd.Timedelta(hours=12)],
                          "text": ["forecast →"]})
    shade = alt.Chart(ahead).mark_rect(color=MUTED, opacity=0.10).encode(x="start:T", x2="end:T")
    shade_text = alt.Chart(ahead).mark_text(align="left", dx=6, y=10, color=MUTED, fontSize=11).encode(
        x="start:T", text="text:N")

    wide = df.pivot_table(index=["time", "label"], columns="series", values="value").reset_index()
    keys = {s: f"s{i}" for i, s in enumerate(present)}
    wide = wide.rename(columns=keys)
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["time"], empty=False, clear="pointerout")
    tips = [alt.Tooltip("label:N", title="Day")] + [
        alt.Tooltip(f"{k}:Q", title=s, format=".1f" if col == "kpmax" else ".0f") for s, k in keys.items()
        if k in wide]
    rule = alt.Chart(wide).mark_rule(color=MUTED, strokeWidth=1).encode(
        x="time:T", opacity=alt.condition(hover, alt.value(0.8), alt.value(0)), tooltip=tips).add_params(hover)
    dots = alt.Chart(df).mark_point(filled=True, size=80).encode(
        x=x, y=y, color=colour, opacity=alt.condition(hover, alt.value(1), alt.value(0)))

    layers = [shade, shade_text, lines, dots, rule]
    if col == "kpmax":
        storm = alt.Chart(pd.DataFrame({"v": [config.STORM_THRESHOLD], "text": ["storm threshold (G1)"]}))
        layers.insert(2, storm.mark_rule(strokeDash=[4, 4], color=MUTED).encode(y="v:Q"))
        layers.insert(3, storm.mark_text(align="left", dx=4, dy=-7, color=MUTED, fontSize=11).encode(
            y="v:Q", text="text:N", x=alt.value(0)))
    return alt.layer(*layers).properties(height=340)


# ── Data ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_bundle():
    # In the browser (Hugging Face static Space via stlite/Pyodide) the scikit-learn pickle cannot be loaded;
    # the same trees are read from the portable .npz instead (identical predictions, see src/portable.py)
    if IN_BROWSER:
        from src.portable import load_portable
        return load_portable(ROOT / "models" / "current_portable.npz")
    return load_bundle()


@st.cache_data(ttl=300, show_spinner="Fetching real-time data from NOAA SWPC…")
def get_live():
    pred, hourly = nowcast(get_bundle())
    live = pred
    comparisons = [(fetch_live.fetch_swpc_kp, "kp_swpc")]
    if not IN_BROWSER:                              # GFZ sends no CORS header, so browsers may not fetch it
        comparisons.insert(0, (fetch_live.fetch_gfz_nowcast, "kp_gfz"))
    for fetch, name in comparisons:
        try:
            live = scoring.attach_block_kp(live, fetch(), name)
        except NETWORK_ERRORS:
            pass                                    # comparison only; the nowcast still works
    return live, hourly, fetch_live.fetch_f107(), pd.Timestamp.now("UTC")


def apply_preset(name: str):
    for k, v in PRESETS[name].items():
        st.session_state[k] = float(v)


def fill_live():
    try:
        _, hourly, f107, _ = get_live()
        latest = hourly.dropna().iloc[-1]
        for c in config.SW_FEATURES:
            st.session_state[c] = float(round(latest[c], 2))
        st.session_state["f107"] = float(f107.dropna().iloc[-1])
    except LIVE_ERRORS:
        st.session_state["fill_error"] = True


BUNDLE = get_bundle()

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🧲 Tormenta")
st.caption("**7-day forecast** of geomagnetic activity (daily Ap and max Kp), scored against official GFZ data as it "
           "arrives, and a **live nowcast** of the Kp index (0–9) from the solar wind measured about an hour upstream "
           "of Earth. GFZ Kp since 1932, NASA OMNI and live NOAA SWPC data.")

forecast_tab, live_tab, manual_tab, about_tab = st.tabs(
    ["📅 7-day forecast", "🛰️ Live nowcast", "🧪 What-if explorer", "📊 About the nowcast model"])

with forecast_tab:
    try:
        log, scores, recent, noaa = get_forecasts()
    except (FileNotFoundError, pd.errors.EmptyDataError):
        log = None
    if log is None or not len(log):
        st.info("No forecast has been issued yet. The daily job runs at 02:00 UTC.", icon="📅")
    else:
        origin = log["origin"].max()
        latest = log[log["origin"] == origin]
        issued, flag = latest["issued_at"].max(), int(latest["origin_flag"].iloc[0])
        days = latest["target_date"]
        st.markdown(f"**Forecast for {days.min():%a %d %b} – {days.max():%a %d %b %Y}**, issued "
                    f"{issued:%d %b %H:%M} UTC from GFZ data up to {origin:%d %b} ({GFZ_FLAGS.get(flag, flag)} values).")
        choice = st.radio("Quantity", list(FC_TARGETS), horizontal=True, label_visibility="collapsed")
        col, unit = FC_TARGETS[choice]
        st.altair_chart(forecast_chart(forecast_long(latest, recent, noaa, col), origin, col, unit), width="stretch")
        st.caption("**Ap** is the day's average geomagnetic activity (0–400; above about 30 is a storm day). **Max Kp** "
                   "is the day's strongest 3-hour Kp; 5− or more is a storm. Hover for every value. "
                   + ("**HistGB** is the machine-learning forecast; the others are simple reference methods it must "
                      "beat. " if FC_TRAINED & set(latest["model"]) else
                      "This issue comes from simple reference methods only; the machine-learning forecast (HistGB) "
                      "joins from the next daily issue. ")
                   + "More models (ARIMA family, a pretrained transformer) are added over the next days. NOAA's "
                   "outlook is shown for comparison only.")
        with st.expander("Forecast table"):
            table = latest.assign(model=latest["model"].map(FC_SERIES)).pivot_table(
                index="target_date", columns="model", values=col)
            table.index = table.index.strftime("%a %d %b")
            st.dataframe(table.round(2 if col == "kpmax" else 1), width="stretch")

        st.subheader("How past forecasts did")
        done = scores.dropna(subset=[f"{col}_obs"]) if len(scores) else scores
        if not len(done):
            st.info(f"Scoring starts when GFZ publishes {log['target_date'].min():%d %b}: each forecast is checked "
                    "against the real value once its day has passed, so a full week of lead days takes 7 days.",
                    icon="⏳")
        else:
            mae = done.assign(model=done["model"].map(FC_SERIES), err=done[f"{col}_err"].abs()).pivot_table(
                index="model", columns="lead", values="err", aggfunc="mean")
            mae.columns = [f"day {c}" for c in mae.columns]
            st.dataframe(mae.round(2), width="stretch")
            n_issues = done["origin"].nunique()
            st.caption(f"Mean absolute error of {unit} by lead day (lower is better), over {len(done)} checked "
                       f"forecasts from {n_issues} issue day{'s' if n_issues > 1 else ''}. Recent observed values are "
                       "GFZ's provisional ones and are rescored when the definitive values arrive.")

with live_tab:
    try:
        live, hourly, f107, fetched = get_live()
    except LIVE_ERRORS as exc:
        st.error(f"Could not get live data from NOAA SWPC ({type(exc).__name__}). Try again in a minute.", icon="📡")
        live = None
    if live is not None and len(live):
        past, ahead = live[~live["ahead"]], live[live["ahead"]]
        now = past.iloc[-1]
        if now["kp_pred"] >= config.STORM_THRESHOLD:
            _, _, short, name, _, icon, meaning = level_of(now["kp_pred"])
            st.error(f"**Geomagnetic storm in progress: {short} ({name}).** {meaning}", icon=icon)

        left, right = st.columns([3, 2], gap="large")
        with left:
            kp_card(now["kp_pred"], now["kp_lo"], now["kp_hi"], f"Kp now · {past.index[-1]:%d %b %H:00} UTC")
            if len(ahead):
                a = ahead.iloc[-1]
                st.caption(f"⏩ **Next hour ({ahead.index[-1]:%H:00} UTC): Kp {a['kp_pred']:.1f}** "
                           f"({a['kp_lo']:.1f}–{a['kp_hi']:.1f}). The solar wind for it has already passed the L1 "
                           "spacecraft and is on its way to Earth.")
        with right:
            latest = hourly.dropna().iloc[-1]
            st.markdown("**Solar wind now** · last 24 h")
            for col, label, unit, fmt in [("bz_gsm", "Bz (north–south field)", "nT", "{:+.1f}"),
                                          ("speed", "Speed", "km/s", "{:.0f}"), ("density", "Density", "cm⁻³", "{:.1f}")]:
                a, b = st.columns([2, 3])
                a.metric(label, f"{fmt.format(latest[col])} {unit}")
                b.altair_chart(sparkline(hourly, col, unit), width="stretch")
            f107_day = f107.dropna().index[-1]
            f107_age = (past.index[-1].normalize() - f107_day).days
            st.caption(f"|B| {latest['b_scalar']:.1f} nT · temperature {latest['temperature']:,.0f} K · "
                       f"F10.7 {f107.dropna().iloc[-1]:.0f} sfu ({f107_day:%d %b}). "
                       "**Negative Bz and high speed drive storms.**")
            if f107_age > config.F107_MAX_STALE_DAYS:
                st.warning(f"Solar flux (F10.7) data is {f107_age} days old, so the model runs without it "
                           "(slightly less accurate).", icon="☀️")

        st.subheader("Last 5 days: nowcast vs observed Kp")
        st.altair_chart(live_chart(live), width="stretch")
        notes = ["Hover for values. Shaded blue: 80% range."]
        ref, ref_name = ("kp_gfz", "GFZ") if "kp_gfz" in past else ("kp_swpc", "NOAA's estimate")
        if ref in past:
            scored = past.dropna(subset=[ref])
            if len(scored):
                m = scoring.metrics(scored[ref], scored["kp_pred"])
                cover = ((scored[ref] >= scored["kp_lo"]) & (scored[ref] <= scored["kp_hi"])).mean()
                notes.append(f"Vs {ref_name} over these {len(scored)} hours: RMSE **{m['rmse']:.2f}**, 80% range "
                             f"covered **{cover:.0%}** (test-set RMSE 0.57).")
        notes.append(f"Data fetched {fetched:%H:%M} UTC; refreshed every 5 minutes.")
        st.caption(" ".join(notes))
        c1, c2 = st.columns([1, 5])
        if c1.button("🔄 Refresh now"):
            get_live.clear()
            st.rerun()
        with c2.expander("Hourly table"):
            table = live.tail(48).iloc[::-1].copy()
            table["level"] = table["kp_pred"].map(lambda k: f"{level_of(k)[5]} {level_of(k)[2]}")
            st.dataframe(table.round(2), width="stretch")

with manual_tab:
    st.markdown("Pick a scenario or type your own conditions. One set of values is **assumed to have held steady "
                "for the past 3 days**, because the model also uses lags and 6–24 h averages.")
    for name, value in DEFAULTS.items():
        st.session_state.setdefault(name, value)
    cols = st.columns(len(PRESETS) + 1)
    for c, name in zip(cols, PRESETS):
        c.button(name, on_click=apply_preset, args=(name,), width="stretch")
    cols[-1].button("🛰️ Latest live values", on_click=fill_live, width="stretch")
    if st.session_state.pop("fill_error", False):
        st.error("Live data unavailable right now.", icon="📡")

    with st.form("manual"):
        fcols = st.columns(4)
        raw = {name: fcols[i % 4].number_input(label, min_value=lo, max_value=hi, step=STEPS.get(name, 0.5), key=name)
               for i, (name, (lo, hi, label)) in enumerate(INPUT_LIMITS.items())}
        submitted = st.form_submit_button("Predict Kp", type="primary")
    if submitted:
        values, errors = validate_inputs(raw)
        st.session_state["manual_values"] = None if errors else values
        for msg in errors.values():
            st.error(msg)
    values = st.session_state.get("manual_values")
    if values:
        out = predict_steady(BUNDLE, values)
        left, right = st.columns([2, 3], gap="large")
        with left:
            kp_card(out["kp_pred"], out["kp_lo"], out["kp_hi"], "Predicted Kp for your inputs")
        with right:
            label = st.radio("How does Kp respond to…", list(SWEEPS), horizontal=True)
            st.altair_chart(sweep_chart(values, label), width="stretch")
            st.caption("Each point is a full model prediction with that one input changed and the others held at "
                       "your values. Hover for the 80% range. Dashed line: storm threshold.")

with about_tab:
    a, b, c, d = st.columns(4)
    a.metric("Test RMSE", "0.573 Kp", "−34% vs persistence", delta_color="inverse")
    b.metric("R²", "0.808")
    c.metric("Storm-hour RMSE", "0.846 Kp", "−38% vs persistence", delta_color="inverse")
    d.metric("80% range coverage", "80.8%")
    st.caption("Test years 2020 → Jan 2026 (52,848 hours), never used for training or model selection.")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Model comparison (test RMSE, lower is better)**")
        table = pd.read_csv(ROOT / "reports" / "metrics" / "test.csv", index_col=0)
        table = table.drop(index=[i for i in table.index if i.startswith("Ensemble")], errors="ignore")
        table = table.assign(model=table.index.str.replace(" (baseline)", "", regex=False),
                             role=np.where(table.index == "HistGB", "production model", "comparison"))
        bars = alt.Chart(table).mark_bar(cornerRadiusEnd=4, height=18).encode(
            x=alt.X("rmse:Q", title="RMSE (Kp units)", scale=alt.Scale(domain=[0, 0.95])),
            y=alt.Y("model:N", sort="-x", title=None),
            color=alt.Color("role:N", scale=alt.Scale(domain=["production model", "comparison"],
                                                      range=[SERIES_COLORS[0], MUTED]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("model:N", title="Model"), alt.Tooltip("rmse:Q", title="RMSE", format=".3f"),
                     alt.Tooltip("storm_rmse:Q", title="Storm RMSE", format=".3f"),
                     alt.Tooltip("r2:Q", title="R²", format=".3f")])
        labels = bars.mark_text(align="left", dx=4, fontSize=11).encode(
            text=alt.Text("rmse:Q", format=".3f"), color=alt.value(MUTED))
        st.altair_chart(alt.layer(bars, labels).properties(height=230), width="stretch")
    with right:
        st.markdown("**The May 2024 superstorm (never seen in training)**")
        st.image(str(ROOT / "reports" / "figures" / "14_may2024_nowcast.png"))

    st.markdown(f"""
**How it works.** 8 inputs (IMF |B|, Bx, By, Bz in GSM; solar-wind speed, density, temperature; F10.7 solar flux)
become 66 causal features: coupling functions, pressure, lags, 3–24 h trends, position in the 3-hour Kp block, and
time of day and year. A HistGradientBoosting model predicts Kp; two quantile models plus a conformal correction give
the 80% range. **No geomagnetic indices are used as inputs.**

**Model** `{BUNDLE['version']}`, trained on definitive data up to {BUNDLE['trained_until'][:10]} and retrained
weekly by GitHub Actions behind a validation gate.

**Limitations.** The largest storms are under-predicted (about −0.6 Kp for G3+), and sudden onsets show up 1–2 h
late within a 3-hour block. This is not an operational warning service; for that, use NOAA SWPC or GFZ.

**Data.** NASA/GSFC OMNIWeb · GFZ Potsdam Kp (CC BY 4.0) · NOAA SWPC real-time data.
[Code](https://github.com/Syeda-Aliza-Ayaz/Tormenta) ·
[Model card](https://huggingface.co/aliza-ayaz/tormenta) · CT-378, NED University · Alizeh & HRK
""")
