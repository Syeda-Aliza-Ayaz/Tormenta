"""Colour tokens (Carbon & Ice dark, Flight Manual light) and the page-wide CSS that restyles Streamlit."""
import altair as alt

from .data import IN_BROWSER

TOKENS = {
    "dark": {
        "ground": "#0E0F11", "surface": "#16181B", "raised": "#1D2024", "hair": "#2C3036", "grid": "#1E2125",
        "track": "#2C3036", "text": "#F1F2F4", "muted": "#9AA0AA", "primary": "#9CC9FF", "primary_fg": "#0B1220",
        "link": "#9CC9FF", "alert": "#FF6A2B", "alert_text": "#FF8A55", "alert_fg": "#1F0B00", "alert_wash": "#24170F",
        "good": "#9CC9FF", "live": "#6FCF97", "band": 0.16, "highlight": "#1A1D21",
        "series": {"histgb": "#9CC9FF", "arimax": "#6FCF97", "noaa": "#D7B46A", "arima": "#E8A6C8",
                   "sarima": "#B9A6F0", "chronos": "#C9A0DC", "trailing27": "#9AA0AA", "persistence": "#F0A36B",
                   "recurrence27": "#7FD1D9", "climatology": "#6A707A"},
        "ramp": ["#2C3036", "#4D525B", "#7C828D", "#FFD166", "#FFA94D", "#FF6A2B", "#F03E5F"],
    },
    "light": {
        "ground": "#F2F4F7", "surface": "#FFFFFF", "raised": "#F7F8FA", "hair": "#D9DEE5", "grid": "#ECEFF3",
        "track": "#E4E8EE", "text": "#0D1B2A", "muted": "#566173", "primary": "#1D4E89", "primary_fg": "#FFFFFF",
        "link": "#1D4E89", "alert": "#FF4F00", "alert_text": "#C23B00", "alert_fg": "#1F0B00", "alert_wash": "#FFF4EE",
        "good": "#1D4E89", "live": "#1E8E5A", "band": 0.13, "highlight": "#F3F6FA",
        "series": {"histgb": "#1D4E89", "arimax": "#2E8B74", "noaa": "#7B5EA7", "arima": "#B4487A",
                   "sarima": "#6A54B8", "chronos": "#B07A1E", "trailing27": "#7A8494", "persistence": "#C2622A",
                   "recurrence27": "#2A8A96", "climatology": "#A3ACB9"},
        "ramp": ["#E4E8EE", "#C3CCD8", "#8C9BB0", "#F6C343", "#FF8A1F", "#FF4F00", "#C81E1E"],
    },
}

_GITHUB_STATIC = "https://raw.githubusercontent.com/Syeda-Aliza-Ayaz/Tormenta/main/app/static/"


def static(name: str) -> str:
    """URL of a file in app/static: served by Streamlit (enableStaticServing), or from GitHub in the browser build."""
    return (_GITHUB_STATIC if IN_BROWSER else "app/static/") + name


def fg_on(hex_color: str) -> str:
    """Readable text colour on a filled background."""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = sum(w * (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for w, c in zip((0.2126, 0.7152, 0.0722), (r, g, b)))
    return "#0B0F14" if lum > 0.25 else "#FFFFFF"


def css(theme: str) -> str:
    t = TOKENS[theme]
    dark = theme == "dark"
    page_bg = (f"background: linear-gradient(rgba(4,6,10,0.42), rgba(4,6,10,0.42)), "
               f"url('{static('milkyway-eso0932a.jpg')}') center 38% / cover fixed, #04060A;") if dark else \
        f"background: {t['ground']};"
    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root {{ --tm-text:{t['text']}; --tm-muted:{t['muted']}; --tm-primary:{t['primary']}; --tm-surface:{t['surface']};
  --tm-raised:{t['raised']}; --tm-hair:{t['hair']}; --tm-alert:{t['alert']}; }}
html, body, .stApp {{ {page_bg} color: {t['text']}; }}
.stApp, .stApp p, .stApp label, .stApp span, .stApp div, .stApp button, .stApp input {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, [data-testid="stExpanderIcon"] span {{ font-family: 'Material Symbols Rounded' !important; }}
.stApp h2.tm-h2, .stApp .stMarkdown h2.tm-h2 {{ font-size: 18px !important; font-weight: 600 !important; line-height: 1.3 !important; padding: 0 !important; margin: 0 !important; letter-spacing: 0 !important; }}
.stApp .stMarkdown h3 {{ padding: 0 !important; line-height: 1.3 !important; }}
.stApp .stMarkdown h1 {{ padding: 0 !important; }}
.stApp [class*="st-key-card_"] {{ background: {t['surface']}; border: 1px solid {t['hair']}; border-radius: 6px; padding: 18px 20px; }}
.stApp code, .tm-mono {{ font-family: 'IBM Plex Mono', monospace !important; }}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer,
[data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width: 1280px; padding: 0 40px 64px !important; }}
[data-testid="stAppViewContainer"] > .main, section.main {{ background: transparent; }}
.stApp [data-testid="stVerticalBlock"] {{ gap: 14px; }}
.element-container:has(iframe[height="0"]), [data-testid="stElementContainer"]:has(iframe[srcdoc*="tmClock"]), .element-container:has(iframe[srcdoc*="tmClock"]) {{ display: none !important; }}
.tm-full {{ width: 100vw; margin-left: calc(50% - 50vw); }}
.tm-gap {{ margin-bottom: 18px; }}
.tm-head {{ background: rgba(5,7,10,0.55); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); }}
a {{ color: {t['link']}; }}


