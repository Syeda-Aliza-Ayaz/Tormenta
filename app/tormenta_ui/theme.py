"""Colour tokens (Carbon & Ice dark, Flight Manual light) and the page-wide CSS that restyles Streamlit."""
import altair as alt

from .data import IN_BROWSER

TOKENS = {
    "dark": {
        "ground": "#0E0F11", "surface": "#16181B", "card": "var(--tm-card)", "card_rgb": "22,24,27", "raised": "#1D2024", "hair": "#2C3036", "grid": "#1E2125",
        "track": "#2C3036", "text": "#F1F2F4", "muted": "#9AA0AA", "primary": "#9CC9FF", "primary_fg": "#0B1220",
        "link": "#9CC9FF", "alert": "#FF6A2B", "alert_text": "#FF8A55", "alert_fg": "#1F0B00", "alert_wash": "#24170F",
        "good": "#9CC9FF", "live": "#6FCF97", "band": 0.16, "highlight": "#1A1D21",
        "series": {"histgb": "#9CC9FF", "arimax": "#6FCF97", "noaa": "#D7B46A", "arima": "#E8A6C8",
                   "sarima": "#B9A6F0", "chronos": "#C9A0DC", "trailing27": "#9AA0AA", "persistence": "#F0A36B",
                   "recurrence27": "#7FD1D9", "climatology": "#6A707A"},
        "ramp": ["#2C3036", "#4D525B", "#7C828D", "#FFD166", "#FFA94D", "#FF6A2B", "#F03E5F"],
    },
    "light": {
        "ground": "#F2F4F7", "surface": "#FFFFFF", "card": "var(--tm-card)", "card_rgb": "255,255,255", "raised": "#F7F8FA", "hair": "#D9DEE5", "grid": "#ECEFF3",
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


def _svg_url(svg: str) -> str:
    from urllib.parse import quote
    return "data:image/svg+xml;utf8," + quote(svg)


# faint dipole field lines across the light page, and a fine dot grid
LIGHT_FIELD = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000" fill="none" '
    'stroke="#1D4E89" stroke-width="1.2" opacity="0.10">'
    + "".join(f'<path d="M1180 360C{1180 - k * 120} {360 - k * 70} {1180 - k * 150} {640 + k * 70} 1180 640"></path>'
              f'<path d="M1180 360C{1180 + k * 120} {360 - k * 70} {1180 + k * 150} {640 + k * 70} 1180 640"></path>'
              for k in range(1, 8))
    + '<circle cx="1180" cy="500" r="64" stroke-width="1.6"></circle></svg>')
LIGHT_DOTS = _svg_url('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"><circle cx="1" cy="1" r="0.9" fill="#0D1B2A" opacity="0.07"></circle></svg>')
SPINNER = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 32 32" fill="none">'
    '<defs><linearGradient id="g" x1="2" y1="4" x2="30" y2="28" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="#9CC9FF"/><stop offset="1" stop-color="#6FCF97"/></linearGradient></defs>'
    '<g stroke="url(#g)" stroke-width="1.7" stroke-linecap="round" stroke-dasharray="40" stroke-dashoffset="40">'
    '<path d="M16 11.2C4.5 3 1.5 26 16 20.8"><animate attributeName="stroke-dashoffset" values="40;0;0;-40" dur="1.8s" repeatCount="indefinite"/></path>'
    '<path d="M16 11.2C27.5 3 30.5 26 16 20.8"><animate attributeName="stroke-dashoffset" values="40;0;0;-40" dur="1.8s" begin="0.3s" repeatCount="indefinite"/></path></g>'
    '<circle cx="16" cy="16" r="4.2" fill="url(#g)"><animate attributeName="r" values="3.6;4.4;3.6" dur="1.8s" repeatCount="indefinite"/></circle>'
    '<circle r="1.6" fill="#9CC9FF"><animateMotion dur="1.6s" repeatCount="indefinite" path="M16 11.2C27.5 3 30.5 26 16 20.8C1.5 26 4.5 3 16 11.2"/></circle></svg>')


