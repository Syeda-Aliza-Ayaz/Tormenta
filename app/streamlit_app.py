"""Tormenta dashboard: 7-day geomagnetic forecast, live Kp nowcast, replays, scorecard and method.

Local:  .venv\\Scripts\\streamlit run app\\streamlit_app.py
Cloud:  Streamlit Community Cloud, main file app/streamlit_app.py, Python 3.12, requirements.txt at repo root.

Pages and theme live in the URL (?page=forecast&theme=light), so every view has its own link. The interface itself
is in app/tormenta_ui; images are served from app/static (server.enableStaticServing in .streamlit/config.toml).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

ICON = Path(__file__).parent / "static" / "logo.svg"          # absent in the in-browser build
st.set_page_config(page_title="Tormenta · Geomagnetic forecast", page_icon=str(ICON) if ICON.exists() else None,
                   layout="wide", initial_sidebar_state="collapsed")

from tormenta_ui import pages_live, pages_models  # noqa: E402
from tormenta_ui.theme import CLIENT_JS, altair_ready, css  # noqa: E402

PAGES = {"overview": pages_live.overview, "forecast": pages_live.forecast, "explore": pages_live.explore,
         "scorecard": pages_models.scorecard, "nowcast": pages_models.nowcast_page, "method": pages_models.method}

page = st.query_params.get("page", "overview").lower()
theme = st.query_params.get("theme", "dark").lower()
page = page if page in PAGES else "overview"
theme = theme if theme in ("dark", "light") else "dark"

altair_ready()
st.markdown(css(theme), unsafe_allow_html=True)
PAGES[page](theme, pd.Timestamp.now("UTC"))
if hasattr(st, "iframe"):                       # live clock and cursor ring; a hidden helper frame
    st.iframe(CLIENT_JS, height=1)
else:                                            # older Streamlit (in-browser build)
    import streamlit.components.v1 as components
    components.html(CLIENT_JS, height=0)
