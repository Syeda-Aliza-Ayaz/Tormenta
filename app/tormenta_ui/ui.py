"""HTML building blocks: the night-sky hero with its scenes, the icon set, cards, tables and small charts.

Everything returns a single-line HTML string for st.markdown(..., unsafe_allow_html=True); one line keeps Markdown
from treating indented markup as code.
"""
import html as _html
import math

import streamlit as st

from .data import level_of
from .theme import TOKENS, fg_on, static

PAGES = ["Overview", "Forecast", "Explore", "Scorecard", "Nowcast", "Method"]


def esc(s) -> str:
    return _html.escape(str(s), quote=True)


def one_line(markup: str) -> str:
    return " ".join(line.strip() for line in markup.splitlines() if line.strip())


def show(markup: str, slot=None):
    (slot or st).markdown(one_line(markup), unsafe_allow_html=True)


def href(page: str, theme: str) -> str:
    return f"?page={page.lower()}&amp;theme={theme}"


# ── Icons (stroke icons drawn on a 24/32 grid; colour from currentColor) ─────
_FIELD = ('<circle cx="16" cy="16" r="4.5"></circle><path d="M16 11.5C9 4 3 9 6 16s10 4.5 10 4.5"></path>'
          '<path d="M16 11.5C23 4 29 9 26 16s-10 4.5-10 4.5"></path>')
ICONS = {
    "quiet": f'<svg width="{{s}}" height="{{s}}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">{_FIELD}</svg>',
    "unsettled": f'<svg width="{{s}}" height="{{s}}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">{_FIELD}<path d="M3 26c2-1.5 4-1.5 6 0s4 1.5 6 0"></path></svg>',
    "storm": '<svg width="{s}" height="{s}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13" cy="17" r="4"></circle><path d="M13 13C7 6.5 2 11 4.5 17S13 21 13 21"></path><path d="M13 13c3-3 6-4 8-3"></path><path d="M24 3l-4 8h5l-4 8"></path></svg>',
    "wind": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 8h11a3 3 0 1 0-3-3"></path><path d="M3 12h16a3 3 0 1 1-3 3"></path><path d="M3 16h7"></path></svg>',
    "bz": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 5l2.5 7h-5z"></path><path d="M9.5 12L12 19l2.5-7"></path></svg>',
    "density": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="6" cy="7" r="1.6"></circle><circle cx="13" cy="5" r="1.6"></circle><circle cx="18" cy="10" r="1.6"></circle><circle cx="9" cy="13" r="1.6"></circle><circle cx="15" cy="16" r="1.6"></circle><circle cx="6" cy="19" r="1.6"></circle></svg>',
    "field": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3v8a6 6 0 0 0 12 0V3"></path><path d="M6 7h4M14 7h4"></path></svg>',
    "sun": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M5 19l1.4-1.4M17.6 6.4L19 5"></path></svg>',
    "aurora": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 20h18"></path><path d="M5 17V9M9 17V5M13 17V7M17 17V4M21 17v-6"></path></svg>',
    "bolt": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2L4 14h7l-1 8 9-12h-7z"></path></svg>',
    "warn": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l9.5 17h-19z"></path><path d="M12 10v4.5"></path><path d="M12 17.5v.5"></path></svg>',
    "logo": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="#9CC9FF" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M2 12c3-6 17-6 20 0"></path><path d="M2 12c3 6 17 6 20 0"></path></svg>',
    "moon": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"></path></svg>',
    "sunny": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.5"></circle><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"></path></svg>',
}


def icon(name: str, size: int = 18) -> str:
    return ICONS[name].replace("{s}", str(size))


def condition_icon(kp: float, size: int = 28) -> str:
    return icon("quiet" if kp < 3 else ("unsettled" if kp < 4.5 else "storm"), size)


# ── Hero scenes ──────────────────────────────────────────────────────────────
def _rng(seed):
    state = [seed]

    def rnd():
        state[0] = (state[0] * 16807) % 2147483647
        return state[0] / 2147483647
    return rnd


def _stars(n, height, seed=11):
    rnd = _rng(seed)
    return "".join(f'<circle class="sh-star" cx="{rnd() * 1440:.1f}" cy="{rnd() * height:.1f}" r="{0.5 + rnd() * 1.1:.2f}" '
                   f'fill="#DCE6F5" style="animation-delay:{rnd() * 4:.2f}s"></circle>' for _ in range(n))