def css(theme: str) -> str:
    t = TOKENS[theme]
    dark = theme == "dark"
    page_bg = (f"background: linear-gradient(rgba(4,6,10,0.42), rgba(4,6,10,0.42)), "
               f"url('{static('milkyway-eso0932a.jpg')}') center 38% / cover fixed, #04060A;") if dark else \
        (f"background: radial-gradient(1100px 620px at 88% -8%, rgba(29,78,137,0.13), transparent 62%) fixed, "
         f"radial-gradient(900px 560px at -8% 34%, rgba(46,139,116,0.10), transparent 60%) fixed, "
         f"radial-gradient(900px 620px at 55% 112%, rgba(123,94,167,0.09), transparent 62%) fixed, "
         f"url(\"{LIGHT_FIELD}\") center top / 1600px auto no-repeat fixed, "
         f"url(\"{LIGHT_DOTS}\") 0 0 / 22px 22px fixed, {t['ground']};")
    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root {{ --tm-card-alpha: 0.2; --tm-card: rgba({t['card_rgb']}, var(--tm-card-alpha));   /* card background see-through: 0 = clear, 1 = solid */
  --tm-text:{t['text']}; --tm-muted:{t['muted']}; --tm-primary:{t['primary']}; --tm-surface:{t['surface']};
  --tm-raised:{t['raised']}; --tm-hair:{t['hair']}; --tm-alert:{t['alert']}; }}
html, body, .stApp {{ {page_bg} color: {t['text']}; }}
.stApp, .stApp p, .stApp label, .stApp span, .stApp div, .stApp button, .stApp input {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, [data-testid="stExpanderIcon"] span {{ font-family: 'Material Symbols Rounded' !important; }}
.stApp h2.tm-h2, .stApp .stMarkdown h2.tm-h2 {{ font-size: 18px !important; font-weight: 600 !important; line-height: 1.3 !important; padding: 0 !important; margin: 0 !important; letter-spacing: 0 !important; }}
.stApp .stMarkdown h3 {{ padding: 0 !important; line-height: 1.3 !important; }}
.stApp .stMarkdown h1 {{ padding: 0 !important; }}
.stApp [class*="st-key-card_"], .tm-card, .tm-flat, [data-testid="stExpander"] details, [data-testid="stForm"] {{ -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }}
.stApp [class*="st-key-card_"] {{ background: {t['card']}; border: 1px solid {t['hair']}; border-radius: 8px; padding: 22px 24px; gap: 14px; }}
.stApp code, .tm-mono {{ font-family: 'IBM Plex Mono', monospace !important; }}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer,
[data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width: 1280px; padding: 0 40px 64px !important; }}
[data-testid="stAppViewContainer"] > .main, section.main {{ background: transparent; }}
.stApp [data-testid="stVerticalBlock"] {{ gap: 20px; }}
.stApp [data-testid="stHorizontalBlock"] {{ gap: 16px; align-items: stretch; }}
/* side-by-side cards: each card fills its column, so cards in one row end at the same height */
.stApp [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
.stApp [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-card_"]) {{ flex: 1 1 auto; }}
.stApp [data-testid="stColumn"] [class*="st-key-card_"] {{ height: 100%; box-sizing: border-box; }}
.stApp .stMarkdown, .stApp [data-testid="stMarkdown"], .stApp [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
.stApp [data-testid="stMarkdownContainer"] > div:last-child {{ margin-bottom: 0; }}
.element-container:has(iframe[height="0"]), [data-testid="stElementContainer"]:has(iframe[srcdoc*="tmClock"]), .element-container:has(iframe[srcdoc*="tmClock"]) {{ display: none !important; }}
.tm-full {{ width: 100vw; margin-left: calc(50% - 50vw); }}
.tm-gap {{ margin-bottom: 8px; }}
.tm-hero {{ -webkit-mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 120px), transparent 100%);
  mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 120px), transparent 100%); }}
.tm-head {{ position: fixed !important; top: 0; left: 0; right: 0; z-index: 1000; background: rgba(5,7,10,0.78);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); box-shadow: 0 8px 24px -16px rgba(0,0,0,.6); }}
.tm-hero {{ padding-top: 65px; box-sizing: border-box; }}
/* the nav's own block sits above every later block (each Streamlit block is its own stacking layer) */
.stApp [data-testid="stElementContainer"]:has(.tm-head), .stApp [data-testid="stMarkdown"]:has(.tm-head) {{ position: relative; z-index: 1000 !important; }}
/* blocks that only hold the stylesheet or an empty placeholder take no space */
.stApp [data-testid="stElementContainer"]:has(> [data-testid="stEmpty"]),
.stApp [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child) {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ padding-top: 0 !important; }}
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
[data-testid="stExpander"] details {{ background: {t['card']}; border: 1px solid {t['hair']} !important; border-radius: 6px; }}
[data-testid="stExpander"] summary p {{ color: {t['text']} !important; font-size: 14px !important; }}
[data-testid="stForm"] {{ background: {t['card']}; border: 1px solid {t['hair']}; border-radius: 6px; }}
[data-testid="stAlert"] {{ background: {t['card']}; border: 1px solid {t['hair']}; color: {t['text']}; }}
[data-testid="stCaptionContainer"], .stApp small {{ color: {t['muted']} !important; }}
[data-testid="stImage"] img {{ border-radius: 6px; }}
[data-testid="stTabs"] [role="tab"] p {{ color: {t['muted']}; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: {t['text']}; }}
[data-baseweb="tab-highlight"] {{ background: {t['primary']} !important; }}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {{ color: {t['muted']}; }}

