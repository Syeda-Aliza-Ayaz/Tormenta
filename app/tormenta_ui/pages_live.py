"""Overview, Forecast and Explore pages."""
import pandas as pd
import streamlit as st

from src import config

from . import ui
from .charts import forecast_band, forecast_chart, forecast_long, show_chart
from .data import (CONTEXT_DAYS, EDIT_DAYS, FC_REFERENCE, FC_SERIES, FC_TARGETS, FC_TRAINED, GFZ_FLAGS, HISTORY_DAYS,
                   NO_NOAA, NOTABLE_DAYS, TRY_PRESETS, get_forecast_models, get_forecasts, get_past_forecasts,
                   get_storm_log, latest_issue, level_of, noaa_kp_for, read_report, run_forecasters, scene_level,
                   try_live)
from .theme import TOKENS

AURORA_REACH = {"Quiet": "Polar", "Unsettled": "Polar", "Active": "High lat.", "G1": "~60°", "G2": "~55°", "G3": "~50°",
                "G4+": "Mid-lat."}


def _warned(r) -> bool:
    w = r["warning"]
    return bool(w) if not isinstance(w, str) else w == "True"


def _test_headline():
    """(HistGB day-1 Ap RMSE, NOAA day-1 Ap RMSE, storm days caught on day 1 as a share) from the one-time test."""
    leads = read_report("metrics", "test_leads.csv")
    warn = read_report("metrics", "test_storm_warning.csv")
    if not len(leads):
        return None
    ap = leads[leads["target"] == "ap"].set_index(["model", "lead"])["rmse"]
    pod = float(warn[warn["lead"] == 1]["pod"].iloc[0]) if len(warn) else None
    return ap.get(("histgb", 1)), ap.get(("noaa", 1)), pod


def _day_label(d: pd.Timestamp, today: pd.Timestamp) -> str:
    return "Today" if d == today else f"{d:%A}"


