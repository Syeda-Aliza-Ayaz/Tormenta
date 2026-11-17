"""Smoke test of the dashboard: each page that needs no network renders without an exception, in both themes."""
import pytest
from streamlit.testing.v1 import AppTest

from src import config

APP = str(config.ROOT / "app" / "streamlit_app.py")


@pytest.mark.parametrize("page", ["forecast", "explore", "scorecard", "method"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_page_renders(page, theme):
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["page"] = page
    at.query_params["theme"] = theme
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("TORMENTA" in m.value for m in at.markdown)          # the hero and navigation were drawn