/* own components */
.tm-card {{ background: {t['card']}; border: 1px solid {t['hair']}; border-radius: 8px; box-sizing: border-box; min-width: 0;
  transition: transform .28s cubic-bezier(.2,.7,.2,1), border-color .28s, box-shadow .28s; }}
.tm-card:hover {{ transform: translateY(-3px); border-color: rgba(156,201,255,0.5); box-shadow: 0 18px 40px -24px rgba(156,201,255,0.45); }}
.tm-split {{ gap: 0 !important; background: {t['card']} !important; -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }}
.tm-split > * {{ background: transparent !important; box-shadow: 1px 0 0 {t['hair']}, 0 1px 0 {t['hair']}; }}
.tm-flat {{ background: {t['card']}; border: 1px solid {t['hair']}; border-radius: 8px; box-sizing: border-box; }}
.tm-flat > .tm-table th:first-child, .tm-flat > .tm-table td:first-child {{ padding-left: 20px; }}
.tm-flat > .tm-table th:last-child, .tm-flat > .tm-table td:last-child {{ padding-right: 20px; }}
.tm-flat > .tm-table caption {{ padding: 20px 20px 8px !important; }}
.tm-flat > p.tm-sub {{ padding: 14px 20px 18px !important; }}
.tm-cell, .tm-row {{ transition: background-color .2s; }}
.tm-cell:hover, .tm-row:hover {{ background-color: rgba(156,201,255,0.07) !important; }}
.tm-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.tm-table th {{ text-align: left; color: {t['muted']}; font-weight: 500; font-size: 12px; padding: 12px 14px; border-bottom: 1px solid {t['hair']}; }}
.tm-table td {{ padding: 12px 14px; border-bottom: 1px solid {t['grid']}; color: {t['text']}; }}
.tm-table tbody tr {{ transition: background-color .2s; }}
.tm-table tbody tr:hover {{ background-color: rgba(156,201,255,0.07); }}
.tm-table .num {{ text-align: right; font-family: 'IBM Plex Mono', monospace; }}
.tm-scroll {{ overflow-x: auto; }}
.tm-link {{ display: inline-block; width: fit-content; max-width: 100%; align-self: flex-start; color: {t['link']}; text-decoration: none; background-image: linear-gradient(currentColor,currentColor);
  background-size: 0% 1px; background-repeat: no-repeat; background-position: 0 100%; transition: background-size .3s cubic-bezier(.2,.7,.2,1); }}
.tm-link:hover {{ background-size: 100% 1px; }}
.tm-nav a {{ transition: color .2s, border-color .25s; }}
.tm-nav a:hover {{ color: #F1F2F4 !important; border-bottom-color: rgba(156,201,255,0.6) !important; }}
.tm-chip {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; padding: 2px 8px; border-radius: 3px; white-space: nowrap; }}
.tm-eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: .14em; color: {t['muted']}; }}
.tm-h2 {{ margin: 0; font-size: 18px; font-weight: 600; color: {t['text']}; }}
.tm-sub {{ font-size: 13px; color: {t['muted']}; line-height: 1.5; }}
:focus-visible {{ outline: 2px solid {t['primary']}; outline-offset: 2px; }}

/* chart tooltips */
#vg-tooltip-element.vg-tooltip {{ background: {t['raised']} !important; color: {t['text']} !important; border: 1px solid {t['hair']} !important;
  border-radius: 6px !important; padding: 10px 12px !important; box-shadow: 0 12px 32px -12px rgba(0,0,0,.55) !important;
  font-family: 'IBM Plex Mono', monospace !important; font-size: 12px !important; }}
#vg-tooltip-element.vg-tooltip td.key {{ color: {t['muted']} !important; padding-right: 12px !important; }}
#vg-tooltip-element.vg-tooltip td.value {{ color: {t['text']} !important; text-align: right !important; }}