/* widgets */
.stApp label, [data-testid="stWidgetLabel"] p {{ color: {t['muted']} !important; font-size: 12px !important; }}
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
  background: {t['raised']}; color: {t['text']}; border: 1px solid {t['hair']}; border-radius: 4px; min-height: 40px;
  font-size: 13px; transition: background-color .2s, border-color .2s, filter .2s, transform .12s; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ border-color: {t['primary']}; color: {t['text']}; filter: brightness(1.1); }}
.stButton > button:active, .stFormSubmitButton > button:active {{ transform: translateY(1px) scale(0.98); }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"], .stFormSubmitButton > button {{
  background: {t['primary']}; color: {t['primary_fg']}; border-color: {t['primary']}; font-weight: 600; }}
[data-testid="stRadio"] [role="radiogroup"] {{ display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: 6px;
  background: {t['raised']}; border: 1px solid {t['hair']}; }}
[data-testid="stRadio"] [role="radiogroup"] label {{ margin: 0 !important; padding: 7px 14px; border-radius: 4px; cursor: pointer;
  transition: background-color .2s; }}
[data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]) {{ display: none !important; }}
[data-testid="stRadio"] [role="radiogroup"] label[data-selected="true"] {{ background: {t['primary']}; }}
[data-testid="stRadio"] [role="radiogroup"] label[data-selected="true"] p {{ color: {t['primary_fg']} !important; }}
[data-testid="stRadio"] [role="radiogroup"] label p {{ color: {t['text']} !important; font-size: 13px !important; }}
[data-testid="stRadio"] [role="radiogroup"] label:hover {{ background: {t['hair']}; }}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {{ background: {t['primary']}; }}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p {{ color: {t['primary_fg']} !important; }}
.stApp input, .stApp textarea, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div {{
  background: {t['raised']} !important; color: {t['text']} !important; border-color: {t['hair']} !important;
  font-family: 'IBM Plex Mono', monospace !important; }}
[data-baseweb="input"]:focus-within {{ border-color: {t['primary']} !important; box-shadow: 0 0 0 3px rgba(156,201,255,.22); }}
[data-testid="stNumberInput"] button {{ background: {t['raised']} !important; color: {t['muted']} !important; }}
[data-testid="stExpander"] details {{ background: {t['surface']}; border: 1px solid {t['hair']} !important; border-radius: 6px; }}
[data-testid="stExpander"] summary p {{ color: {t['text']} !important; font-size: 14px !important; }}
[data-testid="stForm"] {{ background: {t['surface']}; border: 1px solid {t['hair']}; border-radius: 6px; }}
[data-testid="stAlert"] {{ background: {t['surface']}; border: 1px solid {t['hair']}; color: {t['text']}; }}
[data-testid="stCaptionContainer"], .stApp small {{ color: {t['muted']} !important; }}
[data-testid="stImage"] img {{ border-radius: 6px; }}
[data-testid="stTabs"] [role="tab"] p {{ color: {t['muted']}; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {t['text']}; }}
[data-baseweb="tab-highlight"] {{ background: {t['primary']} !important; }}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {{ color: {t['muted']}; }}

/* own components */
.tm-card {{ background: {t['surface']}; border: 1px solid {t['hair']}; border-radius: 6px;
  transition: transform .28s cubic-bezier(.2,.7,.2,1), border-color .28s, box-shadow .28s; }}
