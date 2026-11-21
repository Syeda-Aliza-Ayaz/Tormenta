# Tormenta roadmap: after v2.0

Work in order, top to bottom. Tick a box only when it is done and recorded in [DECISIONS.md](DECISIONS.md).
Blocked items (network, waiting for data) are listed in [TODO.md](TODO.md); [docs/plans/PLAN.md](docs/plans/PLAN.md) is the v2 build plan.

## Rules for every experiment

- **Rule first.** Write the keep/drop rule in DECISIONS.md before any run, and apply it as written.
- **Test period closed.** Decide on 2011–2019 only (the yearly harness, `src/forecast/validate_yearly.py`).
  The 2020 → test runs **once**, after the model is locked (section 7).
- **Isolated from the live model.** Experiments never change `models/`, `src/issue.py`, `forecasts/` or the daily
  job. Check the live-file fingerprints before and after each step.
- **Small first.** Try a small sample (a month, a year) before any large download.
- **Baseline to beat:** the current candidate, solar wind + 27-day echo + Poisson loss (`sw_rec_poisson`, D-68).

## 0. Now running

- [x] **Solar imagery, one-year check (D-70).** Coronal-hole features from daily AIA 193 Å images, 2016.
  - [x] Rules written (D-70)
  - [x] One-month trial (June 2015): download works; wind-speed link peaks 3 days later (+0.77)
  - [x] Preview, Jan–mid-May 2016: link holds, peak 3–4 days later (wind +0.50, Ap +0.37)
  - [x] Full 2016: adds information beyond the 27-day echo and today's wind (log-Ap error −7 to −9 % at 2–4 days
        in a simple 5-input model); passes the stop-early test
  - [x] Continue with section 1

## 1. Solar imagery: full test (only if section 0 passes)

- [x] Download images for **May 2010 – Dec 2019 only** (no test-period images; about 4.3 GB). Done: 3,489 files.
      Status 2026-11-20: paused once, resumed with `python -m src.ingest.fetch_aia` (skips days on disk, prints
      progress); 2,009 of 3,520 days on disk; the server is slow (hours left). 23 days have no 00:00 image.
- [x] Daily coronal-hole series: Earth-facing area, incoming area, darkness, 1–2 day change; filaments filtered
      by size and shape (3,467 days)
- [x] Yearly validation, D-70 rule: **passes** (Ap skill 0.131 → 0.160, days 2–4 0.110 → 0.155, 7 of 7 years,
      storm Heidke 0.310 → 0.364)
- [x] Leakage robustness check: passed (a one-day delay keeps most of the gain; shuffled dates lose it)
- [x] Live-image check: JSOC near-real-time images match the archive (all feature correlations 1.000, 30 days)
- [ ] Shadow mode: the daily job fetches yesterday's near-real-time image, computes the features, and logs the
      model next to the live one; fallbacks: no image → solar-wind model, no solar wind → live HistGB
- [ ] Lock the model, then the one-time 2020 → test (needs images 2020 – Jun 2026 and OMNI refreshed past Jan 2026)

## 2. Measure NOAA's storm catch rate (before any storm work)

- [x] Storm skill of NOAA's forecasts vs ours on 2017–2019 (D-71). Heidke day 1 / 2 / 3: NOAA 0.41 / 0.38 / 0.32,
      solar-wind candidate 0.40 / 0.34 / 0.34. NOAA ahead on days 1–2 (mainly fewer false alarms), ours on day 3.

## 3. Storms, one idea at a time (each with its own rule, each judged on 2011–2019)

