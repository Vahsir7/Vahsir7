"""Render a 12-month weekly contribution chart as an animated SVG.

Usage: GITHUB_TOKEN=... python scripts/contrib_graph.py <user> <out.svg>
"""
import datetime as dt
import json
import os
import sys
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        cal = json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        (w["contributionDays"][0]["date"], sum(d["contributionCount"] for d in w["contributionDays"]))
        for w in cal["weeks"]
    ]
    return cal["totalContributions"], weeks


def render(total, weeks):
    W, H = 900, 300
    left, right, top, bottom = 60, 30, 80, 50
    pw, ph = W - left - right, H - top - bottom
    peak = max(c for _, c in weeks) or 1
    step = pw / (len(weeks) - 1)
    pts = [(left + i * step, top + ph - c / peak * ph) for i, (_, c) in enumerate(weeks)]

    # Smooth path via Catmull-Rom to cubic Bezier.
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{min(c1[1], top + ph):.1f} {c2[0]:.1f},{min(c2[1], top + ph):.1f} {p2[0]:.1f},{p2[1]:.1f}"
    area = f"{d} L{pts[-1][0]:.1f},{top + ph} L{pts[0][0]:.1f},{top + ph} Z"

    grid = ""
    for i in range(5):
        y = top + ph * i / 4
        val = round(peak * (1 - i / 4))
        grid += f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" class="grid"/>'
        grid += f'<text x="{left - 12}" y="{y + 4:.1f}" class="axis" text-anchor="end">{val}</text>'

    months, seen = "", set()
    for i, (date, _) in enumerate(weeks):
        m = date[:7]
        if m not in seen and i > 0:
            label = dt.date.fromisoformat(date).strftime("%b")
            months += f'<text x="{left + i * step:.1f}" y="{H - 20}" class="axis" text-anchor="middle">{label}</text>'
        seen.add(m)

    best = max(range(len(weeks)), key=lambda i: weeks[i][1])
    bx, by = pts[best]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <style>
    .title {{ font: 22px Marcellus, Georgia, serif; fill: #e6ecff; }}
    .meta {{ font: 13px 'Courier New', monospace; fill: #64ffda; letter-spacing: 1px; }}
    .axis {{ font: 11px 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8892b0; }}
    .grid {{ stroke: #8892b0; stroke-opacity: 0.12; }}
    .line {{ fill: none; stroke: #64ffda; stroke-width: 2.2; stroke-linecap: round;
             stroke-dasharray: 3000; stroke-dashoffset: 3000; animation: draw 2.2s ease-out forwards; }}
    .area {{ fill: url(#g); opacity: 0; animation: fade 1.2s 1s ease-out forwards; }}
    .peak {{ fill: #ca66ff; opacity: 0; animation: fade 0.6s 2s ease-out forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes fade {{ to {{ opacity: 1; }} }}
  </style>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#64ffda" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#64ffda" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="14" fill="#020c1b"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#64ffda" stroke-opacity="0.2"/>
  <text x="{left}" y="38" class="meta">CONTRIBUTIONS · LAST 12 MONTHS</text>
  <text x="{left}" y="64" class="title">{total:,} contributions</text>
  {grid}{months}
  <path d="{area}" class="area"/>
  <path d="{d}" class="line"/>
  <circle cx="{bx:.1f}" cy="{by:.1f}" r="4.5" class="peak"/>
  <text x="{bx:.1f}" y="{by - 12:.1f}" class="axis peak" text-anchor="middle">{weeks[best][1]} / week</text>
</svg>
"""


if __name__ == "__main__":
    login, out = sys.argv[1], sys.argv[2]
    total, weeks = fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(render(total, weeks))