_DEFS = """<defs>
<linearGradient id="sh-green" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#5CF2A6" stop-opacity="0.95"></stop><stop offset="0.35" stop-color="#3DDC97" stop-opacity="0.55"></stop><stop offset="1" stop-color="#3DDC97" stop-opacity="0"></stop></linearGradient>
<linearGradient id="sh-red" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#FF5C7A" stop-opacity="0.7"></stop><stop offset="1" stop-color="#FF5C7A" stop-opacity="0"></stop></linearGradient>
<radialGradient id="sh-sun" cx="0.42" cy="0.45" r="0.6"><stop offset="0" stop-color="#FFF6E0"></stop><stop offset="0.55" stop-color="#FFC266"></stop><stop offset="0.88" stop-color="#F28C28"></stop><stop offset="1" stop-color="#C9461A"></stop></radialGradient>
<radialGradient id="sh-neb-g" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff" stop-opacity="1"></stop><stop offset="1" stop-color="#fff" stop-opacity="0"></stop></radialGradient>
<mask id="sh-neb-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1440" height="600"><ellipse cx="1080" cy="200" rx="420" ry="230" fill="url(#sh-neb-g)"></ellipse><ellipse cx="820" cy="120" rx="260" ry="150" fill="url(#sh-neb-g)" opacity="0.7"></ellipse></mask>
<clipPath id="sh-sun-clip"><circle cx="1300" cy="250" r="280"></circle></clipPath>
<filter id="sh-soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6"></feGaussianBlur></filter>
<filter id="sh-glow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="10"></feGaussianBlur></filter>
<filter id="sh-big" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="28"></feGaussianBlur></filter>
<filter id="sh-halo" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="4"></feGaussianBlur></filter>
<filter id="sh-gran" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="3"></feTurbulence><feColorMatrix type="matrix" values="0 0 0 0 0.55  0 0 0 0 0.25  0 0 0 0 0.05  0 0 0 0.9 -0.35"></feColorMatrix></filter>
<filter id="sh-nebA" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.009" numOctaves="5" seed="12"></feTurbulence><feColorMatrix type="matrix" values="0 0 0 0 0.18  0 0 0 0 0.70  0 0 0 0 0.66  0 0 0 1.9 -0.78"></feColorMatrix></filter>
<filter id="sh-nebB" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.008 0.006" numOctaves="5" seed="27"></feTurbulence><feColorMatrix type="matrix" values="0 0 0 0 0.88  0 0 0 0 0.48  0 0 0 0 0.37  0 0 0 2.0 -0.95"></feColorMatrix></filter>
<filter id="sh-dustcloud" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.004 0.012" numOctaves="4" seed="5"></feTurbulence><feColorMatrix type="matrix" values="0 0 0 0 0.62  0 0 0 0 0.57  0 0 0 0 0.52  0 0 0 1.4 -0.72"></feColorMatrix></filter>
</defs>"""


def _aurora(level: str, cy: float, r: float) -> str:
    height, opacity, red = {"quiet": (62, 0.46, False), "unsettled": (110, 0.6, False),
                            "storm": (190, 0.9, True)}.get(level, (50, 0.34, False))
    green, reds = [], []
    for i in range(48):
        x = 140 + i * 24
        base = cy - math.sqrt(r * r - (x + 11 - 720) ** 2) + 4
        h = height * (0.55 + 0.3 * math.sin(i * 0.5) + 0.15 * math.sin(i * 1.7 + 1))
        d = -(i % 9) * 0.8
        green.append(f'<rect class="sh-ray" x="{x}" y="{base - h:.1f}" width="22" height="{h:.1f}" fill="url(#sh-green)" style="animation-delay:{d:.1f}s"></rect>')
        if red:
            reds.append(f'<rect class="sh-ray" x="{x}" y="{base - h * 1.6:.1f}" width="22" height="{h * 0.7:.1f}" fill="url(#sh-red)" style="animation-delay:{d:.1f}s"></rect>')
    return (f'<g filter="url(#sh-soft)" opacity="{opacity}">{"".join(green)}{"".join(reds)}</g>'
            f'<circle cx="720" cy="{cy}" r="{r}" fill="none" stroke="#9CC9FF" stroke-width="16" opacity="0.18" filter="url(#sh-glow)"></circle>'
            f'<circle cx="720" cy="{cy}" r="{r}" fill="#07090D" stroke="#9CC9FF" stroke-opacity="0.55" stroke-width="1.5"></circle>')