.tm-card:hover {{ transform: translateY(-3px); border-color: rgba(156,201,255,0.5); box-shadow: 0 18px 40px -24px rgba(156,201,255,0.45); }}
.tm-flat {{ background: {t['surface']}; border: 1px solid {t['hair']}; border-radius: 6px; }}
.tm-cell, .tm-row {{ transition: background-color .2s; }}
.tm-cell:hover, .tm-row:hover {{ background-color: rgba(156,201,255,0.07) !important; }}
.tm-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.tm-table th {{ text-align: left; color: {t['muted']}; font-weight: 500; font-size: 12px; padding: 10px 12px; border-bottom: 1px solid {t['hair']}; }}
.tm-table td {{ padding: 11px 12px; border-bottom: 1px solid {t['grid']}; color: {t['text']}; }}
.tm-table tbody tr {{ transition: background-color .2s; }}
.tm-table tbody tr:hover {{ background-color: rgba(156,201,255,0.07); }}
.tm-table .num {{ text-align: right; font-family: 'IBM Plex Mono', monospace; }}
.tm-scroll {{ overflow-x: auto; }}
.tm-link {{ color: {t['link']}; text-decoration: none; background-image: linear-gradient(currentColor,currentColor);
  background-size: 0% 1px; background-repeat: no-repeat; background-position: 0 100%; transition: background-size .3s cubic-bezier(.2,.7,.2,1); }}
.tm-link:hover {{ background-size: 100% 1px; }}
.tm-nav a {{ transition: color .2s, border-color .25s; }}
.tm-nav a:hover {{ color: #F1F2F4 !important; border-bottom-color: rgba(156,201,255,0.6) !important; }}
.tm-chip {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; padding: 2px 8px; border-radius: 3px; white-space: nowrap; }}
.tm-eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: .14em; color: {t['muted']}; }}
.tm-h2 {{ margin: 0; font-size: 18px; font-weight: 600; color: {t['text']}; }}
.tm-sub {{ font-size: 13px; color: {t['muted']}; line-height: 1.5; }}
:focus-visible {{ outline: 2px solid {t['primary']}; outline-offset: 2px; }}

/* phones */
@media (max-width: 720px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding: 0 16px 48px !important; }}
  .tm-full header > div, .tm-full > div {{ padding-left: 16px !important; padding-right: 16px !important; }}
  .tm-nav {{ gap: 4px 16px !important; font-size: 13px !important; }}
  .tm-navclock {{ display: none !important; }}
  .tm-kp-big {{ font-size: 96px !important; }}
  .tm-hero-h1 {{ font-size: 32px !important; }}
  .tm-stat-big {{ font-size: 40px !important; }}
  .tm-hero-right {{ align-items: flex-start !important; flex-basis: 100% !important; }}
  .tm-row {{ grid-template-columns: 74px 30px 58px minmax(0,1fr) 40px !important; gap: 8px !important; padding: 12px 14px !important; }}
}}

/* scrollbar */
html {{ scrollbar-width: thin; scrollbar-color: #4A515B transparent; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background-color: #3A4048; border-radius: 10px; border: 3px solid transparent; background-clip: content-box; }}
::-webkit-scrollbar-thumb:hover {{ background-color: {t['primary']}; }}

/* cursor and trailing ring (desktop only) */
#tm-ring {{ position: fixed; left: 0; top: 0; width: 32px; height: 32px; box-sizing: border-box; border-radius: 50%;
  border: 1.5px solid #FFFFFF; mix-blend-mode: difference; pointer-events: none; z-index: 100000; opacity: 0;
  transition: transform .14s cubic-bezier(.2,.7,.2,1), opacity .2s; }}
@media (hover: hover) and (pointer: fine) {{
  .stApp, .stApp * {{ cursor: url('{static("cursor-dot.svg")}') 12 12, auto; }}
  .stApp a, .stApp a *, .stApp button, .stApp button *, .stApp label, .stApp [role="button"], .stApp [role="tab"],
  .stApp [data-baseweb="select"] * {{ cursor: url('{static("cursor-point.svg")}') 12 12, pointer !important; }}
  .stApp input, .stApp textarea {{ cursor: text !important; }}
}}

