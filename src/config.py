"""Central configuration for Tormenta. Every path, column name and constant lives here."""
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"

OMNI_LST = RAW_DIR / "omni2_UuPWjVIAYC.lst"     # Phase 1 seed (OMNIWeb subset)
OMNI_FMT = RAW_DIR / "omni2_UuPWjVIAYC.fmt"
GFZ_TXT = RAW_DIR / "Kp_ap_Ap_SN_F107_since_1932.txt"
PROCESSED_CSV = PROCESSED_DIR / "tormenta_hourly.csv"
F107_HISTORY = DATA_DIR / "f107_history.csv"     # committed; refreshed by slow loop

CURRENT_MODEL = MODELS_DIR / "current.joblib"
METRICS_HISTORY = MODELS_DIR / "metrics_history.json"

# ── Sources ──────────────────────────────────────────────────────────────────
OMNI_SPDF_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{year}.dat"
GFZ_URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"

SWPC_BASE = "https://services.swpc.noaa.gov"
# Checked 2026-10-30: the old products/solar-wind/{mag,plasma}-N-day.json feeds are gone (404).
# Propagated solar wind: 7 days of 1-min IMF (GSM) + plasma from the active L1 spacecraft,
# already time-shifted to Earth (~50–75 min), like OMNI's bow-shock shift.
SWPC_SOLAR_WIND = SWPC_BASE + "/products/geospace/propagated-solar-wind.json"
SWPC_KP = SWPC_BASE + "/products/noaa-planetary-k-index.json"        # estimated Kp, comparison only
GFZ_NOWCAST_URL = "https://kp.gfz.de/app/files/Kp_ap_nowcast.txt"   # GFZ quick-look Kp (same producer as labels)
SWPC_F107 = SWPC_BASE + "/products/10cm-flux-30-day.json"           # observed Penticton flux, daily
LIVE_MIN_MINUTES = 20        # an hour needs >= 20 one-minute samples, else that column is NaN
REQUEST_TIMEOUT = 60         # seconds (slow connections)

# ── OMNI subset (.lst) columns, in .fmt order ────────────────────────────────
OMNI_LST_COLUMNS = [
    "year", "doy", "hour",
    "b_scalar", "bx", "by_gsm", "bz_gsm",
    "temperature", "density", "speed",
    "omni_pressure", "omni_efield", "omni_beta", "omni_mach_a", "omni_mach_ms",
    "sunspot_r", "f107",
]

# Fill sentinels per column (OMNI2 docs; verified against the .lst maxima)
OMNI_FILL = {
    "b_scalar": 999.9, "bx": 999.9, "by_gsm": 999.9, "bz_gsm": 999.9,
    "temperature": 9999999.0, "density": 999.9, "speed": 9999.0,
    "omni_pressure": 99.99, "omni_efield": 999.99, "omni_beta": 999.99,
    "omni_mach_a": 999.9, "omni_mach_ms": 99.9,
    "sunspot_r": 999, "f107": 999.9,
}

# Raw inputs fed to features.py — must be reconstructable from SWPC live feeds.
# F10.7 comes from GFZ's observed (Penticton) flux, the same quantity SWPC serves live,
# not OMNI's f107 column.
RAW_FEATURES = ["b_scalar", "bx", "by_gsm", "bz_gsm", "temperature", "density", "speed", "f107_obs"]

# OMNI precomputed columns: kept only for the one-off derived-field check, never as features
OMNI_CHECK_ONLY = ["omni_pressure", "omni_efield", "omni_beta", "omni_mach_a", "omni_mach_ms"]

# ── Target ───────────────────────────────────────────────────────────────────
TARGET = "kp"
GFZ_DEFINITIVE = 2           # GFZ 'D' flag value for definitive Kp
KP_BLOCK_HOURS = 3

