#!/usr/bin/env python3
"""
Render the bento-grid tiles for the GitHub profile README.

    python scripts/bento.py               # live: GitHub calendar + Substack RSS
    python scripts/bento.py --sample      # demo data, written to .tiles-preview/ (never to assets/)

Every tile is its own SVG so the README can arrange them as a grid and link
individual tiles. All tiles share one scale: 1200 viewBox units = full README
width, so a 400-unit tile goes in at width="33.3%". Each SVG carries a
transparent margin, which becomes the gap between tiles.

Type floor: GitHub shows the README in an ~830px column (scale 0.69), so no
text goes below 17 units (~12px) and reading text stays at 19+ units.

If a live source fails, the last good tile is kept rather than replaced with
stale or invented data. The README's alt text for the live tiles is rewritten
on each run so screen readers get the same facts as the image.

Standard library only (plus the font embedder next to this file).
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import math
import os
import random
import re
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from embed_fonts import embed

ROOT = Path(__file__).resolve().parent.parent
TILES = ROOT / "assets" / "tiles"
PREVIEW = ROOT / ".tiles-preview"
README = ROOT / "README.md"
OUT = TILES  # switched to PREVIEW for --sample runs

# ── Config: edit content here ─────────────────────────────────────────────────
USER = "thariqabe666"
SUBSTACK_FEED = "https://thariqadinegara.substack.com/feed"
WORK = [
    ("Sentiment Analyzer", "Market mood from retail-investor chatter"),
    ("PIT Universe DB", "Point-in-time equity universe for honest backtests"),
    ("Backtest Engine", "Strategy testing under realistic market constraints"),
    ("MCP Servers", "Market and flow data as tools for LLM agents"),
    ("Equity & Strategy Research", "Case studies, strategies and indicator validation"),
]
STACK = [  # (group, items)
    ("Data", ["Python", "SQL", "Postgres", "Supabase"]),
    ("AI", ["LLM agents", "MCP", "NLP"]),
    ("Cloud", ["GCP", "Next.js"]),
]
FALLBACK_POSTS = [  # only used when the feed fails AND no writing tile exists yet
    ("2026-09-11", "Membaca Ulang Crash CUAN: Siapa yang Beli Waktu Semua Orang Jual?"),
    ("2026-09-09", "Lima Hari Auto Reject Atas (ARA), dan Apa yang Ada di Baliknya"),
]
ID_WORDS = {"yang", "dan", "di", "dari", "ini", "itu", "untuk", "dengan", "apa", "siapa", "dalam",
            "ke", "pada", "tidak", "ada", "baliknya", "membaca", "ulang", "hari", "saham"}

# ── Design tokens ─────────────────────────────────────────────────────────────
TILE, BORDER, HAIR = "#0E1013", "#2A2F38", "#1C2027"
WHITE, MUTED, DIM = "#F4F7FB", "#8B93A1", "#7E8796"   # DIM 5.3:1, MUTED 6.2:1 on TILE
BLUE, BLUE_DEEP, BLUE_INK = "#2F9BFF", "#0B4A8F", "#1A6FD6"
FONT = "Geist, Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
M, R = 10, 28            # outer margin (half the gap) and corner radius
LBL = 20                 # tile label size

REDUCED_MOTION = "@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def text_w(s: str, size: float, weight: int = 500) -> float:
    """Rough Geist advance width; good enough to size pills and fit lines."""
    narrow, wide = set("ijlI.,:;'|!·()[] tfr1"), set("mwMW@%&")
    em = sum(.28 if c in narrow else .82 if c in wide else .64 if c.isupper() else .55 for c in s)
    return em * size * (1.03 if weight >= 600 else 1)


def fit(s: str, size: float, avail: float, floor: float = 17) -> float:
    """Largest size <= size that fits avail, but never below the type floor."""
    while size > floor and text_w(s, size) > avail:
        size -= .5
    return size


def tile(name: str, w: int, h: int, body: str, label: str, fill: str = TILE,
         border: str = BORDER, extra_defs: str = "", css: str = "") -> None:
    iw, ih = w - 2 * M, h - 2 * M
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">
<defs>
<clipPath id="clip"><rect x="{M}" y="{M}" width="{iw}" height="{ih}" rx="{R}"/></clipPath>
{extra_defs}
<style>
text {{ font-family: {FONT}; }}
.lbl {{ fill:{MUTED}; font-size:{LBL}px; font-weight:500; }}
{css}
{REDUCED_MOTION}
</style>
</defs>
<rect x="{M}" y="{M}" width="{iw}" height="{ih}" rx="{R}" fill="{fill}"/>
<g clip-path="url(#clip)">
{body}
</g>
<rect x="{M+.5}" y="{M+.5}" width="{iw-1}" height="{ih-1}" rx="{R}" fill="none" stroke="{border}"/>
</svg>
'''
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(embed(svg), encoding="utf-8")


def glow(id_: str, cx: str, cy: str, r: str, opacity: float = .35) -> str:
    return (f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}">'
            f'<stop offset="0" stop-color="{BLUE}" stop-opacity="{opacity}"/>'
            f'<stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></radialGradient>')


def pill(x, y, text, fg=WHITE, bg="#171B22", size=18, dot=None, anchor_right=False) -> tuple[str, float]:
    h, pad = size + 20, 18
    w = text_w(text, size) + 2 * pad + (18 if dot else 0)
    if anchor_right:
        x -= w
    tx = x + pad + (18 if dot else 0)
    d = f'<circle cx="{x+pad+4:.1f}" cy="{y+h/2:.1f}" r="5" fill="{dot}"/>' if dot else ""
    return (f'<rect x="{x:.1f}" y="{y}" width="{w:.0f}" height="{h}" rx="{h/2}" fill="{bg}" stroke="{BORDER}"/>{d}'
            f'<text x="{tx:.1f}" y="{y+h/2+size*.36:.1f}" fill="{fg}" font-size="{size}" font-weight="500">{esc(text)}</text>'), w


# ── Tiles ─────────────────────────────────────────────────────────────────────
HERO_LABEL = "Thariq Adinegara, AI Engineer at Kaji Kapital, building AI systems for capital markets"


def hero():
    w, h = 800, 420
    # No eyebrow pill above the name: the role is stated plainly in the footer row.
    body = f'''
<rect x="0" y="0" width="{w}" height="{h}" fill="url(#g1)"/>
<text x="44" y="200" fill="{WHITE}" font-size="76" font-weight="600" letter-spacing="-2.3">Thariq Adinegara</text>
<text x="47" y="258" fill="{MUTED}" font-size="32" font-weight="400" letter-spacing="-.6">Building AI systems for <tspan fill="{BLUE}" font-weight="500">capital markets.</tspan></text>
<line x1="47" y1="318" x2="{w-47}" y2="318" stroke="{HAIR}"/>
<text x="47" y="364" fill="{WHITE}" font-size="21" font-weight="500">AI Engineer at Kaji Kapital</text>
<text x="{w-47}" y="364" text-anchor="end" fill="{DIM}" font-size="19" font-weight="400">Data pipelines · research tooling · LLM agents</text>'''
    tile("hero", w, h, body, HERO_LABEL, extra_defs=glow("g1", "92%", "0%", "70%", .28))


def inside(x, y, ring) -> bool:
    """Even-odd point-in-polygon test."""
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


ORIGIN_LABEL = ("Background: Chemical engineering to AI. Bioprocess Engineering, Universitas Indonesia. "
                "Based in Jakarta, Indonesia (UTC+7)")


def origin():
    """Background story on top, a dot-matrix map of Indonesia with Jakarta pinned below."""
    w, h = 400, 420
    lon0, lon1, lat0, y0 = 94.6, 141.4, 6.4, 214   # map frame: west, east, north edge, top y
    x0, x1 = 40, w - 40
    k = (x1 - x0) / (lon1 - lon0)                  # px per degree, equirectangular
    proj = lambda lon, lat: (x0 + (lon - lon0) * k, y0 + (lat0 - lat) * k)
    rings = [[proj(*p) for p in r] for r in json.loads((Path(__file__).parent / "indonesia.json").read_text())]
    jx, jy = proj(106.85, -6.21)
    cx, cy, rx, ry = (x0 + x1) / 2, y0 + 56, (x1 - x0) / 2 + 6, 78

    dots, p = [], 5.0
    y = y0 - 6
    while y < y0 + 122:
        x = x0
        while x <= x1:
            if any(inside(x, y, r) for r in rings):
                d = math.hypot(x - jx, y - jy)
                col = "#6BB8FF" if d < 12 else ("#3E77B5" if d < 26 else "#56606F")
                dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.7" fill="{col}"/>')
            else:  # sea dots fade out towards the edge of an ellipse around the map
                o = 1 - math.hypot((x - cx) / rx, (y - cy) / ry)
                if o > .05:
                    dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r=".8" fill="#2A303A" opacity="{min(1, o * 1.6):.2f}"/>')
            x += p
        y += p
    body = f'''
<text class="lbl" x="46" y="66">Background</text>
<text x="45" y="126" fill="{WHITE}" font-size="40" font-weight="600" letter-spacing="-1.2">Chem Eng <tspan fill="{BLUE}">→</tspan> AI</text>
<text x="46" y="164" fill="{MUTED}" font-size="20" font-weight="400">Bioprocess Engineering</text>
<text x="46" y="191" fill="{MUTED}" font-size="20" font-weight="400">Universitas Indonesia</text>
{''.join(dots)}
<circle class="ring" cx="{jx:.1f}" cy="{jy:.1f}" r="6" fill="none" stroke="{BLUE}" stroke-width="2"/>
<circle cx="{jx:.1f}" cy="{jy:.1f}" r="4.5" fill="{BLUE}" stroke="{TILE}" stroke-width="2"/>
<text x="46" y="376" fill="{WHITE}" font-size="22" font-weight="600" letter-spacing="-.3">Jakarta<tspan fill="{MUTED}" font-weight="400">, Indonesia · UTC+7</tspan></text>'''
    css = (".ring { animation: ring 2.4s ease-out infinite; transform-box: fill-box; transform-origin: center; }"
           "@keyframes ring { from { opacity:.9; transform: scale(1); } to { opacity:0; transform: scale(3.2); } }")
    tile("origin", w, h, body, ORIGIN_LABEL, css=css)


def work():
    w, h = 600, 480
    avail = w - 92
    rows = []
    for i, (name, desc) in enumerate(WORK):
        y = 128 + i * 70
        rows.append(
            f'<text x="46" y="{y}" fill="{WHITE}" font-size="{fit(name, 24, avail)}" font-weight="500" letter-spacing="-.3">{esc(name)}</text>'
            f'<text x="46" y="{y+28}" fill="{MUTED}" font-size="{fit(desc, 19, avail)}" font-weight="400">{esc(desc)}</text>')
        if i < len(WORK) - 1:
            rows.append(f'<line x1="46" y1="{y+47}" x2="{w-46}" y2="{y+47}" stroke="{HAIR}"/>')
    badge, _ = pill(w - 46, 40, "Private", fg=MUTED, size=17, anchor_right=True)
    body = f'''
<text class="lbl" x="46" y="66">Selected work</text>
{badge}
{''.join(rows)}'''
    tile("work", w, h, body, "Selected work, all private: " + "; ".join(f"{n} ({d})" for n, d in WORK))


def fetch_posts(n=3):
    """Latest posts, or None when the feed can't be read (caller keeps the last good tile)."""
    try:
        req = urllib.request.Request(SUBSTACK_FEED, headers={"User-Agent": "profile-readme-bot"})
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        posts = []
        for item in root.iter("item"):
            t = item.findtext("title", "").strip()
            d = email.utils.parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
            posts.append((d, t))
        return posts[:n] or None
    except Exception as e:  # network hiccup: keep the last good tile
        print(f"feed unavailable ({e})")
        return None