def _sun() -> str:
    return ('<circle cx="1300" cy="250" r="360" fill="#FF9E3D" opacity="0.10" filter="url(#sh-big)"></circle>'
            '<circle cx="1300" cy="250" r="305" fill="#FFB347" opacity="0.22" filter="url(#sh-glow)"></circle>'
            '<circle cx="1300" cy="250" r="280" fill="url(#sh-sun)"></circle>'
            '<rect x="1020" y="-30" width="560" height="560" filter="url(#sh-gran)" clip-path="url(#sh-sun-clip)" opacity="0.55"></rect>'
            '<g fill="none" stroke-linecap="round">'
            '<path class="sh-loop" d="M1046,142 C955,108 996,22 1092,73" stroke="#FFD08A" stroke-width="3" filter="url(#sh-halo)"></path>'
            '<path class="sh-loop" d="M1046,142 C955,108 996,22 1092,73" stroke="#FFF1D6" stroke-width="1.4" style="animation-delay:-1.5s"></path>'
            '<path class="sh-loop" d="M1113,52 C1078,-26 1152,-52 1169,13" stroke="#FFC56B" stroke-width="2.4" filter="url(#sh-halo)" style="animation-delay:-2.5s"></path>'
            '<path class="sh-loop" d="M1030,190 C946,196 948,138 1037,163" stroke="#FF8A3D" stroke-width="5" opacity="0.8" filter="url(#sh-halo)" style="animation-delay:-0.8s"></path>'
            '<path class="sh-loop" d="M1027,232 C960,252 968,284 1022,280" stroke="#FFB45C" stroke-width="2" style="animation-delay:-3s"></path></g>'
            '<circle class="sh-flare" cx="1071" cy="99" r="16" fill="#FFFFFF" filter="url(#sh-halo)"></circle>'
            '<circle cx="1071" cy="99" r="4" fill="#FFFFFF"></circle>')


def _earth_photo() -> str:
    rnd = _rng(29)
    parts = []
    for _ in range(44):
        parts.append(f'<circle class="sh-p2" cx="{-20 + rnd() * 80:.1f}" cy="{20 + rnd() * 380:.1f}" r="{0.8 + rnd() * 1.2:.2f}" '
                     f'fill="#FFD8A8" style="animation-duration:{5 + rnd() * 4:.2f}s;animation-delay:{-rnd() * 9:.2f}s"></circle>')
    return ("".join(parts)
            + '<path d="M940,6 C800,120 800,300 940,414" fill="none" stroke="#9CC9FF" stroke-opacity="0.55" stroke-width="2" stroke-dasharray="3 6"></path>'
            '<path class="sh-flow" d="M1010,52 C928,130 928,310 1010,388" fill="none" stroke="#9CC9FF" stroke-opacity="0.35" stroke-width="1.3" stroke-dasharray="6 6"></path>'
            '<circle class="sh-earth-glow" cx="1162" cy="220" r="166" fill="#6FA8FF" filter="url(#sh-big)"></circle>'
            f'<image href="{static("earth-epic.webp")}" x="1012" y="70" width="300" height="300" style="mix-blend-mode:screen"></image>'
            '<text x="40" y="404" font-size="11" fill="#FFD8A8" fill-opacity="0.75" font-family="IBM Plex Mono" letter-spacing="1">SOLAR WIND →</text>')


def _nebula() -> str:
    spikes = ""
    for x, y, s in [(1180, 120, 22), (960, 260, 14), (1330, 300, 16), (820, 90, 10), (1060, 360, 12)]:
        spikes += (f'<g stroke="#E8F0FF" stroke-linecap="round"><circle cx="{x}" cy="{y}" r="7" fill="#CFE0FF" opacity="0.5" filter="url(#sh-halo)" stroke="none"></circle>'
                   f'<line x1="{x - s}" y1="{y}" x2="{x + s}" y2="{y}" stroke-width="1" opacity="0.7"></line>'
                   f'<line x1="{x}" y1="{y - s}" x2="{x}" y2="{y + s}" stroke-width="1" opacity="0.7"></line>'
                   f'<circle cx="{x}" cy="{y}" r="2" fill="#FFFFFF" stroke="none"></circle></g>')
    return ('<g class="sh-drift"><rect x="-40" y="-40" width="1520" height="500" filter="url(#sh-nebA)" mask="url(#sh-neb-mask)" opacity="0.9"></rect>'
            '<rect x="-40" y="-40" width="1520" height="500" filter="url(#sh-nebB)" mask="url(#sh-neb-mask)" opacity="0.85"></rect>'
            f'{spikes}</g>')


