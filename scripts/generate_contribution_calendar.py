#!/usr/bin/env python3
"""Generate an isometric SVG from the GitHub contribution calendar."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

COLORS = {
    "FIRST_QUARTILE": ("#9be9a8", "#68b77a", "#3b8a50"),
    "SECOND_QUARTILE": ("#40c463", "#279e47", "#1d6e34"),
    "THIRD_QUARTILE": ("#30a14e", "#23813e", "#165d2a"),
    "FOURTH_QUARTILE": ("#216e39", "#18582e", "#104322"),
}


def contribution_days(username: str, token: str, start: datetime, end: datetime) -> dict[str, tuple[int, str]]:
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({
            "query": QUERY,
            "variables": {"login": username, "from": start.isoformat(), "to": end.isoformat()},
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"][0]["message"])

    weeks = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {
        day["date"]: (day["contributionCount"], day["contributionLevel"])
        for week in weeks
        for day in week["contributionDays"]
    }


def render_svg(username: str, days: list[tuple[int, str]], first_weekday: int) -> str:
    counts = [count for count, _ in days]
    peak = max(counts)
    current = best = 0
    for count in counts:
        current = current + 1 if count else 0
        best = max(best, current)
    average = sum(counts) / len(counts)

    tiles = []
    for index, (count, level) in enumerate(days, start=first_weekday):
        week, weekday = divmod(index, 7)
        x = 132 + (week - weekday) * 15
        y = 104 + (week + weekday) * 8
        height = max(3, round(61 * count / peak)) if count else 0
        top = y - height
        if height:
            fill, left, right = COLORS[level]
            tiles.extend((
                f'<path fill="{left}" d="M{x - 15} {top + 8}L{x} {top + 16}V{y + 16}L{x - 15} {y + 8}Z"/>',
                f'<path fill="{right}" d="M{x} {top + 16}L{x + 15} {top + 8}V{y + 8}L{x} {y + 16}Z"/>',
            ))
        else:
            fill = "var(--empty)"
        tiles.append(
            f'<path class="tile" fill="{fill}" d="M{x} {top}l15 8-15 8-15-8Z"/>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="620" viewBox="0 0 1000 620" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(username)} contributions calendar</title>
  <desc id="desc">An isometric view of the past year of GitHub contributions. Taller blocks indicate more activity.</desc>
  <style>
    :root{{--heading:#79c0ff;--label:#adbac7;--value:#e6edf3;--rule:#30363d;--empty:#e6ebf0;--grid:#8c959f}}
    @media(prefers-color-scheme:light){{:root{{--heading:#0969da;--label:#57606a;--value:#1f2328;--rule:#d0d7de;--empty:#eaeef2}}}}
    text{{font-family:system-ui,"Segoe UI",sans-serif;fill:var(--label)}}
    .title,.group-title{{font-weight:650;fill:var(--heading)}}
    .title{{font-size:32px}}
    .group-title,.stat-label{{font-size:21px}}
    .stat-value{{font-size:34px;font-weight:650;font-variant-numeric:tabular-nums;fill:var(--value)}}
    .stat-unit{{font-size:18px;font-weight:500;fill:var(--label)}}
    .stat-rule{{fill:none;stroke:var(--rule)}}
    .tile{{stroke:var(--grid);stroke-opacity:.45;stroke-width:.55;stroke-linejoin:round}}
  </style>
  <text class="title" x="28" y="48">Contribution calendar</text>
  {''.join(tiles)}
  <g transform="translate(558 87)">
    <path class="stat-rule" d="M0 15h367 M174 31v111"/>
    <g>
      <text class="group-title">Streaks</text>
      <text class="stat-label" y="43">Current streak</text>
      <text class="stat-value" y="76">{current}<tspan class="stat-unit" dx="5"> day{'s' if current != 1 else ''}</tspan></text>
      <text class="stat-label" y="109">Best streak</text>
      <text class="stat-value" y="142">{best}<tspan class="stat-unit" dx="5"> day{'s' if best != 1 else ''}</tspan></text>
    </g>
    <g transform="translate(195 0)">
      <text class="group-title">Daily activity</text>
      <text class="stat-label" y="43">Highest in a day</text>
      <text class="stat-value" y="76">{peak}</text>
      <text class="stat-label" y="109">Daily average</text>
      <text class="stat-value" y="142">{average:.2f}</text>
    </g>
  </g>
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=364)
    calendar = contribution_days(args.username, os.environ["GITHUB_TOKEN"], start, end)
    days = [calendar.get((start.date() + timedelta(days=index)).isoformat(), (0, "NONE")) for index in range(365)]
    first_weekday = (start.weekday() + 1) % 7

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(args.username, days, first_weekday), encoding="utf-8")


if __name__ == "__main__":
    main()
