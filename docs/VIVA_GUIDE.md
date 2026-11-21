# Tormenta: the viva guide (from zero)

A beginner-friendly companion to [VIVA_PREP.md](VIVA_PREP.md). It assumes you know programming and basic ML but **no
physics**. Each chapter has three parts: **Plain explanation**, **What we did**, **If they ask**.
Exact numbers and reasons live in [DECISIONS.md](../DECISIONS.md) (D-numbers) and [PROJECT_EXP.md](../PROJECT_EXP.md).

| # | Chapter | Status |
|---|---|---|
| 0 | The map | written |
| 1 | The physics from zero | written |
| 2 | Data sources | next |
| 3 | Data handling, preprocessing, EDA | |
| 4 | Feature engineering, extraction, scaling | |
| 5 | Splitting and leakage | |
| 6 | How forecasting works + baselines | |
| 7 | Models and the selected one | |
| 8 | Metrics, with toy examples | |
| 9 | Results and graphs | |
| 10 | The UI and live calculations | |
| 11 | Decisions and limitations | |
| 12 | Viva drill | |

---

## Chapter 0. The map

### Plain explanation
Tormenta predicts **how disturbed Earth's magnetic field will be**, because the Sun sometimes hits it hard. It does
two jobs, with two separate models:

| | **Nowcaster** | **Forecaster** |
|---|---|---|
| Question | What is the disturbance **right now**? | What will it be on each of the **next 7 days**? |
| Output | Kp for the current hour (+ the next hour) | Daily Ap and highest Kp for days 1 to 7, plus a storm probability |
| Looks at | Solar wind measured by a spacecraft about an hour upstream | Past activity, solar wind, and a daily picture of the Sun |
| Data from | NASA OMNI (1998 on) | GFZ (1947 on) plus the extras |
| Is it really "forecasting"? | Barely: it estimates the present from an early warning signal | Yes: it predicts days ahead |

### What we did (the 60-second answer)
> Geomagnetic storms can damage power grids, satellites and GPS. Their strength is measured by the Kp index. We built
> Tormenta with two parts: a nowcaster that estimates the current Kp from the solar wind, and a 7-day forecaster for
> daily Ap and Kp with a storm warning. The final forecaster uses past activity, solar wind and coronal holes from one
> solar image per day. It beats our simpler model and is level with NOAA's official forecast. Everything runs live,
> and every forecast is logged and scored.

### If they ask
- **Why two models?** They answer different questions on different time scales with different inputs. The nowcaster
  has only about 1 hour of lead time; the forecaster has days but far less information per day.
- **Which one is the main contribution?** The 7-day forecaster, especially the coronal-hole features.

---

## Chapter 1. The physics from zero

You need five ideas. Everything else is detail.

### 1.1 The Sun blows a wind
### Plain explanation
The Sun constantly throws off charged particles. This is the **solar wind**: about 300 to 800 km/s, and it carries a
weak magnetic field with it, called the **IMF** (interplanetary magnetic field). Think of it as a river of charged
gas flowing past Earth.

### 1.2 Earth has a magnetic shield
Earth's magnetic field forms a bubble around the planet, the **magnetosphere**. Most of the wind flows around it.

### 1.3 The key switch: Bz
The IMF has components. The one that matters most is **Bz**, the north-south component.
- **Bz north (positive):** the wind's field and Earth's field point the same way, so they press together and almost
  nothing gets in.
- **Bz south (negative):** the fields point opposite ways and **connect** (called *reconnection*). Energy pours into
  Earth's magnetic bubble.

Analogy: a door that is closed when Bz is north and open when Bz is south. How much comes through depends on how
fast the wind is and how strongly south it points. The best simple summary is **speed × southward Bz**.

A slow wind with strongly southward Bz can cause a storm. A fast wind with northward Bz may cause almost nothing.

### 1.4 What the energy does, and how we measure it
The energy shakes Earth's magnetic field. Magnetometers on the ground record the shaking, and scientists boil it
down to indices:

| Index | Meaning | Scale | How often |
|---|---|---|---|
| **Kp** | planetary K index: how disturbed the field is | 0 to 9 (in thirds: 4−, 4, 4+, 5−...) | every 3 hours (8 per day) |
| **ap** | the same thing on a linear scale, so averages make sense | 0 to 400 | every 3 hours |
| **Ap** | the daily average of the 8 ap values | 0 to 400 | once per day |

A **storm** in our project is a day whose highest Kp reaches **5−** or more (NOAA's "G1" level, the smallest
storm). Storms are rare: about **14% of days**. That rarity is why we need special handling later (class imbalance,
chapter 7).

### 1.5 What causes storms (this is what we try to predict)

| Cause | What it is | When it hits Earth | Can we see it coming? |
|---|---|---|---|
| **CME** (coronal mass ejection) | a huge cloud of plasma thrown out in an eruption | 1 to 4 days after the eruption | **No.** It leaves no trace in our inputs until it arrives. This is our main limitation |
| **Coronal hole** | a dark patch on the Sun (in extreme-UV images) where fast wind escapes | 2 to 4 days after it faces Earth | **Yes, from a daily solar image.** This is our biggest gain |
| **27-day rotation** | the Sun spins once in about 27 days, so the same hole faces Earth again | repeats every 27 days | **Yes.** Activity 27 days ago predicts activity today (the "27-day echo") |
| **Season** | more storms near the equinoxes (March, September) because of how Earth's tilt lines up with the wind | yearly | Yes, from the date |
| **11-year solar cycle** | the Sun's activity rises and falls over about 11 years | slow | Yes, from **F10.7** (the Sun's radio brightness, a measure of how active it is) |

### Why this decides our whole approach
- Anything **regular** (27-day echo, season, solar cycle) is learnable from the past.
- Anything visible **ahead of time** (coronal holes in images) can be added as an input.
- Anything **sudden and invisible** (a CME) is where every method fails, including NOAA's. We say so openly.

### Words to know before moving on
**solar wind**, **IMF**, **Bz**, **magnetosphere**, **reconnection**, **Kp / ap / Ap**, **storm (Kp >= 5-)**,
**CME**, **coronal hole**, **27-day rotation**, **F10.7**, **L1 point** (the spot 1.5 million km towards the Sun
where spacecraft measure the wind; the wind takes about an hour to travel from there to Earth, which is the
nowcaster's warning time).

### If they ask
- **Why does southward Bz matter?** Opposite fields connect and let solar-wind energy into the magnetosphere;
  same-direction fields do not.
- **What is Kp?** A 0 to 9 measure of how disturbed Earth's field is in a 3-hour block, derived from ground
  magnetometers. 5 or more is a storm.
- **Why can't you predict CMEs?** They are sudden eruptions; our inputs only show them when they reach the
  spacecraft near Earth, about an hour before impact. Predicting them needs images of the eruption itself (we tested
  NASA's CME catalogue and it did not help: D-67).
- **Why 27 days?** The Sun rotates in about 27 days as seen from Earth, so a coronal hole that was facing Earth
  comes round again.

*Chapter 2 (data sources) comes next.*