def _dust() -> str:
    rnd = _rng(41)

    def layer(n, rmin, rmax, omin, omax, fill):
        return "".join(f'<circle cx="{rnd() * 1560:.1f}" cy="{rnd() * 460 - 40:.1f}" r="{rmin + rnd() * (rmax - rmin):.2f}" '
                       f'fill="{fill}" opacity="{omin + rnd() * (omax - omin):.2f}"></circle>' for _ in range(n))
    return ('<g class="sh-drift"><rect x="-40" y="-40" width="1520" height="500" filter="url(#sh-dustcloud)" opacity="0.5"></rect></g>'
            f'<g class="sh-d1">{layer(60, 0.4, 0.9, 0.3, 0.7, "#E9E1D4")}</g>'
            f'<g class="sh-d2">{layer(30, 0.9, 1.6, 0.35, 0.8, "#F3ECE1")}</g>'
            f'<g class="sh-d3" filter="url(#sh-halo)">{layer(12, 2.2, 4.2, 0.15, 0.4, "#FFF6EA")}</g>')


CAPTIONS = {"sun": "ILLUSTRATION · SOLAR FLARE AND CORONAL LOOPS",
            "earthphoto": "EARTH FROM DSCOVR, 1.5 MILLION KM AWAY · NASA EPIC · WIND PARTICLES ILLUSTRATIVE",
            "nebula": "ILLUSTRATION · NEBULA", "dust": "ILLUSTRATION · INTERPLANETARY DUST",
            "bhphoto": "A BLACK HOLE DESTROYS A STAR · NASA/JPL-CALTECH (MIRRORED)"}


def _scene(scene: str, level: str, height: int) -> str:
    photo = ""
    if scene == "bhphoto":
        photo = (f'<div style="position:absolute;inset:0;overflow:hidden" aria-hidden="true"><div class="sh-kb" style="position:absolute;inset:0">'
                 f'<img src="{static("blackhole-pia25440.jpg")}" alt="" style="position:absolute;width:150%;max-width:none;left:-20%;top:50%;transform:translateY(-48%)"></div>'
                 '<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(5,7,10,.94) 0%,rgba(5,7,10,.7) 34%,rgba(5,7,10,.1) 62%,rgba(5,7,10,0) 100%)"></div>'
                 '<div style="position:absolute;inset:0;background:linear-gradient(0deg,rgba(5,7,10,.85) 0%,rgba(5,7,10,0) 40%)"></div></div>')
    body = {"aurora": lambda: _aurora(level, 2060 + int((height - 420) * 0.67), 1720), "sun": _sun, "earthphoto": _earth_photo,
            "nebula": _nebula, "dust": _dust, "bhphoto": lambda: ""}[scene]()
    stars = "" if scene == "bhphoto" else _stars(60, height - 90)
    svg = (f'<svg viewBox="0 0 1440 {height}" preserveAspectRatio="xMidYMax slice" style="position:absolute;inset:0;width:100%;height:100%" aria-hidden="true">'
           f'{_DEFS}{stars}{body}</svg>')
    return photo + svg


def _nav(active: str, theme: str, now_label: str) -> str:
    links = "".join(
        f'<a href="{href(p, theme)}" target="_self" {"aria-current=page" if p == active else ""} '
        f'style="color:{"#F1F2F4" if p == active else "#A9AFB8"};text-decoration:none;display:flex;align-items:center;'
        f'border-bottom:2px solid {"#9CC9FF" if p == active else "transparent"};padding-top:2px">{p}</a>' for p in PAGES)
    other = "light" if theme == "dark" else "dark"
    label = "Switch to light theme" if theme == "dark" else "Switch to dark theme"
    return f"""<header class="tm-head" style="position:relative;z-index:2;border-bottom:1px solid rgba(255,255,255,0.08)">
<div style="max-width:1280px;margin:0 auto;padding:0 40px;min-height:64px;display:flex;flex-wrap:wrap;align-items:center;gap:12px 36px">
<a href="{href('Overview', theme)}" target="_self" style="display:flex;align-items:center;gap:10px;text-decoration:none;color:#F1F2F4">{icon('logo', 22)}
<span style="font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:14px;letter-spacing:0.26em">TORMENTA</span></a>
<nav class="tm-nav" aria-label="Main" style="display:flex;flex-wrap:wrap;gap:4px 26px;font-size:14px;align-self:stretch">{links}</nav>
<span style="margin-left:auto;display:flex;align-items:center;gap:16px">
<span class="tm-navclock" style="display:flex;align-items:center;gap:8px;font-family:'IBM Plex Mono',monospace;font-size:13px;color:#C9CED6">
<span class="sh-dot" style="width:7px;height:7px;border-radius:4px;background:#6FCF97"></span><span class="tm-clock">{now_label}</span> UTC</span>
<a href="{href(active, other)}" target="_self" aria-label="{label}" title="{label}" style="width:44px;height:44px;border-radius:6px;border:1px solid rgba(255,255,255,0.16);background:rgba(5,7,10,0.5);color:#F1F2F4;display:flex;align-items:center;justify-content:center">{icon('sunny' if theme == 'dark' else 'moon')}</a>
</span></div></header>"""


