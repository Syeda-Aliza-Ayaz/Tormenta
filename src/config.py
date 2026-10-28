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
# 3-day products: features need >= 24 h of history (24 h trailing speed mean)
SWPC_MAG = SWPC_BASE + "/products/solar-wind/mag-3-day.json"
SWPC_MAG_FALLBACK = SWPC_BASE + "/products/solar-wind/mag-7-day.json"
SWPC_PLASMA = SWPC_BASE + "/products/solar-wind/plasma-3-day.json"
SWPC_PLASMA_FALLBACK = SWPC_BASE + "/products/solar-wind/plasma-7-day.json"
SWPC_KP = SWPC_BASE + "/products/noaa-planetary-k-index.json"
SWPC_F107 = SWPC_BASE + "/products/summary/10cm-flux.json"

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
F107_TRAILING_DAYS = 81
F107_SPIKE_WINDOW_DAYS = 27    # flare-spike check against the trailing median
F107_SPIKE_RATIO = 2.0         # value > 2× trailing median → treated as flare-contaminated
MIN_HISTORY_HOURS = 24         # live window needed for the longest trailing window (SWPC 3-day feed)

# ── Split & training ─────────────────────────────────────────────────────────
TRAIN_YEARS = (1998, 2016)
VAL_YEARS = (2017, 2019)
TEST_START_YEAR = 2020
CV_SPLITS = 5
SUBSAMPLE_STRIDE = 9         # strided subsample for KNN/SVR (~15–20k rows)
RF_TUNE_STRIDE = 3           # Random Forest tuned on every 3rd hour, refit on all
RANDOM_STATE = 42
QUANTILES = (0.1, 0.9)
N_JOBS = 4                   # 7.4 GB RAM laptop: keep parallel workers modest
SAMPLE_WEIGHT = lambda kp: 1 + kp / 3   # storm-weighting ablation

REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
METRICS_DIR = REPORTS_DIR / "metrics"

# ── Slow loop ────────────────────────────────────────────────────────────────
GATE_HOLDOUT_MONTHS = 6
GATE_TOLERANCE = 1.02        # promote if candidate RMSE <= current RMSE × 1.02