def is_indonesian(title: str) -> bool:
    return len(set(re.findall(r"[a-z]+", title.lower())) & ID_WORDS) >= 2


def writing(posts, archive=False):
    w, h = 600, 480
    bottom, wrap = h - 46, 40
    items, y, shown = [], 118, []
    for d, title in posts[:3]:
        lines = textwrap.wrap(title, wrap)
        for n in (2, 1):  # try two lines, then clamp to one so the post still fits
            ln = lines[:n]
            if len(lines) > n:
                ln[-1] = ln[-1][:wrap - 2].rstrip() + "…"
            if y + 30 + (len(ln) - 1) * 30 <= bottom:
                break
        else:
            break
        date = dt.date.fromisoformat(d).strftime("%d %b %Y")
        lang = f'<tspan fill="{MUTED}" font-weight="400"> · Bahasa Indonesia</tspan>' if is_indonesian(title) else ""
        items.append(f'<text x="46" y="{y}" fill="{BLUE}" font-size="17" font-weight="500">{date}{lang}</text>')
        for j, t in enumerate(ln):
            items.append(f'<text x="46" y="{y+30+j*30}" fill="{WHITE}" font-size="23" font-weight="500" letter-spacing="-.3">{esc(t)}</text>')
        shown.append(title)
        y += 30 + (len(ln) - 1) * 30 + 46
    head = "From the archive" if archive else "Latest writing"
    body = f'''
<rect width="{w}" height="{h}" fill="url(#g3)"/>
<text class="lbl" x="46" y="66">{head}</text>
<text x="{w-46}" y="66" text-anchor="end" fill="{WHITE}" font-size="20" font-weight="500">Substack ↗</text>
{''.join(items)}'''
    label = f"{head} on Substack: " + "; ".join(shown)
    tile("writing", w, h, body, label, extra_defs=glow("g3", "100%", "100%", "60%", .16))
    return label


