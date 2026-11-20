"""Scorecard, Nowcast and Method pages."""
import re

import pandas as pd
import streamlit as st

from src import config, scoring
from src.predict import (INPUT_LIMITS, edited_fields, live_form_values, now_hour, predict_on_history, predict_steady,
                         validate_inputs)

from . import ui
from .charts import live_chart, monitor_chart, nowcast_models_chart, rmse_by_lead, show_chart, sweep_chart
from .data import (DEFAULTS, FC_SERIES, HISTORY_OPTIONS, LIVE_ERRORS, PRESETS, ROOT, SC_FIGURES, SC_KIND, SC_PERIODS,
                   SC_STATUS, STEPS, SWEEPS, get_bundle, get_live, get_monitor_state, get_nowcast_test, level_of,
                   read_report, report_path, scene_level, storm_table_for, try_live)
from .theme import TOKENS


# ── Scorecard ────────────────────────────────────────────────────────────────
def _status_chip(model: str, t: dict) -> str:
    kind = SC_STATUS.get(model, "ref")
    if kind == "live":
        return ui.chip("LIVE · HEADLINE", t["primary"], t["primary_fg"])
    label, color = {"live2": ("LIVE", t["text"]), "bench": ("BENCHMARK", t["series"]["noaa"]),
                    "off": ("NOT ISSUED", t["muted"]), "ref": ("REFERENCE", t["muted"])}[kind]
    return ui.chip(label, "transparent", color, t["hair"] if kind != "bench" else t["series"]["noaa"])