# ── Overview ─────────────────────────────────────────────────────────────────
def overview(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    today = now.tz_localize(None).normalize()
    slot = st.empty()
    ui.show(ui.hero_overview(theme, f"{now:%H:%M:%S}", f"{now:%A} {now.day} {now:%b %Y}", "quiet", "…", "Fetching live data",
                             0.0, "Reading the latest solar wind from NOAA.", [], None, live_ok=False), slot)
    live = try_live()
    issue = latest_issue()
    storm_log = get_storm_log()

    kp_now, hourly, f107, past = None, None, None, None
    if live is not None:
        live_df, hourly, f107, _ = live
        past = live_df[~live_df["ahead"]]
        kp_now = float(past["kp_pred"].iloc[-1])

    days, warn_rows, noaa = [], pd.DataFrame(), None
    if issue is not None:
        origin, rows, _, _, noaa = issue
        hist = rows[rows["model"] == "histgb"].sort_values("target_date")
        if not len(hist):
            hist = rows[rows["model"] == "trailing27"].sort_values("target_date")
        upcoming = hist[hist["target_date"] >= today]
        days = list((upcoming if len(upcoming) else hist).itertuples())
        if len(storm_log):
            warn_rows = storm_log[storm_log["origin"] == origin].set_index("target_date")

    kp_show = kp_now if kp_now is not None else (days[0].kpmax if days else 0.0)
    lv = level_of(kp_show)
    today_stats, watch = [], None
    if days:
        d0 = days[0]
        today_stats = [("Today max", f"Kp {d0.kpmax:.1f}", "#F1F2F4")]
        if pd.notna(getattr(d0, "kpmax_lo", None)):
            today_stats.append(("Range", f"{d0.kpmax_lo:.1f} – {d0.kpmax_hi:.1f}", "#C9CED6"))
        if d0.target_date in warn_rows.index:
            r = warn_rows.loc[d0.target_date]
            today_stats.append(("Storm risk", f"{r['storm_prob']:.0%}", "#FF8A55" if _warned(r) else "#F1F2F4"))
        for d in days:
            if d.target_date in warn_rows.index and _warned(warn_rows.loc[d.target_date]):
                r = warn_rows.loc[d.target_date]
                label = "today" if d.target_date == today else f"{d.target_date:%a %d %b}"
                body = (f"{r['storm_prob']:.0%} chance of reaching Kp 5− {'today' if d.target_date == today else 'that day'}, "
                        f"above the {r['threshold']:.0%} warning line.")
                nk = noaa_kp_for(noaa, d.target_date) if noaa is not None else None
                if nk is not None and nk >= config.STORM_THRESHOLD:
                    body += f" NOAA's official forecast also reaches Kp {nk:.2f}."
                watch = (f"Storm watch · {label}", body)
                break
    line = lv[5] if kp_now is not None else "Live solar-wind data is unavailable right now; showing today's forecast."
    ui.show(ui.hero_overview(theme, f"{now:%H:%M:%S}", f"{now:%A} {now.day} {now:%b %Y}", scene_level(kp_show),
                             f"{kp_show:.1f}", lv[3] if not lv[2].startswith("G") else f"{lv[3]} · {lv[2]}", kp_show,
                             line, today_stats, watch, live_ok=kp_now is not None), slot)

    if days:
        rows_html = ""
        for d in days:
            r = warn_rows.loc[d.target_date] if d.target_date in warn_rows.index else None
            warn = r is not None and _warned(r)
            lo, hi = (d.kpmax_lo, d.kpmax_hi) if pd.notna(getattr(d, "kpmax_lo", None)) else (d.kpmax, d.kpmax)
            bar, dot = (t["alert"], t["alert"]) if warn else (t["primary"], t["primary"])
            risk = f"{r['storm_prob']:.0%}" if r is not None else "—"
            icon_color = t["muted"] if d.kpmax < 3 else t["primary"]
            rows_html += (
                f'<div class="tm-row" style="display:grid;grid-template-columns:130px 44px 92px minmax(0,1fr) 64px;align-items:center;gap:16px;padding:14px 22px;border-bottom:1px solid {t["grid"]}">'
                f'<span style="display:flex;flex-direction:column;gap:2px"><span style="font-size:15px;font-weight:600">{_day_label(d.target_date, today)}</span>'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:{t["muted"]}">{d.target_date.day} {d.target_date:%b}</span></span>'
                f'<span style="color:{icon_color}" title="{level_of(d.kpmax)[3]}">{ui.condition_icon(d.kpmax, 28)}</span>'
                f'<span style="display:flex;align-items:center;gap:6px;font-family:\'IBM Plex Mono\',monospace;font-size:13px;color:{t["alert_text"] if warn else t["muted"]}">{ui.icon("bolt", 14)}{risk}</span>'
                f'<span style="position:relative;height:6px;border-radius:3px;background:{t["track"]}" title="80% range Kp {lo:.1f} to {hi:.1f}">'
                f'<span style="position:absolute;top:0;bottom:0;left:{lo / 9:.1%};width:{max(hi - lo, 0.05) / 9:.1%};border-radius:3px;background:{bar}"></span>'
                f'<span style="position:absolute;top:-4px;width:14px;height:14px;margin-left:-7px;border-radius:7px;left:{d.kpmax / 9:.1%};background:{t["surface"]};border:3px solid {dot};box-sizing:border-box"></span>'
                f'<span style="position:absolute;top:-6px;bottom:-6px;left:50%;width:1px;background:{t["alert"]};opacity:0.6"></span></span>'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:18px;font-weight:600;text-align:right">{d.kpmax:.1f}</span></div>')
        origin_rows = issue[1]
        ui.show(f'<div class="tm-flat" style="position:relative;z-index:2;margin-top:-76px;overflow:hidden">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 22px;border-bottom:1px solid {t["hair"]}">'
                f'<span class="tm-eyebrow">DAILY MAXIMUM KP · NEXT {len(days)} DAYS</span>'
                f'<a class="tm-link" href="{ui.href("Forecast", theme)}" target="_self" style="font-size:13px">Full forecast →</a></div>{rows_html}'
                f'<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding:10px 22px 14px;font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:{t["muted"]}">'
                f'<span>Bar: 80% range on the Kp 0–9 scale · orange line: storm level (Kp 5−)</span>'
                f'<span>Issued {origin_rows["issued_at"].max():%d %b %H:%M} UTC</span></div></div>')

    tiles = []
    if hourly is not None:
        w = hourly.dropna().iloc[-1]
        speed_note = "Fast stream." if w["speed"] >= 500 else "Slow. Fast streams run 500–800 km/s."
        bz_note = ("Southward: energy is entering Earth's field." if w["bz_gsm"] < -2 else
                   "Northward: little coupling." if w["bz_gsm"] > 0 else "Near zero: little coupling.")
        tiles += [ui.tile("wind", "SOLAR WIND", f"{w['speed']:.0f}", "km/s", speed_note, t),
                  ui.tile("bz", "BZ FIELD", f"{w['bz_gsm']:+.1f}", "nT", bz_note, t),
                  ui.tile("density", "DENSITY", f"{w['density']:.1f}", "cm⁻³", "Protons per cubic centimetre.", t),
                  ui.tile("field", "FIELD STRENGTH", f"{w['b_scalar']:.1f}", "nT",
                          "Weak. Storms usually need 15 nT or more." if w["b_scalar"] < 15 else "Strong field.", t)]
    if f107 is not None and len(f107.dropna()):
        tiles.append(ui.tile("sun", "SOLAR FLUX F10.7", f"{f107.dropna().iloc[-1]:.0f}", "sfu",
                             f"Activity on the Sun ({f107.dropna().index[-1]:%d %b}).", t))
    tiles.append(ui.tile("aurora", "AURORA", AURORA_REACH.get(lv[2], "Polar"), "", "Rough guide from Kp; no location used.", t))
    ui.show(ui.grid(tiles, 190))

    head = _test_headline()
    spark = ""
    if past is not None:
        last = past["kp_pred"].tail(24)
        spark = (f'<article class="tm-card" style="padding:22px 24px;display:flex;flex-direction:column;gap:12px">'
                 f'<span style="display:flex;justify-content:space-between" class="tm-eyebrow"><span>NOWCAST · LAST 24 HOURS</span>'
                 f'<span>max {last.max():.1f}</span></span>{ui.sparkline(list(last), 480, 110, t["primary"], top=max(3.0, float(last.max())), labels=(f"{last.index[0]:%H:00} UTC", f"{last.index[-1]:%H:00} UTC"), unit=" Kp")}'
                 f'<a class="tm-link" href="{ui.href("Nowcast", theme)}" target="_self" style="font-size:13px">Open the nowcast →</a></article>')
    trust = ""
    if head and head[0]:
        trust = (f'<article class="tm-card" style="padding:22px 24px;display:flex;flex-direction:column;gap:10px">'
                 f'<span class="tm-eyebrow">HOW FAR TO TRUST THIS</span><span style="font-size:15px;line-height:1.55">'
                 f'Level with NOAA\'s official forecast one day ahead (Ap error {head[0]:.2f} vs {head[1]:.2f}, 2020 – mid-2026). '
                 f'The warning caught {head[2]:.0%} of storm days a day ahead.</span>'
                 f'<a class="tm-link" href="{ui.href("Scorecard", theme)}" target="_self" style="font-size:13px">See the scorecard →</a></article>')
    ui.show(ui.grid([x for x in (spark, trust) if x], 340))
    ui.show(ui.credits(t))


# ── Forecast ─────────────────────────────────────────────────────────────────
def _day_cards(hist: pd.DataFrame, warn_rows: pd.DataFrame, t: dict, actual: pd.Series = None) -> str:
    cards = []
    for d in hist.itertuples():
        r = warn_rows.loc[d.target_date] if len(warn_rows) and d.target_date in warn_rows.index else None
        warn = r is not None and _warned(r)
        lv = level_of(d.kpmax)
        risk_html = ""
        if r is not None:
            p, th = float(r["storm_prob"]), float(r["threshold"])
            risk_html = (f'<span style="display:flex;flex-direction:column;gap:6px;padding-top:10px;border-top:1px solid {t["hair"]}">'
                         f'<span style="display:flex;justify-content:space-between;font-size:12px"><span style="color:{t["muted"]}">Storm risk</span>'
                         f'<span style="font-family:\'IBM Plex Mono\',monospace;font-weight:600;color:{t["alert_text"] if warn else t["text"]}">{p:.0%}</span></span>'
                         f'<span style="position:relative;height:6px;border-radius:3px;background:{t["track"]}">'
                         f'<span style="position:absolute;left:0;top:0;height:6px;border-radius:3px;width:{min(1, p * 2):.0%};background:{t["alert"] if warn else t["primary"]}"></span>'
                         f'<span style="position:absolute;top:-3px;width:2px;height:12px;left:{min(1, th * 2):.0%};background:{t["text"]};opacity:.55"></span></span>'
                         + (ui.chip("WARNING", t["alert"], t["alert_fg"]) if warn else "") + "</span>")
        happened = ""
        if actual is not None and d.target_date in actual.index and pd.notna(actual[d.target_date]):
            a = float(actual[d.target_date])
            happened = (f'<span style="font-size:12px;color:{t["alert_text"] if a >= config.STORM_THRESHOLD else t["muted"]}">'
                        f'Actual Kp {a:.1f}{" · storm" if a >= config.STORM_THRESHOLD else ""}</span>')
        cards.append(
            f'<article class="tm-card" style="padding:18px;display:flex;flex-direction:column;gap:10px;{f"border-color:{t["alert"]};" if warn else ""}">'
            f'<span style="display:flex;justify-content:space-between;align-items:baseline"><span style="font-size:14px;font-weight:600">{d.target_date:%a}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:{t["muted"]}">{d.target_date.day} {d.target_date:%b}</span></span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:26px;font-weight:600">Kp {d.kpmax:.1f}</span>'
            f'<span style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:2px;background:{t["ramp"][lv[4]]}"></span>'
            f'<span style="font-size:13px">{lv[3]}</span><span style="margin-left:auto;font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:{t["muted"]}">Ap {d.ap:.0f}</span></span>'
            f'{happened}{risk_html}</article>')
    return ui.grid(cards, 150, 12)


def forecast(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    issue = latest_issue()
    if issue is None:
        ui.show(ui.hero("Forecast", theme, f"{now:%H:%M:%S}", "sun", "quiet", "7-DAY GEOMAGNETIC OUTLOOK",
                        "No forecast yet", "The daily job issues the first forecast after its next run.", "—", ""))
        return
    origin, latest, scores, recent, noaa = issue
    storm_log = get_storm_log()
    warn_rows = storm_log[storm_log["origin"] == origin].set_index("target_date") if len(storm_log) else pd.DataFrame()
    hist = latest[latest["model"] == "histgb"].sort_values("target_date")
    if not len(hist):
        hist = latest[latest["model"] == "trailing27"].sort_values("target_date")
    peak = hist.loc[hist["kpmax"].idxmax()]
    first, last = hist["target_date"].min(), hist["target_date"].max()
    warned_days = [d for d, r in warn_rows.iterrows() if _warned(r)] if len(warn_rows) else []
    lead = (f"Daily maximum Kp between {hist['kpmax'].min():.1f} and {hist['kpmax'].max():.1f}, highest on "
            f"{peak['target_date']:%A}. ")
    lead += ("No storm is forecast, but the chance of one on " + " and ".join(f"{d:%A}" for d in warned_days)
             + " is above the warning line." if warned_days and peak["kpmax"] < config.STORM_THRESHOLD else
             "A storm day is forecast." if peak["kpmax"] >= config.STORM_THRESHOLD else "No storm warnings this week.")
    heading = (f"{first.day} – {last.day} {last:%B %Y}" if first.month == last.month else
               f"{first.day} {first:%b} – {last.day} {last:%b %Y}")
    ui.show(ui.hero("Forecast", theme, f"{now:%H:%M:%S}", "sun", scene_level(peak["kpmax"]), "7-DAY GEOMAGNETIC OUTLOOK",
                    heading, lead, f"Kp {peak['kpmax']:.1f}", f"Week peak · {peak['target_date']:%a} {peak['target_date'].day}",
                    peak["kpmax"] >= config.STORM_THRESHOLD))

    if warned_days:
        d = warned_days[0]
        r = warn_rows.loc[d]
        body = f"{r['storm_prob']:.0%} chance of a storm day (Kp 5− or higher), above the {r['threshold']:.0%} warning line."
        nk = noaa_kp_for(noaa, d)
        if nk is not None and nk >= config.STORM_THRESHOLD:
            body += f" NOAA's official forecast also reaches Kp {nk:.2f} that day."
        ui.show(ui.banner(f"Storm watch · {d:%A} {d.day} {d:%B}", body, t))

    issued, flag = latest["issued_at"].max(), int(latest["origin_flag"].iloc[0])
    late_h = (issued - (origin + pd.Timedelta(days=1))) / pd.Timedelta(hours=1)
    note = (f"Issued {issued:%d %b %H:%M} UTC from GFZ data up to {origin:%d %b} ({GFZ_FLAGS.get(flag, flag)} values)."
            + (f" This issue went out {late_h:.0f} h into its first day because the scheduler started late; the models "
               "use no data from that day." if late_h > 3 else ""))

    d1 = hist.iloc[0]
    top_risk = warn_rows.loc[warn_rows["storm_prob"].idxmax()] if len(warn_rows) else None
    obs_last = recent.dropna(subset=["kpmax"]).iloc[-1]
    # day 1 is today when the issue goes out after midnight UTC, which is the usual case
    gap = (d1["target_date"].normalize() - now.tz_localize(None).normalize()).days
    d1_name = {0: "Today", 1: "Tomorrow"}.get(gap, f"{d1['target_date']:%A}")
    kpis = [ui.kpi(f"{d1_name} · {d1['target_date']:%a} {d1['target_date'].day}", f"Kp {d1['kpmax']:.1f}",
                   f"range {d1['kpmax_lo']:.1f} – {d1['kpmax_hi']:.1f}" if pd.notna(d1.get("kpmax_lo")) else "",
                   ui.level_chip(d1["kpmax"], t), t=t),
            ui.kpi(f"Week peak · {peak['target_date']:%a} {peak['target_date'].day}", f"Kp {peak['kpmax']:.1f}",
                   f"Ap {peak['ap']:.0f}", ui.level_chip(peak["kpmax"], t), color=t["primary"], t=t)]
    if top_risk is not None:
        w = _warned(top_risk)
        kpis.append(ui.kpi(f"Highest storm risk · {top_risk.name:%a} {top_risk.name.day}", f"{top_risk['storm_prob']:.0%}",
                           f"warning line {top_risk['threshold']:.0%}",
                           ui.chip("WARNING", t["alert"], t["alert_fg"]) if w else ui.chip("NO WARNING", t["raised"], t["muted"], t["hair"]),
                           color=t["alert_text"] if w else t["text"], border=t["alert"] if w else None, t=t))
    kpis.append(ui.kpi(f"Last observed · {obs_last.name:%a} {obs_last.name.day}", f"Kp {obs_last['kpmax']:.1f}",
                       f"Ap {obs_last['ap']:.0f}", ui.level_chip(obs_last["kpmax"], t), t=t))
    ui.show(ui.grid(kpis, 220))

    with ui.card("pages_live_1"):
        c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="center")
        choice = c1.radio("Quantity", list(FC_TARGETS), horizontal=True, label_visibility="collapsed", key="fc_quantity")
        show_noaa = c2.toggle("NOAA outlook", value=True, key="fc_noaa")
        show_ref = c3.toggle("Reference methods", value=not (FC_TRAINED & set(latest["model"])), key="fc_ref",
                             help="Persistence, 27-day recurrence, 27-day average and climatology: the simple forecasts every model must beat.")
        shown = latest if show_ref else latest[~latest["model"].isin(FC_REFERENCE)]
        col, unit = FC_TARGETS[choice]
        show_chart(forecast_chart(forecast_long(shown, recent, noaa if show_noaa else NO_NOAA, col), origin, col, unit,
                                  theme, forecast_band(shown, col)), theme)
        st.caption(note + " Hover for every value; the shaded band is HistGB's 80% range.")

    ui.show(_day_cards(hist, warn_rows, t))
    head = _test_headline()
    reading = (f'<article class="tm-flat" style="padding:22px 24px;display:flex;flex-direction:column;gap:14px">'
               f'<h2 class="tm-h2" style="font-size:16px">Reading this forecast</h2>'
               f'<dl style="margin:0;display:grid;grid-template-columns:120px minmax(0,1fr);gap:10px 16px;font-size:14px;line-height:1.5">'
               f'<dt style="color:{t["muted"]}">Kp value</dt><dd style="margin:0">The expected level for the day. It stays below storm level unless a storm is likely on average.</dd>'
               f'<dt style="color:{t["muted"]}">Storm risk</dt><dd style="margin:0">The chance the day reaches Kp 5− or higher. The tick marks that day\'s warning line.</dd>'
               f'<dt style="color:{t["muted"]}">80% range</dt><dd style="margin:0">The shaded band: in testing, 8 days in 10 fell inside it.</dd></dl></article>')
    good = ""
    if head and head[0]:
        good = (f'<article class="tm-flat" style="padding:22px 24px;display:flex;flex-direction:column;gap:14px">'
                f'<h2 class="tm-h2" style="font-size:16px">How good is it</h2><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px">'
                f'<span style="display:flex;flex-direction:column;gap:4px"><span class="tm-mono" style="font-size:22px;font-weight:600">{head[0]:.2f} '
                f'<span style="font-size:13px;font-weight:400;color:{t["muted"]}">vs {head[1]:.2f}</span></span>'
                f'<span class="tm-sub">Day-1 Ap error, HistGB vs NOAA official (2020 – Jun 2026)</span></span>'
                f'<span style="display:flex;flex-direction:column;gap:4px"><span class="tm-mono" style="font-size:22px;font-weight:600">{head[2]:.0%}</span>'
                f'<span class="tm-sub">of storm days caught one day ahead by the warning</span></span></div>'
                f'<a class="tm-link" href="{ui.href("Scorecard", theme)}" target="_self" style="font-size:14px">Full scorecard →</a></article>')
    ui.show(ui.grid([reading, good] if good else [reading], 340))

    done = scores.dropna(subset=[f"{col}_obs"]) if len(scores) else scores
    if len(done):
        mae = done.assign(err=done[f"{col}_err"].abs()).pivot_table(index="model", columns="lead", values="err", aggfunc="mean")
        rows = [[f"<strong>{FC_SERIES.get(m, m)}</strong>"] + [f"{v:.2f}" if pd.notna(v) else "—" for v in r]
                for m, r in mae.iterrows()]
        n = done["origin"].nunique()
        ui.show(ui.table(["Model"] + [f"Day {c}" for c in mae.columns], rows, set(range(1, len(mae.columns) + 1)),
                         caption=f"Live track record · mean {unit} error by lead day",
                         note=f"Over {len(done)} checked forecasts from {n} issue day{'s' if n != 1 else ''}. Recent observed values are "
                              "GFZ's provisional ones and are rescored when the definitive values arrive."))
    with st.expander("Forecast table · every model"):
        table = latest.pivot_table(index="target_date", columns="model", values=col)
        cols = list(table.columns)
        rows = [[f"{d:%a %d %b}"] + [f"{v:.2f}" if col == "kpmax" else f"{v:.1f}" for v in r] for d, r in table.iterrows()]
        ui.show(ui.table(["Day"] + [FC_SERIES.get(c, c) for c in cols], rows, set(range(1, len(cols) + 1))))
    ui.show(ui.credits(t))


# ── Explore ──────────────────────────────────────────────────────────────────
def _set_day(day: str):
    st.session_state["explore_day"] = pd.Timestamp(day).date()


def _apply_try_preset(name: str, base: pd.DataFrame):
    edited = base.copy()
    spec = TRY_PRESETS[name]
    if spec:
        last = edited.index[-1]
        for k in spec["days"]:
            day = last + pd.Timedelta(days=k)
            if day in edited.index:
                edited.loc[day, ["ap", "kpmax"]] = [spec["ap"], spec["kpmax"]]
    st.session_state["try_history"] = edited
    st.session_state["try_version"] = st.session_state.get("try_version", 0) + 1


def explore(theme: str, now: pd.Timestamp):
    t = TOKENS[theme]
    try:
        _, _, recent_obs, _ = get_forecasts()
    except (FileNotFoundError, pd.errors.EmptyDataError):
        recent_obs = None
    past = get_past_forecasts()
    first, last = past["origin"].min().date(), past["origin"].max().date()
    st.session_state.setdefault("explore_day", pd.Timestamp("2024-05-08").date())
    st.session_state.setdefault("explore_mode", "Replay a past day")
    mode = st.session_state["explore_mode"]
    origin = pd.Timestamp(st.session_state["explore_day"])
    stat, label, level = "—", "", "quiet"
    if mode == "Replay a past day" and recent_obs is not None:
        window = recent_obs["kpmax"].loc[origin + pd.Timedelta(days=1): origin + pd.Timedelta(days=7)].dropna()
        if len(window):
            stat, label = f"Kp {window.max():.1f}", f"highest in the 7 days after {origin.day} {origin:%b %Y}"
            level = scene_level(window.max())
    ui.show(ui.hero("Explore", theme, f"{now:%H:%M:%S}", "nebula", level, "EXPLORE", "Replay the forecaster",
                    "Pick any issue day since January 2020 and see the forecast exactly as it would have been made that "
                    "evening, next to what really happened. Or change the recent days yourself and watch the forecast respond.",
                    stat, label, level == "storm"))

    with ui.card("pages_live_2"):
        c1, c2, c3 = st.columns([2.2, 1.6, 3], vertical_alignment="bottom")
        mode = c1.radio("Mode", ["Replay a past day", "Edit the inputs"], horizontal=True, key="explore_mode",
                        label_visibility="collapsed")
        if mode == "Replay a past day":
            c2.date_input("Issue day", min_value=first, max_value=last, key="explore_day")
            with c3:
                b = st.columns(len(NOTABLE_DAYS) + 1)
                for col, (name, day) in zip(b, NOTABLE_DAYS.items()):
                    col.button(name, on_click=_set_day, args=(day,), width="stretch")
                b[-1].button("Latest issue", on_click=_set_day, args=(str(last),), width="stretch")

    if recent_obs is None:
        st.info("Observed history is not available yet.")
        return
    if mode == "Replay a past day":
        _replay(t, theme, past, recent_obs, pd.Timestamp(st.session_state["explore_day"]))
    else:
        _edit(t, theme, recent_obs)
    ui.show(ui.credits(t))


def _replay(t, theme, past, recent_obs, origin):
    rows = past[past["origin"] == origin]
    values, warn = rows[rows["model"] != "storm_warning"], rows[rows["model"] == "storm_warning"]
    values = values[~values["model"].isin({"persistence", "recurrence27", "climatology"})]
    if not len(values):
        st.info("No forecast stored for that day.")
        return
    actual = recent_obs["kpmax"]
    warn_rows = warn.set_index("target_date")
    verdicts, tally = [], {"caught": 0, "missed": 0, "fa": 0, "quiet": 0}
    for r in warn.sort_values("lead").itertuples():
        a = actual.get(r.target_date)
        if a is None or pd.isna(a):
            continue
        storm, w = a >= config.STORM_THRESHOLD, bool(r.warning) if not isinstance(r.warning, str) else r.warning == "True"
        key = "caught" if storm and w else "missed" if storm else "fa" if w else "quiet"
        tally[key] += 1
        verdicts.append((r, a, w, key))
    left, right = st.columns([2, 1], gap="medium")
    with left:
        with ui.card("pages_live_3"):
            q = st.radio("Quantity", list(FC_TARGETS), horizontal=True, key="replay_quantity", label_visibility="collapsed")
            col, unit = FC_TARGETS[q]
            window = recent_obs.loc[: origin + pd.Timedelta(days=7)]
            show_chart(forecast_chart(forecast_long(values, window, NO_NOAA, col, HISTORY_DAYS + 7), origin, col, unit, theme,
                                      forecast_band(values, col)), theme)
    with right:
        storm_days = tally["caught"] + tally["missed"]
        story = ("A burst of solar eruptions (CMEs) hit Earth on 10 May and drove the strongest storm in two decades: Kp 9 on "
                 "11 May. Eruptions leave no trace in past Kp, so the value forecast only expected an unsettled week. The storm "
                 "classifier warned for 11, 12 and 13 May, but its chance for the 10th stayed under the warning line. NOAA, which "
                 "watches the Sun directly, forecast Ap 37 and 50 for the 10th and 11th."
                 if origin == pd.Timestamp("2024-05-08") else
                 f"{storm_days} storm day{'s' if storm_days != 1 else ''} in the 7 days after this issue. Each forecast used data up to "
                 f"{origin.day} {origin:%B %Y} only.")
        cells = [(f"{tally['caught']} of {storm_days}" if storm_days else "0", "storm days warned", t["good"]),
                 (str(tally["missed"]), "storm days missed", t["alert_text"] if tally["missed"] else t["text"]),
                 (str(tally["fa"]), "false alarms", t["text"]), (str(tally["quiet"]), "quiet days called right", t["text"])]
        tally_html = "".join(f'<span class="tm-cell" style="background:{t["surface"]};padding:12px 14px;display:flex;flex-direction:column;gap:4px">'
                             f'<span class="tm-mono" style="font-size:24px;font-weight:600;color:{c}">{n}</span><span class="tm-sub">{lab}</span></span>'
                             for n, lab, c in cells)
        ui.show(f'<aside class="tm-flat" style="padding:22px 24px;display:flex;flex-direction:column;gap:16px">'
                f'<h2 class="tm-h2" style="font-size:16px">What happened</h2><p style="margin:0;font-size:14px;line-height:1.6">{ui.esc(story)}</p>'
                f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:{t["hair"]};border:1px solid {t["hair"]};border-radius:4px;overflow:hidden">{tally_html}</div></aside>')
    names = {"caught": ("Storm caught", t["good"]), "missed": ("Storm missed", t["alert"]),
             "fa": ("False alarm", t["alert_text"]), "quiet": ("Correct, quiet", t["muted"])}
    hist = values[values["model"] == "histgb"].set_index("target_date")
    rows = []
    for r, a, w, key in verdicts:
        fc = hist["kpmax"].get(r.target_date)
        rows.append([f"{r.target_date:%a %d %b}", f"{fc:.1f}" if fc is not None and pd.notna(fc) else "—",
                     f'<span style="color:{t["alert_text"] if w else t["text"]}">{r.storm_prob:.0%}</span>',
                     ui.chip("WARNING", t["alert"], t["alert_fg"]) if w else f'<span style="color:{t["muted"]}">—</span>',
                     f'<strong style="color:{t["alert_text"] if a >= config.STORM_THRESHOLD else t["text"]}">{a:.1f}</strong>',
                     f'<span style="display:inline-flex;align-items:center;gap:8px"><span style="width:8px;height:8px;border-radius:4px;background:{names[key][1]}"></span>{names[key][0]}</span>'])
    if rows:
        ui.show(ui.table(["Day", "Forecast Kp", "Storm risk", "Warning", "Actual Kp", "Verdict"], rows, {1, 2, 4},
                         caption="Forecast against reality, day by day", min_width=720))
    obs = recent_obs["ap"].reindex(values["target_date"]).to_numpy()
    err = values.assign(abs_err=(values["ap"] - obs).abs()).dropna(subset=["abs_err"])
    if len(err):
        summary = err.groupby("model")["abs_err"].mean().sort_values()
        ui.show(ui.table(["Model", "Mean Ap error over these 7 days"],
                         [[FC_SERIES.get(m, m), f"{v:.1f}"] for m, v in summary.items()], {1},
                         note="Lower is better. Models fitted on data up to 2019 for issue days up to June 2026 (the test run, scored once); "
                              "the live models, refitted up to June 2026, after that."))


def _edit(t, theme, recent_obs):
    kit = get_forecast_models()
    if kit is None:
        st.info("Live re-forecasting needs scikit-learn and statsmodels, which the in-browser version cannot load. "
                "Use the Streamlit app for this mode; replaying a past day works here.")
        return
    base = recent_obs[["ap", "kpmax", "f107_obs"]].tail(CONTEXT_DAYS)
    history = st.session_state.get("try_history")
    if history is None or history.index[-1] != base.index[-1]:
        history = base.copy()
        st.session_state["try_history"] = history
    with ui.card("pages_live_4"):
        ui.show(ui.section_head(f"The last {EDIT_DAYS} days, as GFZ published them",
                                "Change any value, or start from a preset. Every live model then forecasts the next 7 days. "
                                "Older days and F10.7 stay as published."))
        pcols = st.columns(len(TRY_PRESETS))
        for c, name in zip(pcols, TRY_PRESETS):
            c.button(name, on_click=_apply_try_preset, args=(name, base), width="stretch")
        v = st.session_state.get("try_version", 0)
        visible = history.tail(EDIT_DAYS)
        cols = st.columns(EDIT_DAYS)
        new = visible.copy()
        for c, (day, row) in zip(cols, visible.iterrows()):
            new.loc[day, "ap"] = c.number_input(f"Ap · {day.day} {day:%b}", 0.0, 400.0, float(row["ap"]), 1.0, key=f"ap_{v}_{day:%Y%m%d}")
            new.loc[day, "kpmax"] = c.number_input(f"Kp · {day.day} {day:%b}", 0.0, 9.0, float(row["kpmax"]), 0.333,
                                                   format="%.2f", key=f"kp_{v}_{day:%Y%m%d}")
    full = pd.concat([history.iloc[:-EDIT_DAYS], new])
    origin, fc, warn = run_forecasters(full, kit)
    changed = int((abs(new[["ap", "kpmax"]].to_numpy() - base.tail(EDIT_DAYS)[["ap", "kpmax"]].to_numpy()) > 1e-9).sum())
    with ui.card("pages_live_5"):
        q = st.radio("Quantity", list(FC_TARGETS), horizontal=True, key="edit_quantity", label_visibility="collapsed")
        col, unit = FC_TARGETS[q]
        show_chart(forecast_chart(forecast_long(fc, full, NO_NOAA, col), origin, col, unit, theme, forecast_band(fc, col)), theme)
        st.caption(f"Forecast from your history up to {origin:%d %b %Y}"
                   + (f", with {changed} value{'s' if changed != 1 else ''} changed from the real data." if changed else ": the real data, unchanged."))
    hist = fc[fc["model"] == "histgb"].sort_values("target_date")
    warn_rows = warn.set_index("target_date") if len(warn) else pd.DataFrame()
    if len(hist):
        ui.show(_day_cards(hist, warn_rows, t))
