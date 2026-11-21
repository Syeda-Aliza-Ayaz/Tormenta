# Tormenta: viva preparation

Everything an examiner can ask, with the answer and the reason behind it. Numbers are the ones in the final report
and in [DECISIONS.md](../DECISIONS.md) (D-numbers). Read Part 1 first; Part 13 is the question bank.

---

## Part 1. The project in 60 seconds (say this if asked "explain your project")

> Geomagnetic storms damage power grids, satellites and GPS. Their strength is measured by the **Kp index** (0–9,
> every 3 hours). We built **Tormenta**, which answers two questions.
>
> 1. **Nowcast: what is Kp right now?** The solar wind is measured by a spacecraft 1.5 million km upstream and
>    reaches Earth about an hour later. From 8 solar-wind inputs we build 66 features and a HistGradientBoosting
>    model estimates the current Kp with an 80% range. Test RMSE 0.573 Kp, 34% better than persistence.
> 2. **Forecast: how active will the next 7 days be?** Daily Ap and maximum Kp for days 1–7, plus a storm
>    probability. The final model uses past activity, the solar wind and **coronal holes measured on one solar
>    image per day**. On 2020–2026 it beats our index-only model (skill 0.122 vs 0.100) and is level with
>    NOAA's official forecast.
>
> Everything is deployed on Streamlit, Hugging Face and Flask, and every forecast is logged and scored every day.

---

## Part 2. The science you must know

| Term | Meaning | Why it matters to us |
|---|---|---|
| **Solar wind** | stream of charged particles from the Sun, 300–800 km/s, carrying a magnetic field (the IMF) | it is what disturbs Earth's field |
| **Bz** | north–south component of the IMF | **southward (negative) Bz** connects to Earth's field and lets energy in (reconnection). This is the main driver |
| **V·Bs** | speed × southward Bz | the "rectified electric field"; best single driver (EDA: correlates best 1 h earlier) |
| **Newell coupling** | a published formula for how much energy the solar wind passes to the magnetosphere | a physics feature, ref. Newell et al. 2007 |
| **L1 point** | 1.5 million km towards the Sun, where DSCOVR/ACE measure the wind | gives about **1 hour** of warning, which limits the nowcast's lead time |
| **Kp** | planetary K index, 0–9 in thirds (0, 0+, 1−, 1, …), one value per 3-hour block, from ground magnetometers | the nowcaster's target |
| **ap / Ap** | ap = linear version of Kp (0–400); **Ap** = daily mean of the 8 ap values | the forecaster's main target |
| **Storm** | Kp ≥ 5− (NOAA G1). In code: `STORM_THRESHOLD = 4.5`, which sits between 4+ (4.33) and 5− (4.67) | defines the positive class |
| **G1–G5** | NOAA storm scale: Kp 5 = G1 … Kp 9 = G5 | May 2024 was G5 |
| **F10.7** | solar radio flux at 10.7 cm, a measure of solar activity | proxy for the 11-year cycle; flare spikes are removed |
| **27-day rotation** | the Sun rotates once in ~27 days as seen from Earth | the same fast-wind source faces Earth again → **27-day echo** in Ap |
| **Coronal hole** | dark region in extreme-UV images where fast wind escapes | the wind reaches Earth **2–4 days later** → our forecast's biggest gain is on days 2–5 |
| **CME** | coronal mass ejection: a cloud of plasma thrown out in an eruption | causes the biggest storms; **invisible in our inputs until it arrives** (main limitation) |
| **Russell–McPherron effect** | more activity near the equinoxes | why season (sin/cos day of year) is a feature |
| **Definitive vs preliminary Kp** | GFZ revises recent values; definitive values are final | we train and score only on definitive values |

---

## Part 3. The physics behind every feature

An examiner who knows space weather will probe whether you understand *why* each input matters, not just *that* it
was used. This section links every feature group to its physical mechanism.

### 3.1 How a geomagnetic storm works (the energy chain)

```
Sun → solar wind (plasma + IMF) → magnetopause (compressed by ram pressure)
  → reconnection (if Bz is southward) → energy enters magnetosphere
  → ring current intensifies → ground-level magnetic field drops → Kp / Dst rise
```

**Reconnection** is the key step. Earth's magnetic field points northward at the dayside magnetopause. If the
interplanetary magnetic field (IMF) also points northward (+Bz), the two fields press together without connecting —
very little energy enters. When Bz turns **southward (−Bz)**, the two oppositely directed fields merge, opening a
channel through which solar-wind energy flows into the magnetosphere. This is why Bz is the single most important
driver: a fast, dense wind with northward Bz produces barely any activity, while a slow wind with strongly southward
Bz can trigger a storm.

The energy that enters goes into three main sinks:
1. **Ring current** — ions trapped on closed field lines around Earth; their westward drift weakens the surface field
   (measured as Dst/SYM-H drop). This is what sustains a storm over hours to days.
2. **Auroral electrojet** — currents in the high-latitude ionosphere (~100 km altitude) driven by field-aligned
   currents from the magnetotail. Kp is sensitive to these: magnetometers at mid-latitudes pick up the disturbance.
3. **Radiation belts** — high-energy electrons and protons; dangerous to satellites but not directly measured by Kp.

### 3.2 Raw solar-wind inputs (8 columns from OMNI)

| Input | Symbol | Physical meaning | Why it drives Kp |
|---|---|---|---|
| **IMF Bz (GSM)** | Bz | north–south magnetic field component in Geocentric Solar Magnetospheric coords | negative = reconnection → energy in; the main on/off switch |
| **IMF By (GSM)** | By | dawn–dusk component | rotates the reconnection geometry; controls where energy is deposited (dawn vs dusk convection cell); enters the **clock angle** |
| **B scalar** | \|B\| | total field strength | sets the ceiling on how strong Bz/By can be; used in β and Mach |
| **Speed** | V | bulk proton speed, 300–800+ km/s | fast wind = more kinetic energy flux, compresses the magnetopause more; V appears in every coupling function |
| **Density** | n | proton number density, cm⁻³ | contributes to ram pressure and Alfvén Mach; density pulses (shocks) trigger sudden commencements |
| **Temperature** | T | proton temperature, K | enters plasma β; high-T + high-V = fast-stream interaction region; anomalously low T inside a CME magnetic cloud |
| **F10.7** | — | 10.7 cm solar radio flux (solar flux units, 1 sfu = 10⁻²² W/m²/Hz) | proxy for UV + EUV output; tracks the 11-year solar cycle; more spots → more CMEs, more activity overall |

