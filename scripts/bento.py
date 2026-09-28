#!/usr/bin/env python3
"""
Render the bento-grid tiles for the GitHub profile README.

    python scripts/bento.py               # live: GitHub calendar + Substack RSS
    python scripts/bento.py --sample      # offline demo data for the activity tile

Every tile is its own SVG so the README can arrange them as a grid and link
individual tiles. All tiles share one scale: 1200 viewBox units = full README
width, so a 400-unit tile goes in at width="33.3%". Each SVG carries a
transparent margin, which becomes the gap between tiles.

Standard library only (plus the font embedder next to this file).
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import random
import re
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from embed_fonts import embed

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "tiles"

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
STACK = ["Python", "SQL", "GCP", "Supabase", "Postgres", "Next.js", "MCP", "LLM agents", "NLP"]
FALLBACK_POSTS = [  # used only if the feed can't be reached
    ("2026-09-11", "Membaca Ulang Crash CUAN: Siapa yang Beli Waktu Semua Orang Jual?"),
    ("2026-09-09", "Lima Hari Auto Reject Atas (ARA), dan Apa yang Ada di Baliknya"),
]

# ── Design tokens ─────────────────────────────────────────────────────────────
TILE, BORDER, HAIR = "#0E1013", "#1D2128", "#171A20"
WHITE, MUTED, DIM = "#F4F7FB", "#8B93A1", "#565E6B"
BLUE, BLUE_DEEP = "#2F9BFF", "#0B4A8F"
FONT = "Geist, Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
M, R = 10, 28            # outer margin (half the gap) and corner radius


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def tile(name: str, w: int, h: int, body: str, label: str, fill: str = TILE,
         border: str = BORDER, extra_defs: str = "", css: str = "") -> None:
    iw, ih = w - 2 * M, h - 2 * M
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">
<defs>
<clipPath id="clip"><rect x="{M}" y="{M}" width="{iw}" height="{ih}" rx="{R}"/></clipPath>
{extra_defs}
<style>
text {{ font-family: {FONT}; }}
.lbl {{ fill:{MUTED}; font-size:17px; font-weight:500; }}
{css}
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


def pill(x, y, text, fg=WHITE, bg="#171B22", size=15, dot=None) -> str:
    w = len(text) * size * .56 + 32 + (16 if dot else 0)
    tx = x + 16 + (16 if dot else 0)
    d = f'<circle class="pulse" cx="{x+20}" cy="{y+17}" r="4.5" fill="{dot}"/>' if dot else ""
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="34" rx="17" fill="{bg}" stroke="{BORDER}"/>{d}'
            f'<text x="{tx:.0f}" y="{y+22}" fill="{fg}" font-size="{size}" font-weight="500">{esc(text)}</text>')


PULSE_CSS = (".pulse { animation: pulse 2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }"
             "@keyframes pulse { 50% { opacity:.35; transform: scale(1.5); } }")


# ── Tiles ─────────────────────────────────────────────────────────────────────
def hero():
    w, h = 800, 420
    body = f'''
<rect x="0" y="0" width="{w}" height="{h}" fill="url(#g1)"/>
{pill(46, 46, "AI Engineer · Kaji Kapital", dot=BLUE)}
<text x="46" y="214" fill="{WHITE}" font-size="76" font-weight="600" letter-spacing="-2.5">Thariq Adinegara</text>
<text x="48" y="276" fill="{MUTED}" font-size="30" font-weight="400" letter-spacing="-.4">Building AI systems for <tspan fill="{BLUE}" font-weight="500">capital markets.</tspan></text>
<line x1="48" y1="330" x2="{w-48}" y2="330" stroke="{HAIR}"/>
<text x="48" y="370" fill="{DIM}" font-size="17" font-weight="500">Data pipelines · research tooling · LLM agents</text>
<text x="{w-48}" y="370" text-anchor="end" fill="{DIM}" font-size="17" font-weight="500">@{USER}</text>'''
    tile("hero", w, h, body, "Thariq Adinegara — AI Engineer building AI systems for capital markets",
         extra_defs=glow("g1", "92%", "0%", "70%", .28), css=PULSE_CSS)


def location():
    w, h = 400, 420
    dots = []
    for gy in range(0, 9):
        for gx in range(0, 11):
            x, y = 46 + gx * 28, 52 + gy * 24
            dots.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="#2A303A"/>')
    jx, jy = 46 + 6 * 28, 52 + 5 * 24
    body = f'''
<rect width="{w}" height="{h}" fill="url(#g2)"/>
{''.join(dots)}
<circle class="ring" cx="{jx}" cy="{jy}" r="7" fill="none" stroke="{BLUE}" stroke-width="2"/>
<circle cx="{jx}" cy="{jy}" r="5" fill="{BLUE}"/>
<text x="46" y="324" fill="{WHITE}" font-size="34" font-weight="600" letter-spacing="-1">Jakarta</text>
<text x="46" y="358" fill="{MUTED}" font-size="18" font-weight="400">Indonesia · UTC+7</text>'''
    css = (".ring { animation: ring 2.4s ease-out infinite; transform-box: fill-box; transform-origin: center; }"
           "@keyframes ring { from { opacity:.9; transform: scale(1); } to { opacity:0; transform: scale(3.2); } }")
    tile("location", w, h, body, "Based in Jakarta, Indonesia (UTC+7)",
         extra_defs=glow("g2", "60%", "55%", "55%", .22), css=css)


def work():
    w, h = 600, 480
    rows = []
    for i, (name, desc) in enumerate(WORK):
        y = 132 + i * 64
        rows.append(
            f'<text x="46" y="{y}" fill="{BLUE}" font-size="15" font-weight="600">{i+1:02d}</text>'
            f'<text x="92" y="{y}" fill="{WHITE}" font-size="21" font-weight="500" letter-spacing="-.3">{esc(name)}</text>'
            f'<text x="92" y="{y+24}" fill="{MUTED}" font-size="15.5" font-weight="400">{esc(desc)}</text>')
        if i < len(WORK) - 1:
            rows.append(f'<line x1="92" y1="{y+42}" x2="{w-46}" y2="{y+42}" stroke="{HAIR}"/>')
    body = f'''
<text class="lbl" x="46" y="66">Selected work</text>
{pill(w-46-104, 42, "Private", fg=MUTED, size=14)}
{''.join(rows)}'''
    tile("work", w, h, body, "Selected work (private): " + "; ".join(n for n, _ in WORK))


def fetch_posts(n=3):
    try:
        req = urllib.request.Request(SUBSTACK_FEED, headers={"User-Agent": "profile-readme-bot"})
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        posts = []
        for item in root.iter("item"):
            t = item.findtext("title", "").strip()
            d = email.utils.parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
            posts.append((d, t))
        return posts[:n] or FALLBACK_POSTS
    except Exception as e:  # network hiccup: keep the tile rendering
        print(f"feed unavailable ({e}); using fallback posts")
        return FALLBACK_POSTS


def writing(posts):
    w, h = 600, 480
    items, y = [], 124
    for d, title in posts[:3]:
        lines = textwrap.wrap(title, 44)
        if len(lines) > 2:
            lines = lines[:2]
            lines[1] = lines[1][:41].rstrip() + "…"
        date = dt.date.fromisoformat(d).strftime("%d %b %Y")
        items.append(f'<text x="46" y="{y}" fill="{BLUE}" font-size="14.5" font-weight="500">{date}</text>')
        for j, ln in enumerate(lines):
            items.append(f'<text x="46" y="{y+30+j*28}" fill="{WHITE}" font-size="21" font-weight="500" letter-spacing="-.3">{esc(ln)}</text>')
        y += 30 + len(lines) * 28 + 34
    body = f'''
<rect width="{w}" height="{h}" fill="url(#g3)"/>
<text class="lbl" x="46" y="66">Latest writing</text>
<text x="{w-46}" y="66" text-anchor="end" fill="{WHITE}" font-size="17" font-weight="500">Substack ↗</text>
{''.join(items)}
<text x="46" y="{h-46}" fill="{DIM}" font-size="15" font-weight="400">IDX research notes · updated daily</text>'''
    tile("writing", w, h, body, "Latest writing on Substack: " + "; ".join(t for _, t in posts[:3]),
         extra_defs=glow("g3", "100%", "100%", "60%", .16))


def origin():
    w, h = 400, 300
    body = f'''
<text class="lbl" x="46" y="66">Background</text>
<text x="46" y="148" fill="{WHITE}" font-size="38" font-weight="600" letter-spacing="-1.2">Chem Eng <tspan fill="{BLUE}">→</tspan> AI</text>
<text x="46" y="200" fill="{MUTED}" font-size="17" font-weight="400">Bioprocess Engineering</text>
<text x="46" y="226" fill="{MUTED}" font-size="17" font-weight="400">Universitas Indonesia</text>'''
    tile("origin", w, h, body, "Background: Bioprocess Engineering, Universitas Indonesia, now AI engineering")


def stack():
    w, h = 400, 300
    chips, x, y = [], 46, 98
    for s in STACK:
        cw = len(s) * 8.6 + 28
        if x + cw > w - 40:
            x, y = 46, y + 46
        chips.append(f'<rect x="{x}" y="{y}" width="{cw:.0f}" height="34" rx="17" fill="#15181E" stroke="{BORDER}"/>'
                     f'<text x="{x+cw/2:.0f}" y="{y+22}" text-anchor="middle" fill="{WHITE}" font-size="15" font-weight="500">{esc(s)}</text>')
        x += cw + 8
    body = f'<text class="lbl" x="46" y="66">Stack</text>{"".join(chips)}'
    tile("stack", w, h, body, "Stack: " + ", ".join(STACK))


def link_tile(name, title, sub, glyph, accent: bool):
    w, h = 200, 300
    fg = "#FFFFFF" if accent else WHITE
    sub_c = "#D6E9FF" if accent else MUTED
    body = f'''
{glyph}
<text x="36" y="{h-80}" fill="{fg}" font-size="22" font-weight="600" letter-spacing="-.4">{title}</text>
<text x="36" y="{h-52}" fill="{sub_c}" font-size="15" font-weight="400">{sub} ↗</text>'''
    tile(name, w, h, body, f"{title} — {sub}", fill=BLUE if accent else TILE,
         border=BLUE if accent else BORDER)


def links():
    li = ('<rect x="36" y="44" width="46" height="46" rx="12" fill="#FFFFFF"/>'
          f'<text x="59" y="77" text-anchor="middle" fill="{BLUE}" font-size="26" font-weight="700">in</text>')
    ss = (f'<g transform="translate(36,44)"><rect width="46" height="46" rx="12" fill="#1A1E25" stroke="{BORDER}"/>'
          f'<rect x="13" y="12" width="20" height="3" fill="{BLUE}"/><rect x="13" y="19" width="20" height="3" fill="{BLUE}"/>'
          f'<path d="M13 26 H33 V36 L23 30.5 L13 36 Z" fill="{BLUE}"/></g>')
    link_tile("linkedin", "LinkedIn", "Connect", li, accent=True)
    link_tile("substack", "Substack", "Subscribe", ss, accent=False)


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
        raise SystemExit(f"GraphQL error: {p['errors']}")
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

    x0, x1, y0, y1 = 380, w - 46, 70, h - 76
    step = (x1 - x0) / max(1, len(totals))
    bw = step * .62
    bars = []
    for i, t in enumerate(totals):
        bh = max(3, (t / vmax) * (y1 - y0))
        x = x0 + i * step + (step - bw) / 2
        last = i == len(totals) - 1
        col = WHITE if last else "url(#bar)"
        bars.append(f'<rect class="b" style="animation-delay:{i*.018:.3f}s" x="{x:.1f}" y="{y1-bh:.1f}" '
                    f'width="{bw:.1f}" height="{bh:.1f}" rx="{min(3, bw/2):.1f}" fill="{col}"/>')
    months, prev = [], None
    for i, wk in enumerate(weeks):
        m = wk[0][0].month
        if m != prev and i % 1 == 0:
            if prev is not None:
                months.append(f'<text x="{x0 + i*step:.0f}" y="{h-44}" fill="{DIM}" font-size="13" font-weight="500">{wk[0][0]:%b}</text>')
            prev = m
    note = "Sample data" if sample else f"Updated {dt.date.today():%d %b %Y}"
    body = f'''
<text class="lbl" x="46" y="66">Contributions</text>
<text x="46" y="164" fill="{WHITE}" font-size="76" font-weight="600" letter-spacing="-3">{total:,}</text>
<text x="48" y="198" fill="{MUTED}" font-size="17" font-weight="400">in the last 12 months</text>
<text x="48" y="256" fill="{WHITE}" font-size="22" font-weight="600">{last30}</text>
<text x="48" y="280" fill="{DIM}" font-size="14" font-weight="500">last 30 days</text>
<text x="178" y="256" fill="{WHITE}" font-size="22" font-weight="600">{best}</text>
<text x="178" y="280" fill="{DIM}" font-size="14" font-weight="500">best week</text>
<line x1="{x0}" y1="{y1+.5}" x2="{x1}" y2="{y1+.5}" stroke="{HAIR}"/>
{''.join(bars)}
{''.join(months)}
<text x="{x1}" y="66" text-anchor="end" fill="{DIM}" font-size="14" font-weight="500">{note} · weekly</text>'''
    defs = (f'<linearGradient id="bar" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{BLUE}"/>'
            f'<stop offset="1" stop-color="{BLUE_DEEP}"/></linearGradient>')
    css = (".b { transform-box: fill-box; transform-origin: bottom; animation: grow .7s cubic-bezier(.2,.7,.2,1) both; }"
           "@keyframes grow { from { transform: scaleY(0); } }")
    tile("activity", w, h, body, f"{total} GitHub contributions in the last 12 months, shown as weekly bars",
         extra_defs=defs, css=css)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.getenv("GH_USER", USER))
    ap.add_argument("--sample", action="store_true", help="demo data for the activity tile")
    ap.add_argument("--offline", action="store_true", help="skip the Substack feed")
    ap.add_argument("--from-json", help="render activity from a saved snapshot {days:[[date,count],...]}")
    a = ap.parse_args()

    hero(); location(); work(); origin(); stack(); links()
    writing(FALLBACK_POSTS if a.offline else fetch_posts())
    if a.from_json:
        snap = json.loads(Path(a.from_json).read_text())
        days = [(dt.date.fromisoformat(d), c) for d, c in snap["days"]]
    elif a.sample:
        days = sample_days()
    else:
        tok = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not tok:
            raise SystemExit("Set GH_TOKEN or pass --sample")
        days = fetch_days(a.user, tok)
    activity(days, a.sample)
    print("tiles ->", ", ".join(sorted(p.stem for p in OUT.glob("*.svg"))))


if __name__ == "__main__":
    main()