def hero(active: str, theme: str, now_label: str, scene: str, level: str, eyebrow: str, heading: str, lead: str,
         stat_value: str, stat_label: str, stat_alert: bool = False) -> str:
    caption = CAPTIONS.get(scene, "")
    return f"""<section class="tm-full tm-gap" style="position:relative;overflow:hidden;background:#05070A;color:#F1F2F4;min-height:420px;display:flex;flex-direction:column">
{_scene(scene, level, 420)}
{_nav(active, theme, now_label)}
<div style="position:relative;flex-grow:1;max-width:1280px;width:100%;box-sizing:border-box;margin:0 auto;padding:40px 40px 96px;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:28px">
<div style="display:flex;flex-direction:column;gap:12px;flex:1 1 560px;min-width:0">
<span style="font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:0.16em;color:#A9AFB8">{esc(eyebrow)}</span>
<h1 class="tm-hero-h1" style="margin:0;padding:0;font-size:48px;line-height:1.08;font-weight:600;letter-spacing:-0.015em;color:#F1F2F4">{esc(heading)}</h1>
<p style="margin:0;font-size:17px;line-height:1.55;color:#C9CED6;max-width:700px">{esc(lead)}</p></div>
<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;text-align:right;padding:12px 16px;border-radius:6px;background:rgba(5,7,10,0.55)">
<span class="tm-stat-big" style="font-family:'IBM Plex Mono',monospace;font-size:64px;line-height:1;font-weight:500;letter-spacing:-0.03em;color:{'#FF8A55' if stat_alert else '#F1F2F4'}">{esc(stat_value)}</span>
<span style="font-size:14px;color:#C9CED6;max-width:300px">{esc(stat_label)}</span></div></div>
<span style="position:absolute;right:12px;bottom:8px;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:0.08em;color:rgba(220,228,240,0.45)">{esc(caption)}</span>
</section>"""