These 8 are the irreducible physical inputs. Everything else we compute is a derived quantity.

**GSM coordinates:** Geocentric Solar Magnetospheric — x-axis points from Earth to Sun, z-axis is chosen so that
Earth's magnetic dipole lies in the x-z plane. This frame rotates with the dipole tilt, which is why it matters:
Bz in GSM directly tells you whether the IMF opposes or aligns with the geomagnetic field.

### 3.3 Derived physics quantities (computed in `src/features.py:derived`)

| Feature | Formula (code) | Physical basis |
|---|---|---|
| **Dynamic pressure** | p = m_p · n · V² | the **ram pressure** of the solar wind. It compresses the magnetopause; a sudden pressure pulse (CME sheath or corotating interaction region) pushes the magnetopause inward, increasing geomagnetic activity. The 1-hour pressure change (`pressure_change1h`) detects shock arrivals |
| **V·Bs** (rectified electric field) | V · max(−Bz, 0) | Akasofu's **epsilon parameter** simplified: the dawn-to-dusk convection electric field, but only counted when Bz is southward. Energy transfer ∝ V × southward B. This is the best single predictor of Kp because it captures *both* the reconnection switch (Bz < 0) and the energy flux (V). In EDA, V·Bs at 1-hour lag has the highest correlation with Kp |
| **−V·Bz** (electric field) | −V · Bz | the full motional electric field E = −V×B projected onto the dawn–dusk direction. For a linear model this is cleaner because the sign carries information (northward Bz = negative coupling), but for a tree the rectified form V·Bs is equivalent |
| **Plasma β** | β ∝ nT / B² | ratio of thermal to magnetic pressure. **Low β (< 1)** means the magnetic field dominates — typical inside **CME magnetic clouds** (strong, smooth field, cool plasma). **High β** is normal solar wind where the field is weaker. This feature lets the model distinguish CME-like structures from ambient wind |
| **Alfvén Mach number** | M_A = V√n / (20·B) | how supersonic the wind is relative to **Alfvén waves** (the magnetic equivalent of sound waves in a plasma). Normal wind: M_A > 6. CME sheaths: M_A 2–4. **Low M_A paradoxically enhances geoeffectiveness** because the bow shock and magnetosheath compress and amplify the already-strong magnetic field rather than randomising it |
| **Transverse field Bt** | √(By² + Bz²) | the total IMF component perpendicular to the Sun–Earth line; the "raw material" available for reconnection |
| **sin(θ_c/2)** | sin(½ arctan2(By, Bz)) | the **IMF clock angle** fraction — the angle of the transverse field measured from north. When θ_c ≈ 180° (Bz strongly southward), sin(θ_c/2) ≈ 1 and reconnection is maximum. When θ_c ≈ 0° (northward), sin(θ_c/2) ≈ 0 and reconnection shuts off. The half-angle form comes from the **anti-parallel merging geometry**: reconnection occurs where the angle between the two fields exceeds ~90° |
| **Newell coupling** | V^(4/3) · Bt^(2/3) · sin^(8/3)(θ_c/2) | the **Newell et al. (2007) universal coupling function**: the rate at which the solar wind opens magnetic flux on the dayside magnetopause (units: Wb/s). The exponents were fit empirically to 10+ magnetospheric response indices (Dst, AE, Kp, polar cap potential). It unifies the reconnection geometry (clock angle), the magnetic energy density (Bt) and the energy flux (V) in a single number. In our EDA it correlates 0.41 with Kp — higher than any single raw input except speed |

### 3.4 Why lags and rolling windows matter (the time physics)

The solar wind is measured at L1, **1.5 million km upstream**. At 400 km/s the signal reaches Earth in ~62 minutes;
at 800 km/s, ~31 minutes. But the magnetosphere responds on **multiple timescales**:

| Timescale | Process | What the model needs |
|---|---|---|
| **Minutes** | sudden commencement (pressure pulse) | pressure, pressure_change1h |
| **1–3 hours** | substorm cycle: dayside reconnection fills the plasma sheet → cross-tail current sheet thins → reconnection in the tail → substorm onset, auroral breakup | lags 1–3 h of Bz, Newell; 3-h rolling mean/std |
| **3–6 hours** | continued energy injection builds the partial ring current | 3–6 h rolling Newell; block-so-far stats |
| **6–24 hours** | ring current builds to storm main phase; recovery half-life ≈ 12 h | 6, 9, 12, 24 h rolling speed and Newell means; storm memory (decay features with 6 h and 12 h half-lives) |
| **Days** | corotating interaction regions (CIR): fast stream overruns slow → compressed, turbulent interface lasting 1–2 days | 24-h speed mean separates CIRs from transients |

**Block-so-far features:** Kp is defined for a 3-hour block but the app can be queried at any hour within it.
Cumulative mean, max and min of key variables since the block started tell the model how much of the current block
it has seen. Without these, the error was highest in the first hour of each block (v1 → v2 fix).

### 3.5 Storm memory (exponential decay features)

The magnetosphere is not memoryless: after energy injection, the **ring current decays roughly exponentially**
(the Dessler–Parker–Sckopke relation links ring-current energy to the Dst depression). The `storm_memory` features
model this decay:

> weighted mean of Newell coupling over the last 48 hours, weight = 0.5^(k/half_life)

- **6-hour half-life** ≈ the substorm recovery timescale (the auroral electrojet recovers in a few hours).
- **12-hour half-life** ≈ the ring-current decay timescale (charge exchange with the hydrogen geocorona).

This gives the model a "how charged is the magnetosphere right now?" input that fixed rolling windows cannot capture
as cleanly, because a 24-hour mean weights a 20-hour-old substorm the same as the current hour.

