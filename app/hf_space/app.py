"""Tormenta Gradio demo (local). Hosting a Gradio Space now needs HF PRO, so Hugging Face gets the free
model repo + static landing page instead (sync_hf.py); this app runs on a laptop, e.g. for the viva.

    .venv\\Scripts\\python app\\hf_space\\app.py   →  http://127.0.0.1:7860

ROOT is found by searching upwards, so the file also works if copied next to src/ (e.g. a PRO Space).
"""
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src" / "predict.py").exists())
sys.path.insert(0, str(ROOT))

import gradio as gr  # noqa: E402
import requests  # noqa: E402

from src import evaluate as ev  # noqa: E402
from src.ingest import fetch_live  # noqa: E402
from src.predict import INPUT_LIMITS, load_bundle, nowcast, predict_steady, validate_inputs  # noqa: E402

BUNDLE = load_bundle()
DEFAULTS = {"b_scalar": 5.0, "bx": 1.0, "by_gsm": 2.0, "bz_gsm": 0.0, "speed": 400.0, "density": 5.0,
            "temperature": 100000.0, "f107": 120.0}
ASSUMPTION = "Inputs are assumed to have held steady for the past 3 days (the model also uses lags and 24-h averages)."


def predict_manual(*args):
    values, errors = validate_inputs(dict(zip(INPUT_LIMITS, args)))
    if errors:
        raise gr.Error(" ".join(errors.values()))
    out = predict_steady(BUNDLE, values)
    return (f"## Kp {out['kp_pred']:.1f}\n80% range {out['kp_lo']:.1f}–{out['kp_hi']:.1f} · "
            f"level **{out['level']}**\n\n_{ASSUMPTION}_")


def predict_live():
    try:
        pred, hourly = nowcast(BUNDLE)
        live = ev.attach_block_kp(pred, fetch_live.fetch_gfz_nowcast(), "kp_gfz")
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        raise gr.Error(f"Could not get live data from NOAA SWPC ({type(exc).__name__}). Try again in a minute.")
    now = live[~live["ahead"]].iloc[-1]
    text = (f"## Kp now: {now['kp_pred']:.1f}\n{now.name:%Y-%m-%d %H:00} UTC · "
            f"80% range {now['kp_lo']:.1f}–{now['kp_hi']:.1f}")
    ahead = live[live["ahead"]]
    if len(ahead):
        a = ahead.iloc[-1]
        text += f"\n\nNext hour ({a.name:%H:00} UTC): Kp {a['kp_pred']:.1f} ({a['kp_lo']:.1f}–{a['kp_hi']:.1f})"
    latest = hourly.dropna().iloc[-1]
    text += (f"\n\nSolar wind: {latest['speed']:.0f} km/s, Bz {latest['bz_gsm']:+.1f} nT, "
             f"|B| {latest['b_scalar']:.1f} nT, density {latest['density']:.1f} cm⁻³")
    return text, ev.plot_live(live)


with gr.Blocks(title="Tormenta Kp Nowcast") as demo:
    gr.Markdown("# Tormenta: geomagnetic Kp nowcast\nPredicts the Kp index (0–9) from solar-wind conditions. "
                f"Model `{BUNDLE['version']}` · test RMSE 0.57 Kp · "
                "[code](https://github.com/Syeda-Aliza-Ayaz/Tormenta)")
    with gr.Tab("Live"):
        live_btn = gr.Button("Get live nowcast from NOAA SWPC", variant="primary")
        live_text = gr.Markdown()
        live_plot = gr.Plot()
        live_btn.click(predict_live, outputs=[live_text, live_plot])
    with gr.Tab("Try your own inputs"):
        inputs = [gr.Number(value=DEFAULTS[name], label=label, minimum=lo, maximum=hi)
                  for name, (lo, hi, label) in INPUT_LIMITS.items()]
        btn = gr.Button("Predict Kp", variant="primary")
        out = gr.Markdown()
        btn.click(predict_manual, inputs=inputs, outputs=out)
        gr.Examples([[5, 1, 2, 1, 380, 5, 80000, 120], [20, 3, 5, -15, 600, 10, 200000, 150],
                     [40, 5, 10, -35, 800, 20, 500000, 180]], inputs=inputs, label="Quiet · moderate · strong storm")

if __name__ == "__main__":
    demo.launch()
