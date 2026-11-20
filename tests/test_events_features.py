"""D-74: event reports parse, and an issue day's warning signs use only that day and the two before it."""
import numpy as np
import pandas as pd
import pytest

from src.forecast.experiments import events_features as E

NEW = """:Product: 20150621events.txt
:Date: 2015 06 21
#Event    Begin    Max       End  Obs  Q  Type  Loc/Frq   Particulars       Reg#
5420 +     0102   0142      0200  G15  5   XRA  1-8A      M2.0    3.2E-02   2371
5420 +     0107   0140      0434  LEA  1   FLA  N12E13    1N      UMB       2371
5440       0000   ////      0930  LEA  C   RSP  075-180   IV/1
5450       0206   0236      0302  G15  5   XRA  1-8A      M6.5              2372
5451 +     0210   0211      0230  LEA  1   FLA  S40W70    SF                2372
5460       0300   ////      0320  PAL  C   RSP  025-180   II/2              2371
"""
OLD = """Prepared by the U.S. Dept. of Commerce, NOAA, Space Environment Center
EDITED EVENTS for 1996 Jul 31
Event     Begin    Max       End  Obs  Q  Type  Loc/Frq   Particulars       Reg#
3000 +     0829   0835      0840  GO9  5   XRA  1-8A      B2.0    1.18E-04  7981
3000 +     0836  U0836     A0857  SVI  3   FLA  S10E34    SF                7981
"""


def test_parse_new_layout():
    d = E.parse_day(NEW)
    assert d["date"] == pd.Timestamp("2015-06-21")
    assert d["xray_max"] == pytest.approx(6.5e-5)                 # largest flare overall
    assert d["xray_central"] == pytest.approx(2.0e-5)             # only region 2371 sits near the centre
    assert (d["type2"], d["type4"]) == (1, 1)


def test_parse_old_layout():
    d = E.parse_day(OLD)
    assert d["date"] == pd.Timestamp("1996-07-31")
    assert d["xray_max"] == pytest.approx(2.0e-7)
    assert np.isnan(d["xray_central"])                             # E34 is beyond 30 degrees


def test_window_uses_only_past_three_days(monkeypatch):
    days = pd.date_range("2015-06-01", periods=20, freq="D")
    ev = pd.DataFrame({"xray_max": 1e-6, "xray_central": 1e-6, "type2": 0, "type4": 0, "n_reports": 1}, index=days)
    pr = pd.Series(10.0, index=days)
    monkeypatch.setattr(E, "daily_events", lambda years: ev)
    monkeypatch.setattr(E, "daily_protons", lambda years: pr)
    before = E.event_features(days)
    ev.loc["2015-06-15":, ["xray_max", "xray_central"]] = 1e-3
    ev.loc["2015-06-15":, "type2"] = 9
    pr.loc["2015-06-15":] = 1e6
    after = E.event_features(days)
    pd.testing.assert_frame_equal(before.loc[:"2015-06-14"], after.loc[:"2015-06-14"])
    assert after.loc["2015-06-17", "ev_type2"] == 27 and after.loc["2015-06-18", "ev_type2"] == 27