### 3.6 F10.7 and the 81-day mean (solar cycle context)

F10.7 is emitted by hot, magnetically active regions on the Sun (gyroresonance radiation from electrons spiralling
in strong magnetic fields above sunspots). It correlates tightly with sunspot number and with the Sun's total
UV/EUV output. We use two forms:
- **Yesterday's F10.7:** the recent activity level. Spikes from solar flares are removed (> 2× the trailing
  27-day median → missing) because a flare spike is a one-time radio burst that does not predict the next hour's Kp.
- **81-day trailing mean:** the smooth solar-cycle level (three solar rotations). Tells the model whether we are
  in solar minimum (Kp rarely exceeds 4) or solar maximum (storms are 3–5× more frequent). 81 days is the
  standard smoothing (Covington, 1969); it averages over short-term fluctuations from individual active regions.

### 3.7 Cyclical time features (hour-of-day and day-of-year)

**Hour of day** (sin, cos encoding so 23:00 is next to 00:00): Earth's magnetic dipole is tilted ~11° from the
rotation axis and ~23° from the GSM z-axis in total. As the planet rotates, the **subsolar point** (where the
solar wind hits head-on) shifts in magnetic latitude, changing the reconnection geometry. The UT effect on
geomagnetic activity is well documented (Cliver et al., 2000): some UT hours are systematically more geoeffective.

**Day of year** (sin, cos): the **Russell–McPherron effect** (1973). The GSM z-axis is defined by the plane
containing the Sun–Earth line and Earth's dipole. Near the **equinoxes** (March, September), the GSM z-axis is
most tilted relative to the ecliptic, which means a By-dominated solar wind in ecliptic/GSE coordinates projects
more strongly onto **−Bz in GSM** — increasing the reconnection rate. This is why geomagnetic activity peaks near
the equinoxes (the "semi-annual variation"), even though the Sun has no seasonal cycle. The **equinoctial
hypothesis** (a related explanation) adds that at the equinoxes Earth's dipole is most symmetric with respect to
the solar wind flow, maximising the cross-section for energy input.

### 3.8 Forecaster: the 27-day recurrence features

The Sun rotates once in ~27 days as seen from Earth (the **Carrington rotation** is 27.2753 days; the synodic
period seen from Earth is ≈27.27 days). A fast-wind source (a coronal hole) that faces Earth today will face it
again in 27 days. The features:
- `ap_rec27`: Ap exactly 27 days before the target → "was it active last time this solar longitude faced us?"
- `ap_rec27w`: 3-day mean around −27 → smooths the ±1 day jitter from differential rotation (the Sun rotates
  faster at the equator than the poles, so the period varies by source latitude).
- `ap_rec54`, `ap_rec81`: two and three rotations back; coronal holes can persist for **months to over a year**
  (especially the polar extensions during declining phase of the solar cycle).
- `sw_speed_rec27`, `sw_speed_max_rec27`: the solar-wind speed 27 days before the target → fast wind recurs.
- `sw_by_rec27`: By carries the **sector structure** (toward/away polarity of the heliospheric current sheet),
  which is fairly stable over several rotations.

The 27-day echo is the strongest predictor beyond day 3. At that lead time, neither the current wind nor the
current Kp tell you much — but the 27-day echo remembers that a coronal hole was there last rotation. The EDA
autocorrelation plot confirms the peak at lag 27.

### 3.9 Forecaster: daily solar-wind summaries (16 features)

For the issue day D and D−1 (complete UTC days whose data is known when the forecast is made):
- `sw_speed`, `sw_speed_max`: current wind speed; a fast stream crossing today will likely persist into tomorrow
  (CIR duration ≈ 1–2 days). Speed is used rather than Bz because speed persists for days while Bz fluctuates
  on sub-hour scales.
- `sw_bz`, `sw_bz_min`: how southward was the field? A CME sheath still passing → sustained southward Bz.
- `sw_vbs`: the coupling level today — how much energy was deposited.
- `sw_density`, `sw_b`, `sw_pressure_max`: shock or CME sheath presence (high density + high B + high pressure
  = compressed plasma ahead of a fast structure).
- `sw_speed_change`: is the wind speeding up (interaction region **arriving**) or slowing down (trailing edge)?
  The rising phase of a CIR carries the compressed interface and is more geoeffective.
- Lag-1 versions of speed and V·Bs: "was yesterday more or less active than today?" A trend matters: rising
  activity means a structure is still building; falling means recovery.

These add information the index alone cannot provide: Ap tells you the day was active, but not *why*. If it was a
fast stream still present, tomorrow will also be active; if it was a CME that has passed, tomorrow will be quiet.
The solar wind disambiguates.

### 3.10 Forecaster: coronal-hole image features (7 features)

Coronal holes are **open-field regions** in the Sun's corona. In closed-field regions (loops), the magnetic field
lines connect back to the solar surface and trap hot plasma (bright in EUV). In coronal holes, the field lines
extend into the heliosphere — the plasma escapes along them, creating a **high-speed stream** (HSS, 600–800 km/s
vs 300–400 km/s for slow wind). The low density makes coronal holes appear **dark** in EUV images.

**SDO/AIA 193 Å** images the **Fe XII** emission line (iron ionised 11 times, at ~1.5 million K). This wavelength
is ideal because coronal holes are most clearly distinguished from quiet Sun at 193 Å — bright active regions and
dim holes both stand out against the moderate background.

**Travel time:** a fast stream from a coronal hole at disk centre takes **2–4 days** to reach Earth (depending on
speed and the Parker spiral geometry). This is why the coronal-hole features add the most on **days 2–5**: by day 1
the wind may not have arrived; by day 6–7 the solar rotation has moved the hole past the Earth-facing longitude and
its wind is now heading elsewhere.