/* loader: the logo's field lines draw while a particle orbits */
[data-testid="stSpinner"] > div {{ display: flex; align-items: center; gap: 14px; padding: 16px 20px; border-radius: 8px;
  background: {t['card']}; border: 1px solid {t['hair']}; color: {t['muted']}; font-size: 14px; width: fit-content; }}
[data-testid="stSpinner"] i, [data-testid="stSpinner"] svg, [data-testid="stSpinnerIcon"] {{ display: none !important; }}
[data-testid="stSpinner"] > div::before {{ content: ""; flex: 0 0 34px; height: 34px; background: url("{SPINNER}") center / contain no-repeat; }}
.tm-loader {{ display: flex; align-items: center; gap: 14px; padding: 16px 20px; border-radius: 8px; background: {t['card']};
  border: 1px solid {t['hair']}; color: {t['muted']}; font-size: 14px; width: fit-content; }}
.tm-load-mark .tm-draw {{ stroke-dasharray: 40; animation: tm-draw 1.8s ease-in-out infinite; }}
.tm-load-mark .tm-d2 {{ animation-delay: .3s; }}
.tm-load-mark .tm-core {{ transform-box: fill-box; transform-origin: center; animation: tm-breathe 1.8s ease-in-out infinite; }}
@keyframes tm-draw {{ 0% {{ stroke-dashoffset: 40; }} 45%, 60% {{ stroke-dashoffset: 0; }} 100% {{ stroke-dashoffset: -40; }} }}
@keyframes tm-breathe {{ 0%, 100% {{ transform: scale(.88); }} 50% {{ transform: scale(1.06); }} }}
.tm-splash {{ position: fixed; inset: 0; z-index: 99999; font-family: 'IBM Plex Sans', system-ui, sans-serif; display: flex; align-items: center; justify-content: center;
  background: radial-gradient(800px 500px at 50% 45%, #0E1726 0%, #05070A 70%);
  animation: tm-splash-in .3s ease .5s both, tm-splash-out .6s ease 14s forwards; }}
.tm-splash-in {{ display: flex; flex-direction: column; align-items: center; gap: 18px; text-align: center; padding: 24px; }}
.tm-splash-msg {{ font-size: 14px; color: #A9AFB8; }}
.tm-splash-bar {{ width: 180px; height: 2px; border-radius: 2px; background: rgba(156,201,255,.15); overflow: hidden; }}
.tm-splash-bar span {{ display: block; width: 40%; height: 100%; background: linear-gradient(90deg, #9CC9FF, #6FCF97);
  animation: tm-bar 1.4s ease-in-out infinite; }}
@keyframes tm-bar {{ 0% {{ transform: translateX(-110%); }} 100% {{ transform: translateX(260%); }} }}
@keyframes tm-splash-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes tm-splash-out {{ to {{ opacity: 0; visibility: hidden; }} }}
.stApp [data-stale="true"] {{ opacity: .55; transition: opacity .3s; }}

/* footer */
.tm-footer ul {{ list-style: none !important; padding-left: 0 !important; margin: 0 !important; }}
.tm-footer li {{ margin: 0 !important; padding: 0 !important; }}
.tm-footer li::marker {{ content: none; }}
.tm-foot-link {{ color: {t['muted']} !important; text-decoration: none !important; transition: color .2s; }}
.tm-foot-link:hover {{ color: {t['text']} !important; }}
.tm-gh {{ display: inline-flex; align-items: center; gap: 8px; width: fit-content; padding: 9px 14px; border-radius: 6px;
  border: 1px solid {t['hair']}; background: {t['raised']}; color: {t['text']} !important; text-decoration: none !important; font-size: 13px;
  transition: border-color .2s, transform .12s; }}
.tm-gh:hover {{ border-color: {t['primary']}; }}
.tm-gh:active {{ transform: translateY(1px); }}

/* phones */
@media (max-width: 720px) {{
  [data-testid="stMainBlockContainer"], .block-container {{ padding: 0 16px 48px !important; }}
  .tm-full header > div, .tm-full > div {{ padding-left: 16px !important; padding-right: 16px !important; }}
  .tm-nav {{ gap: 4px 16px !important; font-size: 13px !important; }}
  .tm-footer > div:first-child {{ grid-template-columns: 1fr 1fr !important; }}
  .tm-footer > div:first-child > div:first-child {{ grid-column: 1 / -1; }}
  .tm-hero {{ padding-top: 104px; }}
  .tm-head > div {{ padding-top: 8px !important; padding-bottom: 8px !important; }}
  .tm-hero {{ -webkit-mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 70px), transparent 100%);
    mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 70px), transparent 100%); }}
  .stApp [class*="st-key-card_"] {{ padding: 18px 16px; }}
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
#tm-ring {{ position: fixed; left: 0; top: 0; width: 34px; height: 34px; margin: -17px 0 0 -17px; box-sizing: border-box;
  border-radius: 50%; border: 1.5px solid {t['primary']}; pointer-events: none; z-index: 100000; opacity: 0;
  transition: width .22s cubic-bezier(.2,.7,.2,1), height .22s cubic-bezier(.2,.7,.2,1), margin .22s cubic-bezier(.2,.7,.2,1),
  background-color .22s, opacity .25s; will-change: transform; }}