def stack():
    w, h = 600, 300
    rows, y = [], 96
    for group, items in STACK:
        rows.append(f'<text x="46" y="{y+26}" fill="{MUTED}" font-size="18" font-weight="500">{esc(group)}</text>')
        x = 132
        for s in items:
            cw = text_w(s, 18) + 32
            rows.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.0f}" height="40" rx="20" fill="#15181E" stroke="{BORDER}"/>'
                        f'<text x="{x+cw/2:.1f}" y="{y+26.5}" text-anchor="middle" fill="{WHITE}" font-size="18" font-weight="500">{esc(s)}</text>')
            x += cw + 10
        y += 58
    body = f'<text class="lbl" x="46" y="66">Stack</text>{"".join(rows)}'
    tile("stack", w, h, body, "Stack. " + ". ".join(f"{g}: {', '.join(i)}" for g, i in STACK))


def link_tile(name, title, sub, glyph):
    w, h = 300, 300
    body = f'''
{glyph}
<text x="40" y="{h-84}" fill="{WHITE}" font-size="30" font-weight="600" letter-spacing="-.6">{title}</text>
<text x="40" y="{h-50}" fill="{MUTED}" font-size="20" font-weight="400">{sub} ↗</text>'''
    tile(name, w, h, body, f"{title}: {sub}")