Our 7 image features:
| Feature | Physical meaning |
|---|---|
| `ch_band_low` | % of the low-latitude Earth-facing strip covered by holes → the fraction of the geo-effective zone that is open field |
| `ch_band_low_lag1`, `_lag2` | the same, one and two days earlier → tracks the hole's rotation across the disk; a hole moving from east to centre is approaching Earth-facing position |
| `ch_band_low_change` | is the hole growing or shrinking? A growing hole seen approaching centre → larger fast stream coming |
| `ch_east` | % of the incoming (east-limb) strip → holes that will face Earth in 2–4 more days (advance warning) |
| `ch_disk` | total visible-disk coverage → general open-flux level; more open flux = more fast wind globally |
| `ch_dark` | median brightness inside the holes relative to disk median → darker = lower density = **stronger open field = faster wind**. This is physically grounded: the depletion in EUV brightness correlates with the speed of the resulting HSS |

**Why measured areas, not a CNN:** ~3,500 training images is far too few for a deep network; physically motivated
features are stable, explainable, and the **placebo test** (images assigned to random dates → gain disappears,
D-70) confirms the signal is real. One day late → gain preserved, confirming that the temporal alignment, not
overfitting, is the source.

### 3.11 Summary: the information available at each timescale

| Timescale | What's available | Key features | Physical limit |
|---|---|---|---|
| **Now** (nowcaster) | DSCOVR/ACE at L1 | Bz, speed, Newell, V·Bs, lags, rolling windows, block stats, memory | L1 → Earth ≈ 1 h; CME onset invisible until sheath arrives |
| **Tomorrow** (day 1) | today's wind + recent Kp | sw_speed, sw_vbs, ap_lag0, ap_mean3 | CIR persistence; CME sheath still passing |
| **Days 2–5** | 27-day echo + coronal holes | rec27, ch_band_low, ch_east | coronal hole fast-stream travel time; CMEs still invisible |
| **Days 6–7** | 27-day echo + solar cycle | rec27/54/81, f107, f107_mean81, season | only statistical recurrence; hole may have evolved |

The fundamental limit: **CMEs are invisible in all of these inputs until they arrive at L1.** A CME launched from
the Sun takes 1–4 days to reach Earth, but its southward Bz is not known until L1 measurement — by which time
it is only ~1 hour away. This is why our day-1 forecast missed the onset of the May 2024 G5 storm (the CME
arrived on day 1; the model could only warn for the following days once the wind was elevated). Overcoming this
limit would require **coronagraph CME detection** and heliospheric propagation models, which is listed as future
work.

### 3.12 Physics questions for the viva

29. *What is magnetic reconnection and why does it matter?* When oppositely directed magnetic fields meet, they
    merge, converting magnetic energy to kinetic and thermal energy. At the magnetopause, southward IMF meets
    Earth's northward field → field lines open → solar-wind energy enters. It is the main energy gate.
30. *Why is Bz more important than speed?* Speed sets the energy flux, but without southward Bz the energy has no
    way in. A 300 km/s wind with Bz = −20 nT is more geoeffective than 800 km/s with Bz = +10 nT.
31. *Explain the Newell coupling function.* V^(4/3) Bt^(2/3) sin^(8/3)(θ_c/2): the rate of dayside flux opening.
    V = energy flux, Bt = available perpendicular field, sin^(8/3)(θ_c/2) = how much of that field is anti-parallel
    to Earth's. Empirical exponents fit 10+ indices simultaneously (Newell et al., 2007).
32. *What does low plasma β tell you?* Magnetically dominated plasma — likely a CME magnetic cloud with a strong,
    smooth, rotating field. If Bz turns southward inside it, the storm can be intense and prolonged.
33. *Why do coronal holes produce fast wind?* Open field lines let plasma escape along them. The expansion geometry
    (narrow at the base, wide at the top) accelerates the wind through the wave-pressure mechanism
    (Alfvén-wave-driven). Less mass on open lines → lower density → darker in EUV.
34. *Why is the 27-day echo the best predictor beyond day 3?* The same coronal hole faces Earth every rotation.
    At 3+ days ahead the current wind tells you almost nothing; the echo remembers last rotation's activity.
35. *Why does the Russell–McPherron effect cause semi-annual peaks?* At equinoxes the GSM frame is most tilted
    relative to the ecliptic, projecting the By-dominated sector field onto −Bz → more reconnection.
36. *What is a corotating interaction region (CIR)?* A fast stream runs into the slow wind ahead of it, creating
    a compressed, turbulent interface. CIRs recur every 27 days and cause moderate (G1–G2) storms. The rising-speed
    phase is more geoeffective than the peak.
37. *Why can't you predict CME storms?* The key variable — the CME's internal Bz at Earth — is unknown until L1
    measurement (~1 hour). Pre-arrival, we can see the CME in coronagraphs (white-light halo), but the magnetic
    field direction inside it is not measurable remotely. This is the central unsolved problem in space weather.

---

## Part 4. Data (data collection section)

| Dataset | What | How | Licence | Size |
|---|---|---|---|---|
| NASA OMNI2 hourly | solar wind at Earth's bow shock, 1998 → | SPDF yearly files over HTTPS | NASA public | 245,688 hours |
| GFZ Potsdam | Kp, ap, Ap, F10.7, definitive flag, 1932 → | text file over HTTPS, refreshed daily | CC BY 4.0 | 34,653 days |
| SDO/AIA 193 Å | one 1024×1024 solar image per day, 2010 → | Stanford JSOC archive + near-real-time folder | NASA open | 5,856 images |
| NOAA SWPC real-time | live solar wind, F10.7 | JSON API | public domain | live |
| NOAA RSGA | NOAA's own forecasts | FTP | public domain | **benchmark only** |
| NOAA event reports, NASA DONKI | flares, CMEs | FTP / API | public | experiments (rejected) |

**Requirement check:** ≥5,000 rows ✓ (245,688), ≥15 features ✓ (66), ≥2 public sources combined ✓ (OMNI + GFZ),
documented source/method/licence/date ✓ (`DATA.md`), no personal data ✓, download script ✓
(`python -m src.download_data`, raw data not in git).

