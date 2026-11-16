"""Final refit of the live models on the production window (DECISIONS D-63).

Each live model is refitted on every definitive day up to config.PRODUCTION_END with the settings it was selected
with; nothing is re-tuned. The storm thresholds and the 80% ranges stay as calibrated, because they come from
out-of-sample errors (fits ≤ 2007 / ≤ 2016). A model is refitted only if its bundle exists, i.e. it passed its
validation rule (D-31).

    python -m src.forecast.refit
"""
import joblib

from src.forecast import arima, gbm, storm


def main() -> dict:
    from src.daily import load_daily
    from src.issue import production_window

    rows = production_window(load_daily())
    out = {}

    meta = {k: v for k, v in joblib.load(gbm.BUNDLE).items() if k not in ("model", "sklearn_version", "refit")}
    model = gbm.HistGBDirect(meta["params"], log_ap=meta["log_ap"]).fit(rows)
    model.save(**meta, refit="D-63")
    out["histgb"] = model.trained_until_

    meta = {k: v for k, v in joblib.load(storm.BUNDLE).items() if k not in ("model", "sklearn_version", "refit")}
    warn = storm.StormClassifier().fit(rows)
    warn.thresholds_ = meta["thresholds"]
    warn.save(**meta, refit="D-63")
    out["storm_warning"] = warn.trained_until_

    for m in arima.default_models(arima.load_settings()):
        path = arima.BUNDLE_DIR / f"{m.name}.joblib"
        if not path.exists():
            continue
        meta = {k: v for k, v in joblib.load(path).items() if k not in ("model", "refit")}
        m.fit(rows).save(path, **meta, refit="D-63")
        out[m.name] = m.trained_until_

    for name, until in out.items():
        print(f"refitted {name}: trained until {until}")
    return out


if __name__ == "__main__":
    from src.forecast import refit as _module      # pickle the classes under their modules, not __main__ (D-32)
    _module.main()
