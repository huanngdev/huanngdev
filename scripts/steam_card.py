"""Render an animated Steam profile card (assets/steam-card.svg).

Uses only the public Steam community pages, so no API key is needed.
Images are inlined as base64 because GitHub's image proxy blocks
external resources referenced from inside an SVG.
"""

import base64
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

STEAM_ID = "76561199208466836"
PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"
OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "steam-card.svg"
HEADERS = {"User-Agent": "Mozilla/5.0 (profile-readme-bot)", "Accept-Language": "en-US,en"}

WIDTH, HEIGHT = 840, 330
STATE_COLORS = {"online": "#57cbde", "in-game": "#90ba3c", "offline": "#8f98a0"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def data_uri(url: str) -> str:
    try:
        raw = fetch(url)
    except Exception as exc:  # a missing image should not break the card
        print(f"warn: image {url}: {exc}", file=sys.stderr)
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def parse_profile():
    root = ET.fromstring(fetch(PROFILE_URL + "?xml=1"))
    get = lambda tag: (root.findtext(tag) or "").strip()
    page = fetch(PROFILE_URL).decode("utf-8", "replace")

    level = re.search(r'class="friendPlayerLevelNum">(\d+)', page)
    counts = {}
    for label, total in re.findall(
        r'count_link_label">([^<]+)</span>(?:\s|&nbsp;)*<span class="profile_count_link_total">\s*([\d,]+)',
        page,
    ):
        counts[label.strip().lower()] = total.replace(",", "")

    games = []
    for block in re.split(r'<div class="recent_game">', page)[1:4]:
        name = re.search(r'class="game_name"\s*>\s*<a[^>]*>([^<]+)', block)
        details = re.search(r'game_info_details">(.*?)</div>', block, re.S)
        capsule = re.search(r'class="game_capsule" src="([^"]+)"', block)
        if not name:
            continue
        info = " ".join(re.sub(r"<[^>]+>", " ", details.group(1)).split()) if details else ""
        hours = re.search(r"([\d.,]+) hrs on record", info)
        played = re.search(r"last played on (.+)$", info)
        games.append(
            {
                "name": html.unescape(name.group(1).strip()),
                "hours": hours.group(1) if hours else "–",
                "played": "Currently in-game" if "currently in-game" in info.lower()
                else (f"Last played {played.group(1)}" if played else ""),
                "capsule": data_uri(html.unescape(capsule.group(1))) if capsule else "",
            }
        )

    return {
        "name": get("steamID"),
        "state": get("onlineState") or "offline",
        "status": get("stateMessage") or "Offline",
        "since": get("memberSince"),
        "location": get("location"),
        "avatar": data_uri(get("avatarMedium")),
        "level": level.group(1) if level else "?",
        "games": counts.get("games", "–"),
        "badges": counts.get("badges", "–"),
        "friends": counts.get("friends", "–"),
        "recent": games,
    }


def render(p) -> str:
    dot = STATE_COLORS.get(p["state"], STATE_COLORS["offline"])
    status = re.sub(r"<[^>]+>", " ", p["status"])
    status = clip(" ".join(status.split()), 40)

    stats = [("LEVEL", p["level"]), ("GAMES", p["games"]), ("BADGES", p["badges"]), ("FRIENDS", p["friends"])]
    stat_svg = ""
    for i, (label, value) in enumerate(stats):
        x = 470 + i * 88
        stat_svg += f"""
    <g class="fade" style="animation-delay:{0.25 + i * 0.12:.2f}s">
      <text x="{x}" y="58" class="stat">{esc(value)}</text>
      <text x="{x}" y="76" class="label">{label}</text>
    </g>"""

    rows = ""
    for i, g in enumerate(p["recent"]):
        y = 132 + i * 62
        capsule = (
            f'<image href="{g["capsule"]}" x="28" y="{y}" width="134" height="50" clip-path="url(#cap{i})" preserveAspectRatio="xMidYMid slice"/>'
            if g["capsule"] else f'<rect x="28" y="{y}" width="134" height="50" rx="4" fill="#2a475e"/>'
        )
        rows += f"""
    <g class="slide" style="animation-delay:{0.6 + i * 0.18:.2f}s">
      <rect x="20" y="{y - 6}" width="{WIDTH - 40}" height="62" rx="8" class="row"/>
      {capsule}
      <clipPath id="cap{i}"><rect x="28" y="{y}" width="134" height="50" rx="4"/></clipPath>
      <text x="180" y="{y + 21}" class="game">{esc(clip(g["name"], 46))}</text>
      <text x="180" y="{y + 41}" class="muted">{esc(g["played"])}</text>
      <text x="{WIDTH - 36}" y="{y + 31}" class="hours" text-anchor="end">{esc(g["hours"])} hrs</text>
    </g>"""
    if not p["recent"]:
        rows = '<text x="28" y="170" class="muted">No recent activity</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="t">
  <title id="t">Steam profile of {esc(p["name"])}: level {esc(p["level"])}, {esc(p["games"])} games</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#171a21"/>
      <stop offset=".55" stop-color="#1b2838"/>
      <stop offset="1" stop-color="#2a1f45"/>
    </linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#66c0f4"/>
      <stop offset=".5" stop-color="#a78bfa"/>
      <stop offset="1" stop-color="#66c0f4"/>
      <animateTransform attributeName="gradientTransform" type="translate" values="-1 0;1 0" dur="6s" repeatCount="indefinite"/>
    </linearGradient>
    <clipPath id="avatar"><rect x="24" y="22" width="64" height="64" rx="10"/></clipPath>
  </defs>
  <style>
    text {{ font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; }}
    .name {{ fill: #fff; font-size: 22px; font-weight: 700; }}
    .muted {{ fill: #8f98a0; font-size: 12.5px; }}
    .status {{ fill: {dot}; font-size: 13px; font-weight: 600; }}
    .stat {{ fill: #66c0f4; font-size: 22px; font-weight: 700; text-anchor: middle; }}
    .label {{ fill: #8f98a0; font-size: 10px; letter-spacing: 1.5px; text-anchor: middle; }}
    .section {{ fill: #c7d5e0; font-size: 11px; letter-spacing: 2px; font-weight: 600; }}
    .game {{ fill: #e6edf3; font-size: 15px; font-weight: 600; }}
    .hours {{ fill: #a78bfa; font-size: 15px; font-weight: 700; }}
    .row {{ fill: #ffffff; fill-opacity: .035; }}
    .fade {{ animation: fade .6s ease-out backwards; }}
    .slide {{ animation: slide .6s ease-out backwards; }}
    .pulse {{ animation: pulse 2s ease-in-out infinite; transform-origin: 82px 80px; }}
    @keyframes fade {{ from {{ opacity: 0; }} }}
    @keyframes slide {{ from {{ opacity: 0; transform: translateX(-12px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}
    @media (prefers-reduced-motion: reduce) {{ .fade, .slide, .pulse {{ animation: none; opacity: 1; }} }}
  </style>
  <rect x="1" y="1" width="{WIDTH - 2}" height="{HEIGHT - 2}" rx="14" fill="url(#bg)" stroke="url(#edge)" stroke-width="2"/>
  {f'<image href="{p["avatar"]}" x="24" y="22" width="64" height="64" clip-path="url(#avatar)"/>' if p["avatar"] else ''}
  <rect x="24" y="22" width="64" height="64" rx="10" fill="none" stroke="{dot}" stroke-width="2"/>
  <circle class="pulse" cx="82" cy="80" r="6" fill="{dot}" stroke="#171a21" stroke-width="2"/>
  <g class="fade">
    <text x="104" y="46" class="name">{esc(clip(p["name"], 24))}</text>
    <text x="104" y="66" class="status">● {esc(status)}</text>
    <text x="104" y="84" class="muted">Member since {esc(p["since"])}</text>
  </g>
  <line x1="436" y1="30" x2="436" y2="82" stroke="#ffffff" stroke-opacity=".08"/>{stat_svg}
  <text x="24" y="114" class="section">RECENT ACTIVITY</text>
  <line x1="160" y1="110" x2="{WIDTH - 24}" y2="110" stroke="url(#edge)" stroke-opacity=".4"/>{rows}
</svg>
"""


def main():
    try:
        profile = parse_profile()
    except Exception as exc:
        print(f"error: could not read Steam profile: {exc}", file=sys.stderr)
        sys.exit(1)
    OUTPUT.write_text(render(profile), encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(profile['recent'])} recent games)")


if __name__ == "__main__":
    main()