**Why each data choice**
- **OMNI, not raw spacecraft data:** OMNI is cleaned, cross-calibrated and already time-shifted to Earth's bow shock.
- **GFZ, not NOAA's Kp, as labels:** GFZ is the official producer of Kp; NOAA's value is an estimate.
- **Only definitive labels:** preliminary values still change; learning from them would learn noise.
- **Each hour labelled with its 3-hour block's Kp:** the live app runs at any hour, mid-block; training on
  whole-block averages would use data the live app does not have yet. (245,688 rows ≈ 81,900 independent labels.)
- **NOAA forecasts never as inputs (D-06):** otherwise our skill would be borrowed from NOAA.
- **Forecaster trained from 1947-06-01 (D-19):** first day every input exists (the 81-day F10.7 mean); D-66 tested a
  shorter history and it was worse, so the long history stays.
- **Solar images: one per day at 00:00 UTC:** the forecast is issued after the day ends; one image is enough because
  coronal holes change slowly (a one-day-old image kept almost all the gain).

---

## Part 5. EDA (what each plot showed, and what we did because of it)

| Rubric item | Finding | Decision it caused |
|---|---|---|
| **Class balance** | storm hours 4.5% of training years (4.06% all years), G3+ ≈ 0.5% | report storm-hour RMSE; separate storm classifier with rare-event thresholds |
| **Missing values** | ≤2.3% per input, up to 12% in 2000–2002; half the missing hours in gaps > 24 h | keep gaps as gaps (no interpolation); HistGB handles NaN; median imputation for other models |
| **Outliers** | speed to 1189 km/s, Bz to −58 nT | they are documented storms → **kept** (removing them removes the events we want to predict) |
| **Correlations** | speed ρ=0.58, temperature, \|B\|, V·Bs 0.41, Bz −0.33; Kp rises only for southward Bz | coupling features (V·Bs, −VBz, Newell) |
| **Distributions** | speed, density right-skewed | tree models are scale-insensitive; scaling only for KNN/SVR/linear |
| **Time structure** | Ap autocorrelated for days, peaks every 27 days; storm share 0.2% (2009) to 15.5% (2003) | 27/54/81-day echo features; **time-ordered** splits, never shuffled |

Viva tip: if asked "why didn't you remove outliers?" → *because in space weather the outliers are the signal.*

---

## Part 6. Structural design (architecture)

```
download script ─► data/raw ─► clean (fill codes → NaN, hourly grid) ─► features (one shared module)
                                                                         │
           training (time-ordered split, Pipeline, CV) ─► joblib model ──┤
                                                                         ▼
GitHub Actions daily job ─► issue forecast ─► append-only logs ─► Streamlit / Hugging Face / Flask
                      └──► score yesterday's forecasts against GFZ and NOAA
weekly job ─► health check ─► retrain only after 2 bad checks ─► promote only if better on unseen data
```

**Repository:** `data/` (download script), `notebooks/` (nowcaster, 6 notebooks), `src/` (all code),
`app/` (Streamlit, Flask, Hugging Face), `models/` (joblib bundles), `tests/` (173 tests), `requirements.txt`
(exact pins), `DATA.md`, `DECISIONS.md`.

**Design principles and why**
1. **One feature module shared by training and live serving** → the two can never compute features differently
   (train/serve skew). A parity test proves it.
2. **Append-only logs** → a forecast exists only if it was issued before its day; nothing is backfilled or edited.
   This is what makes the live record trustworthy.
3. **Optional inputs never block the forecast** → solar wind, images and NOAA are wrapped; a failure only warns and
   the model falls back.
4. **Shadow mode** → a new model runs next to the live one, logged but not shown, before it is trusted live.
5. **Frozen models with a gate** → the weekly job retrains only after two degraded checks, and a new model replaces
   the old one only if its RMSE on the newest 6 unseen months is ≤ 1.02 × the current model's.

**Deployments (all three)**
- **Streamlit Community Cloud** (`tormenta.streamlit.app`): six pages; input form (what-if), prediction with 80%
  range and storm probability, explanatory charts.
- **Hugging Face:** model + code + model card (`aliza-ayaz/tormenta`), and a live Space. The Space runs Streamlit
  **in the visitor's browser** (stlite/Pyodide) because hosted Gradio/Docker Spaces need a paid account. The
  browser cannot load a scikit-learn pickle, so the trees are exported to numpy (`current_portable.npz`); a test
  shows identical predictions.
- **Flask (local):** HTML form, `/predict` (form or JSON), `/api/forecast`, per-field validation, HTTP 400 with a
  message per bad field.

---

## Part 7. Methodology (the ML lifecycle, step by step)

### 7.1 Pre-processing
- **Cleaning:** fill codes (999.9, 9999…) → missing; complete hourly grid so "3 hours ago" always means 3 hours.
- **F10.7 flare spikes:** values > 2× the trailing 27-day median of earlier days → missing (D-47 fixed a bug where
  24 flare days distorted ~1,900 feature days). Yesterday's F10.7 is used, because today's is measured at ~20:00 UTC.
- **Encoding:** no categorical inputs; time is cyclic, so hour and day-of-year are encoded as **sin/cos** (23:00
  next to 00:00, 31 Dec next to 1 Jan).
- **Imputation + scaling:** `SimpleImputer(median)` + `StandardScaler` inside a scikit-learn `Pipeline`, fitted on
  training rows only. Needed by Linear Regression, KNN, SVR (distance/scale-sensitive). HistGB uses NaN natively.

### 7.2 Feature engineering
- **Nowcaster, 66 features** from 8 inputs: coupling (−VBz, V·Bs, Newell), pressure, plasma β, Alfvén Mach, lags
  1–9 h, 3–24 h windows (mean, std, min/max), statistics since the 3-hour block began (added in v2 because v1's error
  was highest in the first hour of each block), F10.7 and its 81-day mean, sin/cos time.
- **Forecaster, 52 features:** 29 index features (Ap and max Kp of last 7 days, 3/7/27-day means, values 27/54/81 days
  before the target, F10.7, season) + 16 solar-wind (issue day, day before, 27-day echo of speed and By) + 7
  coronal-hole areas (Earth-facing strip on D, D−1, D−2, change, incoming area, whole disk, darkness).