def scorecard(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    test = read_report("metrics", "test_leads.csv")
    ap_test = test[test["target"] == "ap"].set_index(["model", "lead"])["rmse"] if len(test) else pd.Series(dtype=float)
    h1, n1 = ap_test.get(("histgb", 1)), ap_test.get(("noaa", 1))
    ui.show(ui.hero("Scorecard", theme, f"{now:%H:%M:%S}", "dust", "quiet", "SCORECARD", "How good is the forecast?",
                    "Every model forecast 2,379 days it had never seen (1 January 2020 to 30 June 2026), checked against GFZ's "
                    "final values and NOAA's official forecasts. The test was run once, after every choice had been made.",
                    f"{h1:.2f}" if h1 else "—", f"Day-1 Ap error · NOAA {n1:.2f}" if n1 else ""))

    label = st.radio("Period", list(SC_PERIODS), horizontal=True, key="sc_period", label_visibility="collapsed")
    period = SC_PERIODS[label]
    leads = read_report("metrics", f"{period}_leads.csv")
    warn = read_report("metrics", f"{period}_storm_warning.csv")
    cov = read_report("metrics", f"{period}_interval_coverage.csv")
    if len(leads):
        ap = leads[leads["target"] == "ap"]
        hist = ap[ap["model"] == "histgb"].set_index("lead")
        noaa = ap[ap["model"] == "noaa"].set_index("lead")
        cells = []
        if 1 in hist.index:
            cells.append((f"{hist.loc[1, 'rmse']:.2f}", f" vs {noaa.loc[1, 'rmse']:.2f}" if 1 in noaa.index else "",
                          "Day-1 Ap error vs NOAA", "Root-mean-square error one day ahead; NOAA's official forecast on the same days."))
        cells.append((f"{hist['skill_vs_trailing27'].mean():+.3f}", "", "Skill over 7 days",
                       "Share of the 27-day average's squared error removed, averaged over lead days 1 to 7."))
        if len(cov):
            c = cov[(cov["model"] == "histgb") & (cov["target"] == "ap")]["coverage"]
            if len(c):
                cells.append((f"{c.min():.0%}–{c.max():.0%}", "", "Honest ranges", "Share of days whose real Ap fell inside the 80% range."))
        if len(warn):
            w1 = warn[warn["lead"] == 1].iloc[0]
            cells.append((f"{w1['pod']:.0%}", "", "Storm days warned, day 1",
                          f"{int(w1['hits'])} of {int(w1['hits'] + w1['misses'])} storm days caught one day ahead."))
        ui.show(f'<div class="tm-split" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1px;background:{t["hair"]};'
                f'border:1px solid {t["hair"]};border-radius:6px;overflow:hidden">'
                + "".join(f'<div class="tm-cell" style="background:{t["card"]};padding:22px 24px;display:flex;flex-direction:column;gap:8px">'
                          f'<span class="tm-mono" style="font-size:30px;font-weight:600">{v}<span style="font-size:15px;font-weight:400;color:{t["muted"]}">{s}</span></span>'
                          f'<span style="font-size:14px;font-weight:500">{lab}</span><span class="tm-sub">{note}</span></div>' for v, s, lab, note in cells)
                + "</div>")

    left, right = st.columns(2, gap="small")
    with left:
        with ui.card("pages_models_1"):
            ui.show(ui.section_head("Error by lead day", "Daily Ap, root-mean-square error. Lower is better."))
            if len(leads):
                show_chart(rmse_by_lead(leads, theme), theme)
    with right:
        with ui.card("pages_models_2"):
            n_storm = int(warn["hits"].iloc[0] + warn["misses"].iloc[0]) if len(warn) else 0
            ui.show(ui.section_head("Storm warnings", f"{n_storm} storm days. Bar = share caught; then caught, false alarms, Heidke skill (0 = chance)."))
            if len(warn):
                rows = ""
                for r in warn.sort_values("lead").itertuples():
                    rows += (f'<div style="display:grid;grid-template-columns:54px minmax(0,1fr) 200px;gap:14px;align-items:center;font-size:13px">'
                             f'<span style="color:{t["muted"]}">Day {r.lead}</span><span style="position:relative;height:22px;background:{t["track"]};border-radius:3px">'
                             f'<span style="position:absolute;left:0;top:0;bottom:0;width:{r.pod:.1%};background:{t["primary"]};border-radius:3px"></span>'
                             f'<span class="tm-mono" style="position:absolute;left:8px;top:3px;font-size:12px;font-weight:600;color:{t["primary_fg"]}">{r.pod:.0%}</span></span>'
                             f'<span class="tm-mono" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));font-size:12px;text-align:right">'
                             f'<span>{r.hits}</span><span style="color:{t["muted"]}">{r.false_alarms}</span><span style="font-weight:600">{r.hss:.2f}</span></span></div>')
                ui.show(f'<div style="display:flex;flex-direction:column;gap:10px">{rows}'
                        f'<div class="tm-mono" style="display:grid;grid-template-columns:54px minmax(0,1fr) 200px;gap:14px;font-size:11px;color:{t["muted"]}">'
                        f'<span></span><span></span><span style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));text-align:right">'
                        f'<span>caught</span><span>false al.</span><span>Heidke</span></span></div></div>')

    from .data import comparison_rows
    rows, styles = [], []
    for r in comparison_rows(period):
        m = r["model"]
        fmt = lambda v: "—" if v is None or pd.isna(v) else f"{v:.2f}"  # noqa: E731
        skill = f"{r['skill']:+.3f}" + ("*" if m == "noaa" else "")
        rows.append([f'<strong>{FC_SERIES.get(m, m)}</strong><span style="display:block;font-size:12px;color:{t["muted"]}">{SC_KIND.get(m, "")}</span>',
                     _status_chip(m, t), fmt(r["d1"]), fmt(r["d3"]), fmt(r["d7"]),
                     f'<strong style="color:{t["alert_text"] if r["skill"] < 0 else t["text"]}">{skill}</strong>'])
        styles.append(f"background:{t['highlight']}" if m == "histgb" else "")
    if rows:
        ui.show(ui.table(["Model", "Status", "Ap error, day 1", "Day 3", "Day 7", "Skill vs 27-day average"], rows, {2, 3, 4, 5},
                         caption="Every model, same days", min_width=820, row_styles=styles,
                         note="*NOAA publishes Ap for days 1–3 only, so its skill covers those days. Skill = share of the 27-day "
                              "average's squared error removed. Models marked not issued failed the validation rule set in advance."))

    with ui.card("pages_models_3"):
        ui.show(ui.section_head("Storm days: who caught them?", "Storm day = max Kp ≥ 5−. Pick a lead day."))
        lead = st.radio("Lead day", [f"Day {i}" for i in config.FORECAST_LEADS], horizontal=True, key="sc_lead",
                        label_visibility="collapsed")
        st_tab = storm_table_for(period, int(lead.split()[1]))
        if len(st_tab):
            names = {**FC_SERIES, "storm_warning": "Storm warning (classifier)"}
            ui.show(ui.table(["Model", "Caught", "Missed", "False alarm", "Correct quiet", "Detection", "False-alarm ratio", "Heidke"],
                             [[names.get(r.model, r.model), r.hits, r.misses, r.false_alarms, r.correct_negatives,
                               f"{r.pod:.0%}", "—" if pd.isna(r.far) else f"{r.far:.0%}", f"{r.hss:.2f}"] for r in st_tab.itertuples()],
                             set(range(1, 8)), min_width=760))

    with st.expander("Report figures"):
        tabs = st.tabs(list(SC_FIGURES))
        for tab, name in zip(tabs, SC_FIGURES.values()):
            path = report_path("figures", name)
            if path.exists():
                tab.image(str(path))

    with ui.card("pages_models_4"):
        ui.show(ui.section_head("Model health · retrain only when performance drops",
                                "Weekly check of HistGB's 56-day skill against the 27-day average."))
        state = get_monitor_state()
        last = state["checks"][-1] if state.get("checks") else None
        if last:
            status = {"healthy": ("HEALTHY", t["live"]), "degraded": ("DEGRADED", t["alert"]),
                      "insufficient_data": ("NOT ENOUGH LIVE DATA YET", t["muted"])}[last["status"]]
            ui.show(f'<p style="margin:0;font-size:14px">Latest check ({last["checked_on"]}): {ui.chip(status[0], "transparent", status[1], status[1])} '
                    f'· {last["pairs"]} scored forecasts · skill {"—" if last["skill"] is None else format(last["skill"], "+.2f")} '
                    f'(degraded below {last["floor"]:.2f}) · retrains so far: {len(state["retrains"])}.</p>')
        windows = read_report("metrics", "monitor_test_windows.csv")
        if len(windows):
            show_chart(monitor_chart(windows, float(windows["skill"].quantile(0.05)), theme), theme)
            st.caption("What the monitor would have seen on the test period. A retrain is due only after two weekly checks in a "
                       "row below the line, and the new model must also beat the current one on the newest 6 months.")
    ui.show(ui.credits(t, theme))


# ── Nowcast ──────────────────────────────────────────────────────────────────
def _apply_preset(name: str):
    for k, v in PRESETS[name].items():
        st.session_state[k] = float(v)
    st.session_state["history_mode"] = HISTORY_OPTIONS[1]


def _fill_live():
    try:
        live, hourly, f107, _ = get_live()
        hour = now_hour(live)
        shown = live_form_values(hourly, f107, hour)
        for k, v in shown.items():
            st.session_state[k] = float(round(v, 2))
        st.session_state["live_shown"] = shown
        st.session_state["live_shown_hour"] = hour
        # predict at once with the filled values, so no older "Predict Kp" values linger
        st.session_state["manual_values"] = {k: float(round(v, 2)) for k, v in shown.items()}
        st.session_state["history_mode"] = HISTORY_OPTIONS[0]
    except LIVE_ERRORS:
        st.session_state["fill_error"] = True


def _follow_live_hour():
    """If the form holds untouched "latest live values" from an hour that has since passed, refill it for the
    current hour, so an unedited form always matches the live Kp (runs before the form's widgets are drawn)."""
    filled_hour = st.session_state.get("live_shown_hour")
    if filled_hour is None:
        return
    try:
        live, _, _, _ = get_live()
    except LIVE_ERRORS:
        return
    shown = st.session_state.get("live_shown") or {}
    untouched = st.session_state.get("manual_values") == {k: float(round(v, 2)) for k, v in shown.items()}
    if now_hour(live) != filled_hour and untouched:
        _fill_live()


def nowcast_page(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    slot = st.empty()
    lead = ("Estimated every hour from the solar wind measured by spacecraft 1.5 million km upstream, before GFZ "
            "publishes the official value.")
    ui.show(ui.hero("Nowcast", theme, f"{now:%H:%M:%S}", "earthphoto", "quiet", "NOWCAST", "Kp right now", lead, "…",
                    "fetching live solar wind"), slot)
    bundle = get_bundle()
    live = try_live()
    kp_now, label = None, "Live data unavailable"
    if live is not None:
        live_df, hourly, f107, fetched = live
        past, ahead = live_df[~live_df["ahead"]], live_df[live_df["ahead"]]
        cur = past.iloc[-1]
        kp_now = float(cur["kp_pred"])
        label = f"{ui.pk(past.index[-1]):%d %b %H:00} PKT · {level_of(kp_now)[3].lower()}"
    ui.show(ui.hero("Nowcast", theme, f"{now:%H:%M:%S}", "earthphoto", scene_level(kp_now or 0), "NOWCAST", "Kp right now",
                    lead, f"Kp {kp_now:.1f}" if kp_now is not None else "—", label,
                    kp_now is not None and kp_now >= config.STORM_THRESHOLD), slot)

    if live is None:
        st.error("Could not reach NOAA SWPC for live solar-wind data. Try again in a minute.")
    else:
        lv = level_of(kp_now)
        if kp_now >= config.STORM_THRESHOLD:
            ui.show(ui.banner(f"Geomagnetic storm in progress · {lv[2]} ({lv[3]})", lv[5], t))
        nxt = ""
        if len(ahead):
            a = ahead.iloc[-1]
            nw = hourly.loc[:ahead.index[-1]].ffill().iloc[-1]
            nxt = (f'<span class="tm-sub">Next hour ({ui.pk(ahead.index[-1]):%H:00} PKT): Kp {a["kp_pred"]:.1f} '
                   f'({a["kp_lo"]:.1f}–{a["kp_hi"]:.1f}), from wind at {nw["speed"]:.0f} km/s with Bz {nw["bz_gsm"]:+.1f} nT '
                   f'that has already passed the spacecraft.</span>')
        readout = (f'<div class="tm-flat" style="padding:26px 28px;display:flex;flex-direction:column;justify-content:space-between;gap:20px;height:100%;box-sizing:border-box">'
                   f'<div style="display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap"><span class="tm-mono" style="font-size:88px;line-height:.9;font-weight:600;letter-spacing:-0.03em">{kp_now:.1f}</span>'
                   f'<span style="display:flex;flex-direction:column;gap:6px;padding-bottom:6px">{ui.level_chip(kp_now, t)}'
                   f'<span class="tm-sub" style="font-size:14px">Kp at {ui.pk(past.index[-1]):%H:00} PKT · 80% range {cur["kp_lo"]:.1f} – {cur["kp_hi"]:.1f}</span></span></div>'
                   f'{ui.kp_scale(kp_now, cur["kp_lo"], cur["kp_hi"], t)}<span style="font-size:14px;line-height:1.5">{ui.esc(lv[5])}</span>{nxt}</div>')
        upto = hourly.loc[:past.index[-1]]                  # the "Kp now" hour, like the headline and the form
        w = upto.ffill().iloc[-1]
        h24 = upto.dropna().tail(24)
        cells = [("Bz · north–south field", f"{w['bz_gsm']:+.1f}", "nT", "Southward (negative) lets energy in.", "bz_gsm"),
                 ("Wind speed", f"{w['speed']:.0f}", "km/s", "Fast streams run 500–800 km/s.", "speed"),
                 ("Density", f"{w['density']:.1f}", "cm⁻³", "CME sheaths reach 20–40.", "density"),
                 ("Field strength |B|", f"{w['b_scalar']:.1f}", "nT", "Storms usually need 15 nT or more.", "b_scalar")]
        wind_html = "".join(
            f'<div class="tm-cell" style="background:{t["card"]};padding:18px 20px;display:flex;flex-direction:column;gap:6px">'
            f'<span class="tm-sub">{lab}</span><span class="tm-mono" style="font-size:26px;font-weight:600">{v} <span style="font-size:13px;font-weight:400;color:{t["muted"]}">{u}</span></span>'
            f'{ui.sparkline(list(h24[col]), 240, 64, t["primary"], labels=("24 h ago", "now"))}<span class="tm-sub" style="font-size:12px">{note}</span></div>'
            for lab, v, u, note, col in cells)
        acc = ""
        ref, ref_name = ("kp_gfz", "GFZ quick-look") if "kp_gfz" in past else ("kp_swpc", "NOAA's estimate")
        if ref in past:
            scored = past.dropna(subset=[ref])
            if len(scored):
                m = scoring.metrics(scored[ref], scored["kp_pred"])
                cover = ((scored[ref] >= scored["kp_lo"]) & (scored[ref] <= scored["kp_hi"])).mean()
                bias = float((scored["kp_pred"] - scored[ref]).mean())
                stats = [(f"{m['mae']:.2f}", "mean error, Kp"), (f"{m['rmse']:.2f}", "RMSE"), (f"{cover:.0%}", "inside 80% range"),
                         (f"{bias:+.2f}", "bias")]
                acc = (f'<div class="tm-flat" style="padding:20px 22px;display:flex;flex-direction:column;gap:12px">'
                       f'<span style="font-size:15px;font-weight:600">Live accuracy · last {len(scored)} hours vs {ref_name}</span>'
                       f'<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px">'
                       + "".join(f'<span style="display:flex;flex-direction:column;gap:4px"><span class="tm-mono" style="font-size:20px;font-weight:600">{v}</span>'
                                 f'<span class="tm-sub" style="font-size:12px">{lab}</span></span>' for v, lab in stats)
                       + f'</div><span class="tm-sub" style="font-size:12px">Test period 2020 onwards (cleaned OMNI data): RMSE 0.57 Kp, 81% of the variation explained.</span></div>')
        right = (f'<div class="tm-split" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;height:100%;'
                 f'background:{t["hair"]};border:1px solid {t["hair"]};border-radius:6px;overflow:hidden">{wind_html}</div>')
        ui.show(ui.grid([readout, right], 380, align="stretch"))      # both cards end at the same height
        if acc:
            ui.show(acc)                                                # full width, under both cards

        with ui.card("pages_models_5"):
            ui.show(ui.section_head("Last 5 days · nowcast vs observed Kp",
                                    f"Shaded: 80% range. Data fetched {ui.pk(fetched):%H:%M} PKT; refreshed every 5 minutes."))
            show_chart(live_chart(live_df, theme), theme)
            c1, c2 = st.columns([1, 5])
            if c1.button("Refresh now"):
                get_live.clear()
                st.rerun()
            with c2.expander("Hourly table"):
                tab = live_df.tail(24).iloc[::-1]
                ui.show(ui.table(["Hour (PKT)", "Kp", "80% low", "80% high", "Level"],
                                 [[f"{ui.pk(i):%d %b %H:00}", f"{r.kp_pred:.2f}", f"{r.kp_lo:.2f}", f"{r.kp_hi:.2f}", level_of(r.kp_pred)[3]]
                                  for i, r in zip(tab.index, tab.itertuples())], {1, 2, 3}))

    ui.show(ui.section_head("What if the solar wind changed?",
                            "Pick a scenario or type your own conditions for the current hour. The model also uses the past "
                            "3 days, so choose what that past looks like."))
    for name, value in DEFAULTS.items():
        st.session_state.setdefault(name, value)
    _follow_live_hour()
    cols = st.columns(len(PRESETS) + 1)
    for c, name in zip(cols, PRESETS):
        c.button(name, on_click=_apply_preset, args=(name,), width="stretch")
    cols[-1].button("Latest live values", on_click=_fill_live, width="stretch", type="primary")
    if st.session_state.pop("fill_error", False):
        st.error("Live data unavailable right now.")
    with st.form("manual"):
        fcols = st.columns(4)
        raw = {name: fcols[i % 4].number_input(lab, min_value=lo, max_value=hi, step=STEPS.get(name, 0.5), key=name)
               for i, (name, (lo, hi, lab)) in enumerate(INPUT_LIMITS.items())}
        submitted = st.form_submit_button("Predict Kp")
    if submitted:
        values, errors = validate_inputs(raw)
        st.session_state["manual_values"] = None if errors else values
        for msg in errors.values():
            st.error(msg)
    values = st.session_state.get("manual_values")
    if values:
        st.session_state.setdefault("history_mode", HISTORY_OPTIONS[1])
        mode = st.radio("Past 3 days", HISTORY_OPTIONS, horizontal=True, key="history_mode")
        live_h = None
        if mode == HISTORY_OPTIONS[0]:
            try:
                live_h, hourly_h, f107_h, _ = get_live()
            except LIVE_ERRORS:
                st.warning("Live data is unavailable right now, so the past 3 days are assumed steady.")
        if live_h is not None:
            hour = now_hour(live_h)
            shown = st.session_state.get("live_shown") or live_form_values(hourly_h, f107_h, hour)

            def predict(x):
                return predict_on_history(bundle, hourly_h, f107_h, hour, edited_fields(x, shown))
            changed = edited_fields(values, shown)
            title = (f"Kp at {ui.pk(hour):%d %b %H:00} PKT, real history" if not changed else
                     f"Kp at {ui.pk(hour):%d %b %H:00} PKT with your {len(changed)} change{'s' if len(changed) > 1 else ''}")
        else:
            def predict(x):
                return predict_steady(bundle, x)
            title, changed = "Predicted Kp, conditions steady for 3 days", None
        out = predict(values)
        storm = out["kp_pred"] >= config.STORM_THRESHOLD
        left, right = st.columns([2, 3], gap="medium")
        with left:
            ui.show(f'<div class="tm-flat" style="padding:22px 24px;display:flex;flex-direction:column;gap:16px;{f"border-color:{t["alert"]};background:{t["alert_wash"]};" if storm else ""}">'
                    f'<span class="tm-sub">{ui.esc(title)}</span><div style="display:flex;align-items:center;gap:20px">'
                    f'<span class="tm-mono" style="font-size:56px;font-weight:600;line-height:1;color:{t["alert_text"] if storm else t["text"]}">{out["kp_pred"]:.1f}</span>'
                    f'<span style="display:flex;flex-direction:column;gap:6px">{ui.level_chip(out["kp_pred"], t)}'
                    f'<span class="tm-sub">80% range {out["kp_lo"]:.1f} – {out["kp_hi"]:.1f}</span></span></div>'
                    f'{ui.kp_scale(out["kp_pred"], out["kp_lo"], out["kp_hi"], t)}<span style="font-size:14px;line-height:1.5">{ui.esc(level_of(out["kp_pred"])[5])}</span></div>')
            if live_h is not None:
                st.caption("Unchanged live values: this equals the live nowcast for the same hour." if not changed else
                           "Changed: " + ", ".join(INPUT_LIMITS[k][2] for k in changed) + ". Everything before this hour is the real solar wind.")
        with right:
            with ui.card("pages_models_6"):
                lab = st.radio("How does Kp respond to…", list(SWEEPS), horizontal=True, key="sweep_label")
                show_chart(sweep_chart(values, lab, predict, theme), theme)
                st.caption("Each point is a full model prediction with that one input changed and the others held at your values.")
    ui.show(ui.credits(t, theme))


# ── Method ───────────────────────────────────────────────────────────────────
def _decision_count() -> str:
    path = ROOT / "DECISIONS.md"
    if not path.exists():
        return "64"
    return str(len(set(re.findall(r"^### D-(\d+)", path.read_text(encoding="utf-8"), flags=re.M))))


def method(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    n_dec = _decision_count()
    ui.show(ui.hero("Method", theme, f"{now:%H:%M:%S}", "bhphoto", "quiet", "METHOD", "How Tormenta works",
                    "Ninety years of official geomagnetic records, models chosen by rules written before the results were seen, "
                    "and a forecast issued every morning that can never be edited afterwards.", n_dec,
                    "decisions on record, each with its reason"))
    steps = [("01", "Official records", "GFZ Potsdam's daily Ap, max Kp and solar flux F10.7, 1932 to yesterday."),
             ("02", "29 features", "Last 7 days, activity levels, solar flux, values one to three solar rotations back, season."),
             ("03", "Models", "HistGB for values, a classifier for storm chance, ARIMAX for comparison."),
             ("04", "Daily issue", "A scheduled job forecasts the next 7 days each morning into an append-only log."),
             ("05", "Scoring", "Each day is scored when GFZ publishes it; a weekly check decides on retraining.")]
    ui.show(ui.section_head("From data to a forecast"))
    ui.show(ui.grid([f'<div class="tm-card" style="padding:18px;display:flex;flex-direction:column;gap:8px;height:100%;box-sizing:border-box">'
                     f'<span class="tm-mono" style="font-size:12px;color:{t["primary"]}">{n}</span><span style="font-size:15px;font-weight:600">{a}</span>'
                     f'<span class="tm-sub">{b}</span></div>' for n, a, b in steps], 200, 10))
    split = [("1947 – 2016", "Training", "Models learn here. Settings tuned with time-ordered folds and a 7-day gap.", t["hair"], t["hair"]),
             ("2017 – 2019", "Validation", "Every choice made here, by rules set in advance.", "#4A5A70" if theme == "dark" else "#B9C8DC", "transparent"),
             ("2020 – Jun 2026", "Test, scored once", "Never looked at until the end. 2,379 days, 325 storms.", t["primary"], t["primary"]),
             ("Jul 2026 →", "Live", "Models refitted on all data; judged by the live log.", t["surface"], t["primary"])]
    ui.show(f'<div class="tm-flat" style="padding:24px 26px;display:flex;flex-direction:column;gap:16px">'
            f'<div style="display:flex;justify-content:space-between;gap:8px"><h2 class="tm-h2">Which years do what</h2><span class="tm-sub" style="font-size:12px">Widths not to scale</span></div>'
            f'<div style="display:grid;grid-template-columns:58fr 10fr 20fr 12fr;gap:3px">'
            + "".join(f'<div style="display:flex;flex-direction:column;gap:10px;min-width:0"><span style="height:36px;border-radius:3px;background:{bg};border:1px solid {bd}"></span>'
                      f'<span class="tm-mono tm-sub" style="font-size:12px">{y}</span><span style="font-size:14px;font-weight:600">{n}</span><span class="tm-sub">{d}</span></div>'
                      for y, n, d, bg, bd in split) + "</div></div>")
    models = [("VALUES · LIVE HEADLINE", "HistGB", "Gradient-boosted trees, one model per lead day and quantity (14 in all), so an error on "
               "day 1 never feeds day 2. Level with NOAA's official forecast on day 1."),
              ("WARNINGS · LIVE", "Storm classifier", "Seven classifiers give the chance of a storm day. Storms are rare, so the warning "
               "line is set for rare events (23–31%), not 50%, and no data is resampled."),
              ("COMPARISON", "ARIMAX and reference forecasts", "A linear time-series model, plus the simple rules every model must beat: "
               "persistence, the 27-day average and climatology. ARIMA, SARIMA and a pretrained transformer were tested and not issued.")]
    ui.show(ui.grid([f'<article class="tm-card" style="padding:22px 24px;display:flex;flex-direction:column;gap:10px"><span class="tm-eyebrow">{r}</span>'
                     f'<h3 style="margin:0;font-size:18px;font-weight:600">{n}</h3><p class="tm-sub" style="margin:0;font-size:14px;line-height:1.6">{b}</p></article>'
                     for r, n, b in models], 320))
    checks = [("Beat the simple rules", "Skill is measured against tomorrow-equals-today, the 27-day average and climatology."),
              ("Compare with the professionals", "NOAA's official forecasts for the same days, from its archived reports."),
              ("Honest splits", "Train, validate, then a test scored once; a marker file blocks repeats."),
              ("No future data", "Automated tests cut the future off and confirm forecasts do not change."),
              ("More than one number", "Error, skill, storm catches and false alarms, probability quality and range coverage."),
              ("Live proof", "Forecasts are logged before their day happens and can never be edited.")]
    ui.show(ui.section_head("Six checks before a number is trusted"))
    ui.show(f'<div class="tm-split" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1px;background:{t["hair"]};border:1px solid {t["hair"]};border-radius:6px;overflow:hidden">'
            + "".join(f'<div class="tm-cell" style="background:{t["card"]};padding:20px 22px;display:grid;grid-template-columns:40px minmax(0,1fr);gap:4px 12px">'
                      f'<span class="tm-mono" style="grid-row:span 2;font-size:20px;font-weight:600;color:{t["primary"]}">{i:02d}</span>'
                      f'<span style="font-size:15px;font-weight:600">{a}</span><span class="tm-sub">{b}</span></div>' for i, (a, b) in enumerate(checks, 1))
            + "</div>")

    bundle = get_bundle()
    test = get_nowcast_test()
    ui.show(ui.section_head("The nowcaster", f"Model {bundle['version']} · trained on definitive data up to {bundle['trained_until'][:10]}."))
    if "HistGB" in test.index:
        h, p = test.loc["HistGB"], test.loc[[i for i in test.index if i.startswith("Persistence")][0]]
        stats = [(f"{h['rmse']:.3f}", "Test RMSE (Kp)", f"{1 - h['rmse'] / p['rmse']:.0%} below persistence"),
                 (f"{h['r2']:.3f}", "R²", "share of Kp's variation explained"),
                 (f"{h['storm_rmse']:.3f}", "Storm-hour RMSE", f"{1 - h['storm_rmse'] / p['storm_rmse']:.0%} below persistence"),
                 (f"{int(h['n']):,}", "Test hours", "2020 onwards, never used for training")]
        ui.show(ui.grid([ui.kpi(lab, v, note, t=t) for v, lab, note in stats], 220))
    left, right = st.columns(2, gap="small")
    with left:
        with ui.card("pages_models_7"):
            ui.show(ui.section_head("Model comparison", "Test RMSE, lower is better."))
            show_chart(nowcast_models_chart(test, theme), theme)
    with right:
        with ui.card("pages_models_8"):
            ui.show(ui.section_head("The May 2024 superstorm", "Never seen in training."))
            fig = ROOT / "reports" / "figures" / "14_may2024_nowcast.png"
            if fig.exists():
                st.image(str(fig))
    ui.show(
        f'<article class="tm-flat" style="padding:28px 32px;display:flex;flex-direction:column;gap:16px">'
        f'<h2 class="tm-h2" style="font-size:22px !important">Known limits</h2>'
        f'<ul style="margin:0;padding-left:22px;display:flex;flex-direction:column;gap:14px;font-size:17px;line-height:1.6;color:{t["text"]}">'
        '<li>Storms from sudden solar eruptions leave no trace in past Kp, so their onset is usually missed by the 7-day forecast.</li>'
        '<li>The nowcaster under-reads the largest storms (about −0.6 Kp for G3+) and sudden onsets show up 1–2 h late.</li>'
        '<li>Storm chances read somewhat high in quiet spells; warnings are unaffected. A correction was tested and rejected by its own rule.</li>'
        '<li>This is a course project, not an operational warning service; for that, use NOAA SWPC or GFZ.</li></ul></article>')
    ui.show(ui.credits(t, theme))