def links():
    # LinkedIn mark drawn as shapes (dot, stem, arch), not typed text.
    li = (f'<g transform="translate(40,42)"><rect width="56" height="56" rx="14" fill="{BLUE_INK}"/>'
          '<circle cx="17.5" cy="17" r="4" fill="#FFFFFF"/>'
          '<rect x="14" y="24" width="7" height="19" rx="1" fill="#FFFFFF"/>'
          '<path d="M25.5 24h6.6v2.7c1.1-1.9 3.2-3.2 6-3.2 4.6 0 6.4 2.9 6.4 7.6V43h-7V32.3c0-2.3-.8-3.6-2.8-3.6'
          '-2.1 0-3.3 1.5-3.3 3.9V43h-6.9z" fill="#FFFFFF"/></g>')
    ss = (f'<g transform="translate(40,42)"><rect width="56" height="56" rx="14" fill="#1A1E25" stroke="{BORDER}"/>'
          f'<rect x="16" y="15" width="24" height="3.5" fill="{BLUE}"/><rect x="16" y="23" width="24" height="3.5" fill="{BLUE}"/>'
          f'<path d="M16 31 H40 V43 L28 36.5 L16 43 Z" fill="{BLUE}"/></g>')
    link_tile("linkedin", "LinkedIn", "Connect", li)
    link_tile("substack", "Substack", "Subscribe", ss)