- [x] **3a. Re-issue during the day (D-72). Failed the rule (check 4: 5 of 9 years); not adopted.** Every 3 hours (03 … 21 UTC), update today and tomorrow from the Kp
      blocks measured so far today and today's solar wind. Days 2–7 stay once a day.
  - [x] 1. Rule written (D-72) before any run
  - [x] 2. Replay dataset: every day 1947–2019 at each of the 7 update times (Kp blocks so far, solar wind so far)
  - [x] 3. Leakage tests: a block counts only once it has ended; data after the update time changes nothing
  - [x] 4. Yearly validation 2011–2019: updates vs the midnight forecast vs the simple rule
  - [x] 5. Decision by the rule, recorded in D-72: fails (today 9/9 years, tomorrow 5/9; needed 6/9)
  - [—] 6. Only if kept (not kept): live check, GFZ quick-look and NOAA estimated Kp vs GFZ final values, block by block
  - [—] 7. Only if kept (not kept): shadow mode, a separate 3-hourly job writing `forecasts/intraday_log.csv`, not shown
  - [—] 8. Only if kept (not kept): after a few weeks of shadow, decide whether to show it on the site
  - Nowcaster: not used in the test (it was trained on data that includes 2011–2019); the solar wind it reads is
    used directly. Its hourly estimate can be added in live use.
  - A "today-only" product (the part that did well) was considered and dropped (user's decision, 2026-11-20).
- [x] **3b. Flare and radio warning signs (D-74). Failed the rule (Heidke 0.308 vs 0.310, false alarms up); not adopted.** Large flares near the Sun's centre, radio bursts (type II/IV), proton
      events. Records from 1975/1996 (NOAA GOES flare lists, SWPC event reports); check availability first.
  - [x] 1. Data check: SWPC event reports, 1996–2025, one small archive per year (FTP warehouse, `YYYY_events.tar.gz`):
        X-ray flares (class, region), optical flares with location, radio sweeps (type II/IV), radio bursts
  - [x] 2. Data check: GOES X-ray flares are in the same event reports (XRA lines, class and region), so no
        separate list is needed
  - [x] 3. Data check: daily proton fluence (>1, >10, >100 MeV), 1996 onward (`YYYY_DPD.txt`)
  - [x] 4. Live sources: `json/edited_events.json` (same event types and fields, last ~30 days),
        `json/goes/primary/xray-flares-7-day.json`, `json/goes/primary/integral-protons-3-day.json`, all reachable
  - [x] 5. Verdict: enough history (1996 → , ~20 storm-rich years) and a live source in the same format.
        Caution for the rule: archive files are written a few days after the day (e.g. 21 Jun 2015 created
        24 Jun), so an event may appear later live than in the archive; check this before trusting a gain
        (the D-67 lesson). Example found: 21 Jun 2015, M2.0 flare at N12E13 with type IV sweep, a day before
        the 22–23 Jun storm (Ap 57, 72).
  - [x] 6. Rule written (D-74) before any run
  - [x] 7. Download event reports and particle data, 1996–2019 only (48 files; events from Jul 1996)
  - [x] 8. Parse into daily inputs, with leakage tests (only events up to the issue day; 3 tests pass)
  - [x] 9. Yearly validation 2011–2019
  - [x] 10. Decision by the rule, recorded in D-74: fails checks 1 and 2
- [ ] **3c. Longer CME catalogue. On hold.** SOHO/LASCO (CDAW, CACTus) from 1996, instead of DONKI from 2014
      (D-67). Finalised weeks late, so live use needs a real-time source. Low expected value for now: CME data
      (D-67) and flare signs (D-74) both failed, partly because storm skill is scored on 2015–2019, the quiet end
      of the cycle; 3c would face the same problem. Revisit only with a rule written for active years.
- [x] **3d. Storm start vs continuation (D-73). Failed the rule (false alarms rose 56 → 58 %); not adopted.** Separate the hard case (a new storm) from the easy one (a storm
      already under way), to cut false alarms.
  - [x] 1. Rule written (D-73) before any run
  - [x] 2. Features: how yesterday ended (last blocks, storm blocks, storm days in a row) — with leakage tests
  - [x] 3. Yearly validation 2011–2019
  - [x] 4. Decision by the rule, recorded in D-73: fails check 2. Side finding not used: Ap skill +0.010

- **Pattern across 3a, 3b, 3d:** each caught more storms by warning more often, so false alarms never fell and
  none passed. Side gains in Ap values (3d +0.010, 3b +0.006) were not what the rules tested, so not used.
- **3e. Ensemble with NOAA's forecast:** parked in `dev_notes/deferred_ideas.md` (user's decision).

## 4. Solar-wind candidate: conditions for adoption (D-69, running in parallel)

- [ ] Several weeks of shadow scores (`forecasts/shadow_log.csv`) against the live model
- [ ] Refresh OMNI past 2026-01-10, then compare the live archive with OMNI hour by hour; rescale if biased
      (live density looked low, 0.9–3 cm⁻³, on 12–18 Nov)
- [ ] 27-day echo available in the live archive (about 9 Dec 2026)

## 5. Smaller items