def hero_overview(theme: str, now_label: str, date_label: str, level: str, kp: str, condition: str, kp_value: float,
                  line: str, today: list, watch: tuple = None, live_ok: bool = True) -> str:
    stats = "".join(f'<span>{esc(k)} <strong style="color:{c};font-weight:600">{esc(v)}</strong></span>' for k, v, c in today)
    watch_html = ""
    if watch:
        watch_html = (f'<span role="status" style="display:flex;gap:12px;align-items:flex-start;max-width:360px;padding:14px 16px;border:1px solid #FF6A2B;border-radius:6px;background:rgba(36,23,15,0.82)">'
                      f'<span style="color:#FF8A55;flex-shrink:0;margin-top:1px">{icon("warn", 20)}</span>'
                      f'<span style="display:flex;flex-direction:column;gap:3px"><span style="font-size:14px;font-weight:600;color:#FF8A55">{esc(watch[0])}</span>'
                      f'<span style="font-size:13px;line-height:1.5;color:#E4E7EB">{esc(watch[1])}</span></span></span>')
    live_dot = "#6FCF97" if live_ok else "#9AA0AA"
    return f"""<section class="tm-full" style="position:relative;overflow:hidden;background:#05070A;color:#F1F2F4;min-height:600px;display:flex;flex-direction:column">
{_scene("aurora", level, 600)}
{_nav("Overview", theme, now_label)}
<div style="position:relative;flex-grow:1;max-width:1280px;width:100%;box-sizing:border-box;margin:0 auto;padding:44px 40px 120px;display:flex;flex-wrap:wrap;justify-content:space-between;gap:32px">
<div style="display:flex;flex-direction:column;gap:14px;flex:1 1 520px;min-width:0">
<span style="display:flex;align-items:center;gap:10px;font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:0.14em;color:#A9AFB8">
<span class="sh-dot" style="width:8px;height:8px;border-radius:4px;background:{live_dot}"></span>GEOMAGNETIC CONDITIONS · NOW</span>
<span style="display:flex;align-items:flex-start;gap:6px"><span style="font-family:'IBM Plex Mono',monospace;font-size:28px;font-weight:500;color:#A9AFB8;padding-top:22px">Kp</span>
<span class="tm-kp-big" style="font-family:'IBM Plex Mono',monospace;font-size:168px;line-height:0.95;font-weight:500;letter-spacing:-0.04em">{esc(kp)}</span></span>
<span style="display:flex;align-items:center;gap:12px"><span style="color:{'#FF8A55' if kp_value >= 4.5 else '#9CC9FF'}">{condition_icon(kp_value, 30)}</span>
<span style="font-size:30px;font-weight:500">{esc(condition)}</span></span>
<span style="font-size:17px;line-height:1.5;color:#C9CED6;max-width:560px">{esc(line)}</span>
<span style="display:flex;flex-wrap:wrap;gap:8px 22px;font-family:'IBM Plex Mono',monospace;font-size:14px;color:#C9CED6;padding-top:6px">{stats}</span></div>
<div class="tm-hero-right" style="display:flex;flex-direction:column;align-items:flex-end;gap:16px;flex:0 1 380px">
<span style="font-family:'IBM Plex Mono',monospace;font-size:34px;font-weight:500;letter-spacing:0.02em"><span class="tm-clock">{now_label}</span><span style="font-size:14px;color:#A9AFB8"> UTC</span></span>
<span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#A9AFB8">{esc(date_label)}</span>{watch_html}</div></div>
</section>"""


# ── Cards and parts ──────────────────────────────────────────────────────────
def chip(text: str, bg: str, fg: str = None, border: str = None) -> str:
    fg = fg or fg_on(bg)
    b = f"border:1px solid {border};" if border else ""
    return f'<span class="tm-chip" style="background:{bg};color:{fg};{b}">{esc(text)}</span>'


def level_chip(kp: float, t: dict) -> str:
    lv = level_of(kp)
    bg = t["ramp"][lv[4]]
    return chip(lv[2].upper() if lv[2].startswith("G") else lv[3].upper(), bg)


def kpi(label: str, value: str, note: str, chip_html: str = "", color: str = None, border: str = None, t=None) -> str:
    return (f'<div class="tm-card" style="padding:18px 20px;display:flex;flex-direction:column;gap:8px;{f"border-color:{border};" if border else ""}">'
            f'<span style="font-size:13px;color:{t["muted"]}">{esc(label)}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:32px;font-weight:600;letter-spacing:-0.01em;color:{color or t["text"]}">{esc(value)}</span>'
            f'<span style="display:flex;align-items:center;gap:8px;font-size:13px;color:{t["muted"]}">{chip_html}{esc(note)}</span></div>')


def grid(items: list, min_px: int = 220, gap: int = 12, align: str = "stretch") -> str:
    return f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax({min_px}px,1fr));gap:{gap}px;align-items:{align}">{"".join(items)}</div>'


def banner(title: str, body: str, t: dict) -> str:
    return (f'<div role="status" style="border:1px solid {t["alert"]};border-radius:6px;padding:16px 18px;display:flex;gap:14px;background:{t["alert_wash"]}">'
            f'<span style="color:{t["alert_text"]};flex-shrink:0;margin-top:2px">{icon("warn", 22)}</span>'
            f'<span style="display:flex;flex-direction:column;gap:4px"><span style="font-size:14px;font-weight:600;color:{t["alert_text"]}">{esc(title)}</span>'
            f'<span style="font-size:14px;line-height:1.5;color:{t["text"]}">{esc(body)}</span></span></div>')


def section_head(title: str, sub: str = "", right: str = "") -> str:
    s = f'<span class="tm-sub">{esc(sub)}</span>' if sub else ""
    return (f'<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:8px 24px;margin:6px 0 2px">'
            f'<div style="display:flex;flex-direction:column;gap:4px"><h2 class="tm-h2">{esc(title)}</h2>{s}</div>{right}</div>')