# Storm-level bins for error-by-level evaluation: 0–3, 4, 5 (G1), 6 (G2), 7+ (G3–G5).
# Kp comes in thirds (4- = 3.667, 5- = 4.667); NOAA rounds to the nearest integer, so
# edges sit at the half-integers.
KP_BINS = [0, 3.5, 4.5, 5.5, 6.5, 9.01]
KP_BIN_LABELS = ["0-3", "4", "5 (G1)", "6 (G2)", "7+ (G3-G5)"]
STORM_THRESHOLD = 4.5        # Kp >= 5- is a geomagnetic storm (NOAA G1+)

# Solar-wind columns of the hourly frame passed to features.build_features (F10.7 goes in separately, daily)
SW_FEATURES = [c for c in RAW_FEATURES if c != "f107_obs"]

# ── Features ─────────────────────────────────────────────────────────────────
LAG_HOURS = [1, 3, 6, 9]
LAG_COLUMNS = ["bz_gsm", "speed", "density", "vbs"]
ROLL_WINDOWS = [3, 6, 9]
LONG_SPEED_WINDOWS = [12, 24]  # EDA: speed keeps ~a day of memory
LONG_NEWELL_WINDOWS = [12, 24] # v2: coupling memory beyond 9 h
BLOCK_SO_FAR_MEAN = ["newell", "vbs"]  # v2: running stats since the current Kp block started
# v3 storm memory: exponentially decaying mean of energy input over a FIXED trailing window,
# so the live path (SWPC 3-day feed) computes exactly what training computed
USE_MEMORY_FEATURES = False    # 05_final_round: rejected (CV better, validation worse)
MEMORY_COLUMNS = ["newell", "vbs"]
MEMORY_HALFLIVES = [6, 24]     # hours
MEMORY_WINDOW_HOURS = 48
F107_TRAILING_DAYS = 81
F107_SPIKE_WINDOW_DAYS = 27    # flare-spike check against the trailing median
F107_SPIKE_RATIO = 2.0         # value > 2× trailing median → treated as flare-contaminated
MIN_HISTORY_HOURS = 48         # live warm-up: hours dropped before the first prediction (>= longest window; feed has 7 days)

# ── Split & training ─────────────────────────────────────────────────────────
TRAIN_YEARS = (1998, 2016)
VAL_YEARS = (2017, 2019)
TEST_START_YEAR = 2020
CV_SPLITS = 5
SUBSAMPLE_STRIDE = 9         # strided subsample for KNN/SVR (~15–20k rows)
RF_TUNE_STRIDE = 3           # Random Forest tuned on every 3rd hour, refit on all
HISTGB_N_ITER = 20           # v2: wider search (v1 used 8)
ENSEMBLE_MEMBERS = ["HistGB", "Random Forest", "SVR"]   # equal-weight average, no weights fitted
RANDOM_STATE = 42
QUANTILES = (0.1, 0.9)
N_JOBS = 4                   # 7.4 GB RAM laptop: keep parallel workers modest
SAMPLE_WEIGHT = lambda kp: 1 + kp / 3   # storm-weighting ablation
# v3 physics constraints for HistGB: Kp may only rise (+1) / fall (-1) as these rise
USE_MONOTONIC = False        # 05_final_round: rejected (CV and validation worse)
MONOTONIC_INCREASING = ["speed", "vbs", "newell", "newell_mean3h", "newell_mean6h", "newell_mean9h",
                        "newell_mean12h", "newell_mean24h", "newell_block_mean", "newell_block_max",
                        "vbs_block_mean", "newell_decay6h", "newell_decay24h", "vbs_decay6h", "vbs_decay24h"]
MONOTONIC_DECREASING = ["bz_gsm", "bz_min3h", "bz_block_min"]
CONFORMAL_SKIP_FOLDS = 1     # first CV fold trains on only ~3 years → too pessimistic for calibration

REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
METRICS_DIR = REPORTS_DIR / "metrics"

# ── Slow loop ────────────────────────────────────────────────────────────────
GATE_HOLDOUT_MONTHS = 6
GATE_TOLERANCE = 1.02        # promote if candidate RMSE <= current RMSE × 1.02