- **Coronal-hole detection (no learning):** normalise by exposure; dark = below 0.35 × disk median after a 5-px median
  filter; 7×7 morphological opening; keep regions ≥ 300 px (removes filaments); Earth-facing strip |x| < 0.3 R.

### 7.3 Why feature engineering is outside the Pipeline (likely question!)
A Pipeline prevents leakage from steps that **learn** (fit) from data. Our features learn nothing: fixed formulas over
current and past hours. Same values inside or outside, so they cannot leak test information. All fitted steps are
inside. Reasons to keep them outside:
1. **Lags need the continuous series.** A Pipeline only receives one fold's rows; windows at each block start lose
   their history. Tested: training features identical, but 3.7% of test rows and 7% of each CV fold changed.
2. **Label rows are selected after features** (definitive Kp only), and a Pipeline cannot drop rows between steps.
3. **One module serves training and live use.**
Causality is guaranteed by tests instead (delete future data → features unchanged).

### 7.4 Split
- **Time-ordered, never shuffled.** Shuffling lets the model see the future: neighbouring hours are nearly identical,
  so a shuffled split leaks and gives a falsely good score.
- **Nowcaster:** train 1998–2016 (68%), validation 2017–2019 (11%), test 2020–Jan 2026 (21%).
- **Forecaster:** train from 1947; validation by the **yearly harness** 2011–2019 (each year predicted by a model
  trained on all earlier years); test 2020-01 to 2026-06 (2,373 days, 325 storm days).
- Why not 70/15/15 exactly: we split by **whole years** so each split is a clean period and solar-cycle phases are not
  cut mid-year; percentages come out close to the suggested ones.

### 7.5 Models
| Product | Baseline | Models |
|---|---|---|
| Nowcaster | persistence ("Kp now = previous block's Kp") | Linear Regression, KNN, SVR (RBF), Random Forest, **HistGradientBoosting** |
| Forecaster | persistence, 27-day recurrence, **27-day mean**, climatology | ARIMA/SARIMA/ARIMAX, Chronos (pretrained transformer, zero-shot), Holt-Winters, LSTM, GRU, **HistGB (14 direct models)** + storm classifier |

**Why HistGB won:** best CV, validation and test RMSE; handles missing values natively (live data has gaps); fast on
245k rows; captures non-linear thresholds (Bz turning south); supports quantile loss for intervals.
**Why direct multi-step (one model per lead day):** a recursive model feeds on its own errors; day-1 mistakes would
compound into day 7.
**Why gradient boosting beat LSTM/GRU (D-75):** ~23,000 daily samples and a few dozen hand-built features favour trees;
recurrent nets need far more data and tuning. Holt-Winters chased day-to-day noise and was worse than the 27-day mean.

### 7.6 Tuning
- **Nowcaster:** `RandomizedSearchCV` over **5-fold `TimeSeriesSplit`** (each fold trains on the past, validates on the
  future), scoring negative RMSE. KNN and SVR tuned on every 9th hour (SVR is O(n²)–O(n³)).
- **Forecaster:** same random search, 5 time-ordered folds with a **7-day gap** (D-59): a target lies up to 7 days
  after its issue day, so without the gap the last training rows would carry targets inside the validation fold.
- **Why randomized, not grid:** same quality with far fewer fits when only a few parameters matter.
- Final nowcaster HistGB: learning rate 0.039, 700 iterations, 31 leaves, 50 min samples/leaf, L2 0.28.
- Final forecaster: Ap model lr 0.03/200 iter/7 leaves/200 per leaf/L2 3; max-Kp model lr 0.02/400/7/400/3;
  storm classifier lr 0.05/300/15/100/1 (fixed in advance, not tuned).

### 7.7 Intervals
Two quantile HistGB models (10th, 90th percentile) give an 80% band. Raw coverage was 75.7%; a **conformalized
quantile regression** margin (Romano et al. 2019), estimated only on out-of-fold training/validation years, widens it
to **80.8%** on test. Why: a single number hides uncertainty; the band should really contain 8 in 10 hours.

### 7.8 Adoption rules (the scientific discipline)
Every change had a rule written **before** it ran. Forecaster example (D-68): pooled skill improves, wins in at least
**6 of 9** years, storm Heidke not lower by more than 0.01. Why 6 of 9: a change that does nothing wins each year by
coin flip; 6+ of 9 by luck happens ~25% of the time (5 of 9 ≈ 50%), so lucky passes are rare. Failed ideas stay on
record (CME catalogue, flare reports, intraday updates, log target).

---

## Part 8. Every metric, and why we use it