def table(headers: list, rows: list, num_cols: set = frozenset(), caption: str = "", note: str = "", min_width: int = 0,
          row_styles: list = None) -> str:
    th = "".join(f'<th scope="col" class="{"num" if i in num_cols else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = ""
    for r_i, row in enumerate(rows):
        style = f' style="{row_styles[r_i]}"' if row_styles and row_styles[r_i] else ""
        body += f"<tr{style}>" + "".join(f'<td class="{"num" if i in num_cols else ""}">{cell}</td>' for i, cell in enumerate(row)) + "</tr>"
    cap = f'<caption style="text-align:left;padding:16px 16px 6px;font-size:16px;font-weight:600">{esc(caption)}</caption>' if caption else ""
    foot = f'<p class="tm-sub" style="margin:0;padding:12px 16px 16px">{note}</p>' if note else ""
    mw = f"min-width:{min_width}px;" if min_width else ""
    return (f'<div class="tm-flat tm-scroll"><table class="tm-table" style="{mw}">{cap}<thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table>{foot}</div>')


def kp_scale(kp: float, lo: float, hi: float, t: dict) -> str:
    edges = [(0, 3), (3, 3.5), (3.5, 4.5), (4.5, 5.5), (5.5, 6.5), (6.5, 7.5), (7.5, 9)]
    segs = "".join(f'<span style="flex:{b - a};background:{t["ramp"][i]};border-radius:2px"></span>' for i, (a, b) in enumerate(edges))
    return (f'<div style="display:flex;flex-direction:column;gap:8px"><span style="position:relative;display:flex;gap:2px;height:12px">{segs}'
            f'<span style="position:absolute;top:-5px;height:20px;border:2px solid {t["text"]};border-radius:5px;left:{lo / 9:.2%};width:{max(hi - lo, 0.08) / 9:.2%};box-sizing:border-box;opacity:.55"></span>'
            f'<span style="position:absolute;top:-7px;width:3px;height:26px;margin-left:-1px;background:{t["text"]};border-radius:2px;left:{kp / 9:.2%}"></span></span>'
            f'<span style="display:flex;justify-content:space-between;font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:{t["muted"]}">'
            f'<span>0</span><span>3</span><span>5 · G1</span><span>7 · G3</span><span>9 · G5</span></span></div>')


def sparkline(values: list, width: int, height: int, color: str, top: float = None) -> str:
    vals = [v for v in values if v == v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), (top if top is not None else max(vals))
    span = (hi - lo) or 1
    pts = " ".join(f"{i * width / (len(vals) - 1):.1f},{height - 4 - (v - lo) / span * (height - 8):.1f}" for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto;display:block" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"></polyline></svg>')


def tile(icon_name: str, title: str, value: str, unit: str, note: str, t: dict, extra: str = "") -> str:
    return (f'<article class="tm-card" style="padding:18px;display:flex;flex-direction:column;gap:10px;min-height:150px">'
            f'<span style="display:flex;align-items:center;gap:8px;font-size:12px;font-weight:500;letter-spacing:0.06em;color:{t["muted"]}">'
            f'<span style="color:{t["primary"]};display:flex">{icon(icon_name)}</span>{esc(title)}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:30px;font-weight:500;letter-spacing:-0.01em">{esc(value)}'
            f'<span style="font-size:14px;color:{t["muted"]}"> {esc(unit)}</span></span>{extra}'
            f'<span style="margin-top:auto;font-size:13px;line-height:1.45;color:{t["muted"]}">{esc(note)}</span></article>')


def card(name: str):
    """A Streamlit container styled as a card (CSS matches its key class, st-key-card_<name>)."""
    return st.container(key=f"card_{name}")


def credits(t: dict) -> str:
    return (f'<div class="tm-credits" style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 24px;padding-top:20px;margin-top:12px;'
            f'border-top:1px solid {t["hair"]};font-size:12px;color:{t["muted"]}">'
            '<span>Data: GFZ Potsdam (Kp, Ap, F10.7, CC BY 4.0) · NOAA SWPC · NASA OMNIWeb. Images: Milky Way ESO/S. Brunier (CC BY 4.0) · '
            'Earth NASA EPIC/DSCOVR · black hole NASA/JPL-Caltech.</span>'
            '<span style="font-family:\'IBM Plex Mono\',monospace">Tormenta · CT-378 Machine Learning, NED University</span></div>')
