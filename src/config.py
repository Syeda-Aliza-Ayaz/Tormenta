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
SWPC_MAG = SWPC_BASE + "/products/solar-wind/mag-1-day.json"
SWPC_MAG_FALLBACK = SWPC_BASE + "/products/solar-wind/mag-3-day.json"
SWPC_PLASMA = SWPC_BASE + "/products/solar-wind/plasma-1-day.json"
SWPC_PLASMA_FALLBACK = SWPC_BASE + "/products/solar-wind/plasma-3-day.json"
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

# Storm-level bins for error-by-level evaluation: 0–3, 4, 5, 6, 7+
KP_BINS = [0, 4, 5, 6, 7, 9.01]
KP_BIN_LABELS = ["0-3", "4", "5", "6", "7+"]

# ── Features ─────────────────────────────────────────────────────────────────
LAG_HOURS = [1, 3, 6, 9]
ROLL_WINDOWS = [3, 6, 9]
F107_TRAILING_DAYS = 81
MIN_HISTORY_HOURS = 21       # live window needed for lags + rolling

# ── Split & training ─────────────────────────────────────────────────────────
TRAIN_YEARS = (1998, 2016)
VAL_YEARS = (2017, 2019)
TEST_START_YEAR = 2020
CV_SPLITS = 5
SUBSAMPLE_STRIDE = 9         # strided subsample for KNN/SVR (~15–20k rows)
RANDOM_STATE = 42
QUANTILES = (0.1, 0.9)

# ── Slow loop ────────────────────────────────────────────────────────────────
GATE_HOLDOUT_MONTHS = 6
GATE_TOLERANCE = 1.02        # promote if candidate RMSE <= current RMSE × 1.02