- [ ] **5a. Save the hourly nowcast** to `forecasts/nowcast_log.csv` in the daily job, so its live accuracy can be scored
  - [x] 1. Module: append the last 7 days of hourly nowcasts; keep the first value written for each hour
  - [x] 2. Daily job calls it; a failure only warns and never blocks the forecast
  - [x] 3. Tests (append-only, failure leaves the file alone, daily-job tests write to a temp folder)
  - [x] 4. Run once locally on the live feed (118 hours logged, 15–20 Nov)
  - [ ] 5. Push and merge (needs the user's go-ahead; touches the daily job). Waiting: the user will say when
        the UI changes are final, and everything goes in one push.
- [x] **5b. Report comparisons (D-75):** Holt-Winters, LSTM, GRU on the yearly harness (validation only, not shipped)
  - [x] 1. Method and leakage guards written (D-75)
  - [x] 2. Code, with leakage tests (a forecast for D unchanged when later data changes; 4 pass)
  - [x] 3. Run Holt-Winters (Ap skill −0.108: worse than the 27-day average)
  - [x] 4. Run LSTM and GRU (Ap skill 0.029 and 0.051)
  - [x] 5. Comparison table recorded in D-75: HistGB + solar wind 0.112 > HistGB 0.089 > GRU 0.051 > LSTM 0.029 >
        Holt-Winters −0.108
- [ ] Dashboard: design boards 2–4 on the canvas (Nowcast/Overview, Scorecard, Method), then build them
- [ ] Check the site on a phone

## 6. Lock the model (D-76)

- [x] Model locked and committed before any test data: HistGB + solar wind + 27-day echo + coronal holes, Poisson
      loss, live settings, no retuning; fallbacks no image → solar-wind model, no solar wind → live HistGB
- [x] Test protocol and adoption rule fixed in D-76
- [x] OMNI solar wind refreshed to 2026-11-05 (NASA SPDF yearly file; the hourly table is extended, not overwritten)
- [x] Test script written and dry-run on 2019 (`src/forecast/test_locked.py`; reproduces the harness exactly)
- [x] Bot changes built on `fixes`: daily near-real-time image step (`src/ingest/aia_live.py`, log
      `forecasts/imagery_daily.csv`), locked model in shadow mode (`src/forecast/locked_shadow.py`, log
      `forecasts/locked_shadow_log.csv`), astropy pinned; 28 tests pass; image step run once on the live feed
- [x] Download test-period images, 2020-01-01 → 2026-06-30 (`python -m src.ingest.fetch_aia --first 2020-01-01
      --last 2026-06-30`; 2,367 of 2,373 days, 6 with no 00:00 image)

## 7. Test once, then go live

- [x] Image features through 2026-06-30: `python -m src.forecast.imagery --last 2026-06-30`
- [x] The one-time test: `python -m src.forecast.test_locked` (marker file blocks a second run); record it in
      DECISIONS (D-77) whatever it shows: RMSE per lead, skill vs the 27-day average, storm warnings, NOAA,
      Diebold–Mariano tests, block-bootstrap interval → **D-77**: skill 0.122 vs 0.100, level with NOAA
- [x] Adoption rule (D-76) parts (a) and (b): better pooled Ap skill and day-1 RMSE than the live HistGB, storm
      Heidke days 1–3 not lower by more than 0.01
- [x] Fix the day-1 NaN in `test_locked.score` (a NOAA gap reached the Diebold–Mariano test); re-scored from the
      saved forecasts with `--rescore` (no refit)
- [x] If they pass: production fit on definitive days to `PRODUCTION_END` (`python -m src.forecast.locked_shadow`)
- [ ] Push and merge (needs the user's go-ahead; goes with the UI changes): the bot starts the image log and the
      locked shadow log
- [ ] Locked shadow status: add the 27-day echo state (`no_echo`, echo days missing) like sw_shadow; the first
      bot run logged `full` while 9 echo days were missing (proposed 2026-11-21, awaiting approval)
- [ ] At least 3 weeks of shadow running; check every fallback was exercised or tested (adoption rule part c)
- [ ] Switch the served forecast to the locked model with its fallbacks; update the app and the model card
- [ ] Paper: the angle from the test results (locked model vs NOAA vs live HistGB, with the significance tests)
      evaluation method)

## 8. Clean-up, NOAA comparison, report (planned 2026-11-21)

- [ ] **Clean-up** (reorganise + remove clutter, user's choice):
  - [x] Experiment-only code moved to `src/forecast/experiments/` (7 modules); imports, tests and documented
        commands updated; full suite passes (169)
  - [x] `reports.zip` and `docs/report/overleaf_upload.zip` removed: every file in them has an identical copy in the
        repo (checked by content); the Overleaf note now says to zip `docs/report/`
  - [x] Dead-code check: no unreferenced function or class; the 5 never-imported modules are command-line scripts
  - [x] README updated for the locked model, with the D-77 result
- [x] **NOAA comparison and paper decision** (after the one-time test; D-77: level with NOAA, better than the
      live model → solid paper): Ap days 1–3 and storm warnings, locked model
      vs NOAA vs live HistGB, with the D-76 significance tests. Guide fixed now: significantly better than NOAA →
      clear paper; level with NOAA and clearly better than the live model → solid paper (coronal holes as the
      contribution); clearly behind → workshop paper or report only
- [ ] **Report v2** (LaTeX, new, covering the nowcaster, the forecaster and the locked model; the v1 report stays):
      datasets, architecture, features, models tried and locked with parameter tables, evaluation method,
      decisions and reasons, results, NOAA comparison, live system and shadow, limitations, references; new figures:
      architecture diagram, coronal-hole example with its mask, live vs archive images, locked test vs NOAA