#tm-ring.hot {{ width: 48px; height: 48px; margin: -24px 0 0 -24px; background-color: rgba(156,201,255,0.12); }}
#tm-ring.down {{ width: 24px; height: 24px; margin: -12px 0 0 -12px; }}
#tm-ring.text {{ opacity: 0 !important; }}
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
  .tm-load-mark .tm-draw, .tm-load-mark .tm-core, .tm-splash-bar span {{ animation: none; stroke-dasharray: none; }}
  .sh-ray,.sh-star,.sh-dot,.sh-loop,.sh-flare,.sh-drift,.sh-flow,.sh-d1,.sh-d2,.sh-d3,.sh-kb,.sh-p2,.sh-earth-glow {{ animation: none; }}
  .tm-card, #tm-ring {{ transition: none; }} .tm-card:hover {{ transform: none; }}
}}
</style>"""


CLIENT_JS = """<script>
(function () {
  // Streamlit replaces this helper frame on every rerun, and handlers created by a replaced frame stop running.
  // So each run removes the previous run's timer and handlers (kept on the page itself) and attaches fresh ones.
  const w = window.parent, d = w.document;
  if (w.__tmTimer) { w.clearInterval(w.__tmTimer); }
  for (const [type, fn] of Object.entries(w.__tmHandlers || {})) { d.removeEventListener(type, fn); }
  w.__tmHandlers = {};
  if (w.__tmFrame) { w.cancelAnimationFrame(w.__tmFrame); }

  const tick = () => {
    const pk = new Date(Date.now() + 5 * 3600 * 1000).toISOString().slice(11, 19);   // Pakistan: UTC+5, no DST
    d.querySelectorAll('.tm-clock-pk').forEach(e => { e.textContent = pk; });
  };
  w.__tmTimer = w.setInterval(tick, 1000); tick();

  const fine = w.matchMedia('(hover: hover) and (pointer: fine)').matches;
  const calm = w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!fine) { return; }
  let r = d.getElementById('tm-ring');
  if (!r) { r = d.createElement('div'); r.id = 'tm-ring'; d.body.appendChild(r); }
  const st = w.__tmRing || (w.__tmRing = {mx: -100, my: -100, rx: -100, ry: -100});
  st.rx = st.mx; st.ry = st.my;                       // start at the pointer, no glide from an old position
  const ease = calm ? 1 : 0.2;                        // the ring eases behind the pointer
  const step = () => {
    st.rx += (st.mx - st.rx) * ease; st.ry += (st.my - st.ry) * ease;
    r.style.transform = 'translate3d(' + st.rx + 'px,' + st.ry + 'px,0)';
    w.__tmFrame = (Math.abs(st.mx - st.rx) > 0.1 || Math.abs(st.my - st.ry) > 0.1) ? w.requestAnimationFrame(step) : 0;
  };
  const on = (type, fn) => { d.addEventListener(type, fn); w.__tmHandlers[type] = fn; };
  on('mousemove', e => {
    st.mx = e.clientX; st.my = e.clientY; r.style.opacity = '1';
    const tg = e.target && e.target.closest ? e.target : null;
    r.classList.toggle('hot', !!(tg && tg.closest('a, button, label, [role=button], [role=tab], summary, [data-baseweb=select]')));
    r.classList.toggle('text', !!(tg && tg.closest('input, textarea')));
    if (!w.__tmFrame) { w.__tmFrame = w.requestAnimationFrame(step); }
  });
  on('mousedown', () => r.classList.add('down'));
  on('mouseup', () => r.classList.remove('down'));
  on('mouseleave', () => { r.style.opacity = '0'; });
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