# ── Activity ─────────────────────────────────────────────────────────────────
QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def fetch_days(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        p = json.load(r)
    if "errors" in p:
        raise RuntimeError(f"GraphQL error: {p['errors']}")
    weeks = p["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def sample_days(seed=7, target=720):
    rng = random.Random(seed)
    end = dt.date.today()
    start = end - dt.timedelta(days=370)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    n = (end - start).days + 1
    days = []
    for i in range(n):
        d, ph = start + dt.timedelta(days=i), i / n
        base = .4 + 3.2 * ph ** 1.6
        c = max(0, int(rng.gauss(base, base * .9) * (.45 if d.weekday() >= 5 else 1)
                       + (6 * rng.random() if rng.random() < .08 + .1 * ph else 0)))
        days.append((d, 0 if rng.random() < .35 - .2 * ph else c))
    k = target / max(1, sum(c for _, c in days))
    return [(d, round(c * k)) for d, c in days]


def activity(days, sample):
    w, h = 1200, 340
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)][-52:]
    totals = [sum(c for _, c in wk) for wk in weeks]
    total = sum(c for _, c in days)  # calendar already spans ~1 year, same as GitHub's headline
    last30 = sum(c for _, c in days[-30:])
    best = max(totals) if totals else 0
    vmax = max(best, 1)
    partial = bool(weeks) and len(weeks[-1]) < 7

    x0, x1, y0, y1 = 400, w - 46, 92, h - 82
    step = (x1 - x0) / max(1, len(totals))
    bw = step * .62
    bars = []
    if total:
        for i, t in enumerate(totals):
            bh = max(3, (t / vmax) * (y1 - y0))
            x = x0 + i * step + (step - bw) / 2
            op = ' opacity=".45"' if partial and i == len(totals) - 1 else ""  # week still in progress
            bars.append(f'<rect class="b" style="animation-delay:{i*.018:.3f}s" x="{x:.1f}" y="{y1-bh:.1f}" '
                        f'width="{bw:.1f}" height="{bh:.1f}" rx="{min(3, bw/2):.1f}" fill="url(#bar)"{op}/>')
    else:
        bars.append(f'<text x="{(x0+x1)/2:.0f}" y="{(y0+y1)/2:.0f}" text-anchor="middle" fill="{MUTED}" '
                    f'font-size="20">No public contributions in the last 12 months</text>')
    months, prev = [], None
    for i, wk in enumerate(weeks):
        m = wk[0][0].month
        if m != prev:
            if prev is not None and i * step < (x1 - x0) - 30:  # skip the partial first month and edge overflow
                months.append(f'<text x="{x0 + i*step:.0f}" y="{h-48}" fill="{DIM}" font-size="17" font-weight="500">{wk[0][0]:%b}</text>')
            prev = m
    note = "Sample data" if sample else f"Updated {dt.date.today():%d %b %Y}"
    body = f'''
<text class="lbl" x="46" y="66">Contributions</text>
<text x="44" y="164" fill="{WHITE}" font-size="76" font-weight="600" letter-spacing="-2.5">{total:,}</text>
<text x="47" y="198" fill="{MUTED}" font-size="20" font-weight="400">in the last 12 months</text>
<text x="47" y="256" fill="{WHITE}" font-size="28" font-weight="600">{last30:,}</text>
<text x="47" y="284" fill="{DIM}" font-size="18" font-weight="500">last 30 days</text>
<text x="200" y="256" fill="{WHITE}" font-size="28" font-weight="600">{best:,}</text>
<text x="200" y="284" fill="{DIM}" font-size="18" font-weight="500">best week</text>
<line x1="{x0}" y1="{y1+.5}" x2="{x1}" y2="{y1+.5}" stroke="{HAIR}"/>
{''.join(bars)}
{''.join(months)}
<text x="{x1}" y="66" text-anchor="end" fill="{DIM}" font-size="18" font-weight="500">{note} · weekly</text>'''
    defs = (f'<linearGradient id="bar" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{BLUE}"/>'
            f'<stop offset="1" stop-color="{BLUE_DEEP}"/></linearGradient>')
    css = (".b { transform-box: fill-box; transform-origin: bottom; animation: grow .7s cubic-bezier(.2,.7,.2,1) both; }"
           "@keyframes grow { from { transform: scaleY(0); } }")
    label = (f"{total:,} GitHub contributions in the last 12 months, {last30:,} in the last 30 days, "
             f"best week {best:,}, shown as weekly bars")
    tile("activity", w, h, body, label, extra_defs=defs, css=css)
    return label