| Metric | Used for | Why this metric |
|---|---|---|
| **RMSE** | main value metric (Kp, Ap) | squares errors, so **big misses (storms) are punished more**; same units as the target |
| **MAE** | secondary | typical error size, less dominated by a few big misses |
| **R²** | nowcaster | share of variance explained (0.808 = 81%); easy to compare with other work |
| **Storm-hour RMSE** | nowcaster | overall RMSE is dominated by quiet hours (96%); this shows performance when it matters |
| **Error by storm level / bias** | nowcaster | shows *where* the model fails: under-predicts big storms (G3+ bias −0.57 Kp) |
| **Skill vs 27-day mean** | forecaster | `1 − SSE_model / SSE_reference`. Raw RMSE depends on how active the period was (storms make everyone's RMSE big); skill normalises against a strong, simple reference. 0 = no better than "how active has it been lately", 1 = perfect |
| **Heidke skill score (HSS)** | storm warnings | accuracy is useless for rare events (always "no storm" = 86% accurate); HSS measures improvement **over chance** (0 = chance, 1 = perfect) |
| **POD (detection), FAR (false alarms)** | storm warnings | the two sides of the trade-off: catching storms vs crying wolf |
| **F1** | storm warnings | harmonic mean of precision and recall; rubric asks for it; ignores true negatives (good for rare events) |
| **Confusion matrix** | storm warnings | shows the raw counts behind every rate (e.g. day 1: 172 hits, 153 misses, 204 false alarms) |
| **Brier score / skill** | NOAA comparison (D-71) | scores the probability itself, no threshold needed |
| **Interval coverage** | both | does the 80% band really contain 80%? (80.8% nowcaster, 80–81% forecaster) |
| **Diebold–Mariano test** | final test | are two forecasts' errors significantly different? Errors are autocorrelated (storms last days), so a normal t-test is wrong; DM with **Newey–West variance, lag h−1** handles overlapping h-day forecasts |
| **Block bootstrap (30-day blocks)** | final test | confidence interval for the skill gain that keeps autocorrelation inside each block |

**Why Poisson loss for the final forecaster:** Ap is non-negative, very right-skewed, and its variance grows with its
level (like counts). Poisson loss models that shape; it passed the D-68 rule (6/9 years) and was kept.

**Why warning thresholds are not 0.5:** storms are rare, so the model's probability almost never reaches 0.5. We pick
the threshold per lead day that maximises Heidke on training/harness years only (21–31% for the live model).
**Why no resampling (SMOTE etc.):** it distorts the predicted probabilities, which the app shows to users.

---

## Part 9. Results to memorise

**Nowcaster (test 2020–Jan 2026, 52,848 hours)**

| Model | CV | Val | Test RMSE | Test R² | Storm RMSE |
|---|---|---|---|---|---|
| Persistence | – | 0.819 | 0.862 | 0.566 | 1.368 |
| Linear Regression | 0.665 | 0.595 | 0.665 | 0.742 | 1.470 |
| KNN | 0.696 | 0.614 | 0.657 | 0.748 | 1.337 |
| SVR | 0.618 | 0.557 | 0.605 | 0.786 | 1.079 |
| Random Forest | 0.644 | 0.564 | 0.606 | 0.785 | 0.972 |
| **HistGB** | **0.561** | **0.522** | **0.573** | **0.808** | **0.846** |

- Over/under-fitting: HistGB train/CV/val 0.534 / 0.561 / 0.522 → no overfit. **KNN** train ≈ 0 → memorises
  (overfit). **Linear** train 0.689 > val 0.595 → underfits (too simple).
- Learning curve: gap closes with more data; doubling data gains only 0.003 → **information limit**, not capacity.
- Complexity curve: validation flat 31–127 leaves, train keeps falling → bigger trees only memorise.
- May 2024 G5 storm: predicted peak 8.6 vs observed 9; onsets 1–2 h late (block's driver not fully arrived).
- Past Kp as input would only improve validation 0.522 → 0.512, so leaving it out costs almost nothing.
- Live RMSE vs GFZ quick-look ≈ 0.59.

**Forecaster (test 2020-01 → 2026-06, fitted to 2019)**

| | day 1 | day 2 | day 3 | day 7 | skill 1–7 |
|---|---|---|---|---|---|
| **Final (SW + coronal holes)** | **10.67** | 11.80 | **11.73** | **11.95** | **0.122** |
| HistGB indices only (live) | 10.78 | 11.98 | 11.91 | 12.01 | 0.100 |
| NOAA official | 10.89 | **11.73** | 11.90 | – | – |
| 27-day mean | 12.27 | 12.42 | 12.45 | 12.48 | 0 |

- Gain significant on **days 2–5** (DM p ≤ 0.025) = coronal-hole travel time. Bootstrap 95% CI of gain +0.007…+0.050.
- vs NOAA: ahead days 1 and 3, behind day 2, **no significant difference** (p 0.69 / 0.91 / 0.55).
- Storm Heidke days 1–3: 0.40 / 0.26 / 0.25 vs 0.34 / 0.20 / 0.20, with fewer false alarms. Day 1: detects 53%,
  54% of warnings false, F1 0.49.
- Validation harness (2013–2019): coronal holes raised skill 0.131 → 0.160, days 2–4 0.110 → 0.155, **7 of 7** years.

---

## Part 10. Decisions and why (the "why did you…" questions)

| Decision | Why |
|---|---|
| No geomagnetic index as nowcaster input | the nowcast must not wait for magnetometers; ablation showed past Kp adds only 0.010 RMSE |
| Past Kp/Ap **allowed** for the forecaster (D-02) | nobody measures solar wind days ahead; past activity and the 27-day echo are the information left |
| Targets daily Ap and max Kp (D-03) | what NOAA forecasts → direct comparison; 56 three-hourly steps would be noisy |
| Direct models, one per lead day (D-31) | no error compounding |
| Separate storm classifier (D-22, D-48) | value forecasts regress to the mean and almost never cross the storm line |
| Yearly validation harness (D-68) | one 3-year block at solar minimum was too short to judge small changes; 9 years = full solar cycle, 362 storm days |
| Solar wind + 27-day echo + Poisson (D-68) | passed 9 of 9 years: skill 0.089 → 0.112 |
| Coronal holes (D-70) | days 2–7 were weakest; holes send fast wind 2–4 days ahead; passed 7 of 7 |
| CME catalogue rejected (D-67) | starts 2014, added almost nothing, hurt storm Heidke |
| Flare/radio reports, intraday updates, "how yesterday ended" rejected (D-72–74) | each caught more storms only by warning more often (false alarms up) |
| Images: simple measured features, no CNN | ~3,500 training images is too few for a deep network; measured areas are explainable |
| Model locked before the test (D-76) | git history proves the test result could not influence the choice |
| Test scored once, marker file | the one honest measure; a second look would turn the test into validation |
| Shadow mode before going live | live inputs (NOAA real-time, near-real-time images) differ from the training archives; the 27-day echo needs 27 days of our own archive; fallbacks must be seen working |
| Retrain only on degradation, behind a gate (D-12, D-53) | forecasts change only when inputs change, never by silent drift |

---

## Part 11. Leakage: the examiner's favourite topic

How we **prove** there is no leakage:
1. **Causality tests:** delete every row after time t (nowcast) or day D (forecast) → features/forecasts unchanged.
2. **Parity test:** live and training paths give identical features.
3. **Pipeline:** every fitted step is fitted on training rows only.
4. **Time-ordered CV with a gap** (7 days for the forecaster).
5. **Test never used for choices:** the validation harness asserts it never reads 2020+; the model was committed
   (18:42 UTC) before the test ran (20:21 UTC); a marker file blocks a second run.
6. **Placebo test for images:** images moved to random dates → gain disappears (0.137, fails); one day late → gain
   kept (0.154). So the gain comes from the real images on their real dates.
7. **Definitive labels only; yesterday's F10.7 only** (today's is measured late in the day).

**"You refitted the deployed model on the test years. Isn't the test contaminated?"**
No. All reported test scores come from models fitted **only up to 2019**, scored once on 2020–2026. After scoring, the
deployed models were refitted on all data (standard practice: more data, including the 2024 solar maximum, makes the
live model better). The test number measures the **method**; the deployed model's own evidence is the live log, and
the final model's is the shadow log. We say this explicitly in the report.

---

## Part 12. Limitations (say them before the examiner does)
1. **CME storms** are invisible until they arrive → onset day missed. May 2024: both models missed 10 May, warned
   11–13 May.
2. **Extremes under-predicted** (Kp 9 is rare; trees cannot extrapolate beyond training values).
3. **Lead time** of the nowcast ≤ ~1 hour (L1 travel time).
4. **Quiet validation years** 2017–2019; NOAA storm comparison rests on 91 storm days.
5. **Live inputs noisier** than corrected archives → shadow mode checks this.
**Future work:** coronagraph CME detection, sub-hourly solar wind, probabilistic 1–3 h Kp forecasts, journal paper.

---

## Part 13. Question bank (practise these out loud)

**Problem and data**
1. *Why is this a regression and not a classification problem?* Kp is continuous-valued (0–9 in thirds) and the size
   of a storm matters; we add a separate classifier only for the yes/no storm warning.
2. *Why OMNI and not live NOAA data for training?* OMNI is long (1998→), cleaned and time-shifted; NOAA's live feed
   keeps only 7 days. Live NOAA is used for serving, with a parity test.
3. *How many independent samples do you really have?* 245,688 hourly rows but ~81,900 independent Kp labels, because
   each label covers 3 hours.
4. *Why not interpolate missing values?* Half the missing hours are in gaps > 24 h; interpolating would invent data
   (and could invent or erase storms).

**EDA**
5. *What does the 27-day peak in the autocorrelation mean?* The same fast-wind source on the Sun faces Earth again
   after one rotation; shuffled data shows no peak, so it is real time structure.
6. *Why keep outliers?* They are documented storms, the events we most want to predict.

**Methodology**
7. *Why TimeSeriesSplit and not KFold?* KFold shuffles time; the model would validate on the past after training on
   the future, giving an optimistic score.
8. *Why is the forecaster's CV gap 7 days?* A row's target is up to 7 days after its issue day; without the gap,
   training targets would fall inside the validation fold.
9. *Why does KNN have train RMSE ≈ 0?* With distance weighting each training point is its own nearest neighbour →
   memorisation (overfitting).
10. *Why HistGB over Random Forest?* Boosting corrects errors sequentially and was better on every split; it is
    faster, handles NaN, and supports quantile loss.
11. *What is conformal calibration?* Measure, on data the quantile models did not train on, how far observed values
    fall outside the band; widen both sides by that margin so coverage hits the target (75.7% → 80.8%).
12. *Why is feature engineering not in the Pipeline?* See Part 7.3: stateless features, need continuous history,
    rows selected afterwards; causality tested instead.
13. *What would happen if you shuffled?* Leakage: nearly identical neighbouring hours would sit in both train and test,
    so the score would be falsely high.

**Metrics**
14. *Why not accuracy for storms?* Saying "no storm" always is 86% accurate and useless; Heidke measures skill over
    chance.
15. *Why skill instead of RMSE for the forecaster?* RMSE depends on how active the period was; skill compares with a
    strong simple reference on the same days.
16. *What does a Diebold–Mariano p of 0.69 mean?* No evidence that our day-1 errors differ from NOAA's; "level with
    NOAA", not "better".
17. *Why block bootstrap and not ordinary bootstrap?* Errors are autocorrelated (storms last days); resampling single
    days would understate uncertainty.

**Results and models**
18. *Why did LSTM/GRU lose?* ~23k daily samples and few inputs; trees with hand-built features use them better.
19. *Why is the forecast's gain largest on days 2–5?* That is the travel time of fast wind from a coronal hole crossing
    the Sun's centre.
20. *Is the final model better than NOAA?* Level: ahead on days 1 and 3, behind on day 2, no significant difference;
    clearly better than our own index-only model.
21. *Why didn't the CME catalogue help?* It starts in 2014 (short), arrival predictions are uncertain, and it hurt
    storm warnings; it failed its pre-set rule.

**Deployment and engineering**
22. *How do you know live features equal training features?* One shared module + a parity test.
23. *Why does the Hugging Face Space run in the browser?* Hosted Gradio/Docker Spaces need a paid account; stlite runs
    Streamlit on Pyodide; trees exported to numpy because pickles don't load there.
24. *What happens if the solar-wind feed goes down?* The final model falls back to the index-only model (the
    solar-wind model is worse than it with no wind: 0.075 vs 0.089); no images for 2 days → solar-wind model.
25. *How do you stop a bad retrain going live?* Retrain only after two degraded weekly checks; promote only if RMSE on
    the newest 6 unseen months ≤ 1.02 × the current model's.
26. *Why pin exact versions?* A scikit-learn pickle is only guaranteed to load and predict identically under the same
    version; `load_bundle` warns on a mismatch.

**Ethics and honesty**
27. *Did you use the test set more than once?* Nowcaster: once per version (v1–v3), all reported, choices made on
    CV+validation. Forecaster: once (D-52), re-scored once after a bug audit that came before any new number (D-62),
    final model once (D-77). Every look is recorded.
28. *Is this an operational warning service?* No; for official alerts use NOAA SWPC.

---

## Part 14. Who says what (split the viva)
Both of you should be able to answer everything, but agree who leads each area so you do not talk over each other:
data and EDA · features and leakage · models, tuning and metrics · forecaster and coronal holes · deployment and
automation. Practise Part 12 with one person asking and the other answering, then swap.