/* hero scene animation */
.sh-ray {{ transform-box: fill-box; transform-origin: 50% 100%; animation: sh-sway 7s ease-in-out infinite alternate; }}
.sh-star {{ animation: sh-twinkle 4s ease-in-out infinite; }}
.sh-dot {{ animation: sh-pulse 2s ease-in-out infinite; }}
.sh-loop {{ animation: sh-loop 5s ease-in-out infinite alternate; }}
.sh-flare {{ transform-box: fill-box; transform-origin: center; animation: sh-flare 6s ease-in-out infinite; }}
.sh-drift {{ animation: sh-drift 40s ease-in-out infinite alternate; }}
.sh-flow {{ animation: sh-flow 3s linear infinite; }}
.sh-d1 {{ animation: sh-dust 26s linear infinite; }} .sh-d2 {{ animation: sh-dust 18s linear infinite; }} .sh-d3 {{ animation: sh-dust 12s linear infinite; }}
.sh-kb {{ transform-origin: 65% 40%; animation: sh-kb 36s ease-in-out infinite alternate; }}
.sh-p2 {{ animation-name: sh-stream2; animation-timing-function: linear; animation-iteration-count: infinite; }}
.sh-earth-glow {{ transform-box: fill-box; transform-origin: center; animation: sh-breathe 6s ease-in-out infinite alternate; }}
@keyframes sh-sway {{ 0% {{ transform: scaleY(.82) skewX(-4deg); }} 50% {{ transform: scaleY(1.06) skewX(2deg); }} 100% {{ transform: scaleY(.9) skewX(5deg); }} }}
@keyframes sh-twinkle {{ 0%,100% {{ opacity: .25; }} 50% {{ opacity: .9; }} }}
@keyframes sh-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}
@keyframes sh-loop {{ 0% {{ opacity: .45; }} 100% {{ opacity: 1; }} }}
@keyframes sh-flare {{ 0%,70%,100% {{ transform: scale(.6); opacity: .35; }} 80% {{ transform: scale(1.5); opacity: 1; }} }}
@keyframes sh-drift {{ 0% {{ transform: translate(0,0); }} 100% {{ transform: translate(-40px,12px); }} }}
@keyframes sh-flow {{ to {{ stroke-dashoffset: -120; }} }}
@keyframes sh-dust {{ 0% {{ transform: translate(0,0); }} 100% {{ transform: translate(-120px,40px); }} }}
@keyframes sh-kb {{ from {{ transform: scale(1) rotate(0deg); }} to {{ transform: scale(1.12) rotate(1.2deg); }} }}
@keyframes sh-stream2 {{ 0% {{ transform: translateX(0); opacity: 0; }} 8% {{ opacity: .9; }} 80% {{ opacity: .9; }} 100% {{ transform: translateX(840px); opacity: 0; }} }}
@keyframes sh-breathe {{ from {{ opacity: .18; }} to {{ opacity: .32; }} }}
@media (prefers-reduced-motion: reduce) {{
  .sh-ray,.sh-star,.sh-dot,.sh-loop,.sh-flare,.sh-drift,.sh-flow,.sh-d1,.sh-d2,.sh-d3,.sh-kb,.sh-p2,.sh-earth-glow {{ animation: none; }}
  .tm-card, #tm-ring {{ transition: none; }} .tm-card:hover {{ transform: none; }}
}}
</style>"""


CLIENT_JS = """<script>
(function () {
  const w = window.parent, d = w.document;
  if (!w.__tmClock) {
    const tick = () => { const s = new Date().toISOString().slice(11, 19); d.querySelectorAll('.tm-clock').forEach(e => { e.textContent = s; }); };
    w.__tmClock = setInterval(tick, 1000); tick();
  }
  const fine = w.matchMedia('(hover: hover) and (pointer: fine)').matches;
  const calm = w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (fine && !calm && !d.getElementById('tm-ring')) {
    const r = d.createElement('div'); r.id = 'tm-ring'; d.body.appendChild(r);
    d.addEventListener('mousemove', e => {
      const hot = e.target && e.target.closest ? e.target.closest('a, button, label, input, [role=button], [role=tab]') : null;
      r.style.opacity = '1';
      r.style.transform = 'translate(' + (e.clientX - 16) + 'px,' + (e.clientY - 16) + 'px) scale(' + (hot ? 1.5 : 1) + ')';
    });
    d.addEventListener('mouseleave', () => { r.style.opacity = '0'; });
  }
})();
</script>"""


def style_chart(chart, theme: str, height: int = None):
    """Transparent background, theme colours, monospace axis labels."""
    t = TOKENS[theme]
    if height:
        chart = chart.properties(height=height)
    return (chart.configure(background="transparent", font="IBM Plex Sans")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=t["muted"], titleColor=t["muted"], gridColor=t["grid"], domainColor=t["hair"],
                            tickColor=t["hair"], labelFont="IBM Plex Mono", labelFontSize=11, titleFontSize=12,
                            titleFontWeight=500)
            .configure_legend(labelColor=t["text"], titleColor=t["muted"], labelFont="IBM Plex Sans", labelFontSize=12,
                              symbolStrokeWidth=3)
            .configure_text(font="IBM Plex Mono"))


def altair_ready():
    alt.data_transformers.disable_max_rows()