# ── README alt text ───────────────────────────────────────────────────────────
def set_alt(src: str, alt: str) -> None:
    """Keep the README's alt text for a live tile in step with what the tile shows."""
    if not README.exists():
        return
    md = README.read_text(encoding="utf-8")
    pat = re.compile(r'(<img src="assets/tiles/' + re.escape(src) + r'"[^>]*?alt=")[^"]*(")')
    new = pat.sub(lambda m: m.group(1) + esc(alt) + m.group(2), md)
    if new != md:
        README.write_text(new, encoding="utf-8")


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.getenv("GH_USER", USER))
    ap.add_argument("--sample", action="store_true", help="demo data; renders into .tiles-preview/, never assets/")
    ap.add_argument("--offline", action="store_true", help="skip the Substack feed (keeps the current writing tile)")
    ap.add_argument("--from-json", help="render activity from a saved snapshot {days:[[date,count],...]}")
    a = ap.parse_args()
    live = not a.sample
    if a.sample:
        OUT = PREVIEW
        print(f"sample mode: writing tiles to {PREVIEW} (assets/tiles untouched)")

    hero(); origin(); work(); stack(); links()

    posts = None if a.offline else fetch_posts()
    if posts:
        label = writing(posts)
        if live:
            set_alt("writing.svg", label)
    elif (OUT / "writing.svg").exists():
        print("writing: keeping the last good tile")
    else:
        writing(FALLBACK_POSTS, archive=True)

    days = None
    if a.from_json:
        snap = json.loads(Path(a.from_json).read_text())
        days = [(dt.date.fromisoformat(d), c) for d, c in snap["days"]]
    elif a.sample:
        days = sample_days()
    else:
        tok = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not tok:
            raise SystemExit("Set GH_TOKEN, or pass --sample to preview with demo data")
        try:
            days = fetch_days(a.user, tok)
        except Exception as e:  # keep the last good tile instead of failing the whole run
            print(f"contributions unavailable ({e}); keeping the last good tile")
    if days is not None:
        label = activity(days, a.sample)
        if live:
            set_alt("activity.svg", label)
    print("tiles ->", ", ".join(sorted(p.stem for p in OUT.glob("*.svg"))))


if __name__ == "__main__":
    main()
