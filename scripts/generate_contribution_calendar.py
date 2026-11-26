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
    :root{{--heading:#58a6ff;--text:#adbac7;--empty:#e6ebf0;--grid:#8c959f}}
    @media(prefers-color-scheme:light){{:root{{--heading:#0969da;--text:#57606a;--empty:#eaeef2;--grid:#8c959f}}}}
    text{{font:24px system-ui,sans-serif;fill:var(--text)}}
    .heading{{font-size:27px;font-weight:600;fill:var(--heading)}}
    .title{{font-size:30px}}
    .tile{{stroke:var(--grid);stroke-opacity:.45;stroke-width:.55;stroke-linejoin:round}}
  </style>
  <text class="heading title" x="28" y="48">Contributions calendar</text>
  {''.join(tiles)}
  <g>
    <text class="heading" x="570" y="91">Contribution streaks</text>
    <text x="570" y="125">Current streak · {current} day{'s' if current != 1 else ''}</text>
    <text x="570" y="159">Best streak · {best} day{'s' if best != 1 else ''}</text>
    <text class="heading" x="570" y="197">Contributions per day</text>
    <text x="570" y="231">Highest in a day · {peak}</text>
    <text x="570" y="265">Daily average · {average:.2f}</text>
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
