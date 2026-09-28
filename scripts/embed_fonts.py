#!/usr/bin/env python3
"""
Inline the Geist subsets (assets/fonts/*.woff2) into an SVG as base64
@font-face rules, only for the weights the SVG actually uses.

GitHub's image proxy blocks external font URLs, but data: fonts inside the
SVG render, so the tiles look the same on every device.

Subsets cover Latin-1 plus a few symbols (· – — ’ “ ” • … → ↗). If tile text
needs other characters, regenerate the subsets with pyftsubset.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
START, END = "/*@fonts-start*/", "/*@fonts-end*/"


def _used_weights(svg: str) -> set[int]:
    found = {int(w) for w in re.findall(r'font-weight[=:]\s*"?(\d{3})', svg)} or {400}
    return {min(WEIGHTS, key=lambda k: abs(k - w)) for w in found} | {400}


def embed(svg: str) -> str:
    svg = re.sub(re.escape(START) + ".*?" + re.escape(END), "", svg, flags=re.S)
    rules = []
    for w in sorted(_used_weights(svg)):
        data = base64.b64encode((FONT_DIR / f"Geist-{WEIGHTS[w]}.subset.woff2").read_bytes()).decode()
        rules.append("@font-face{font-family:'Geist';font-style:normal;"
                     f"font-weight:{w};src:url(data:font/woff2;base64,{data}) format('woff2');}}")
    return svg.replace("<style>", "<style>" + START + "".join(rules) + END, 1)
