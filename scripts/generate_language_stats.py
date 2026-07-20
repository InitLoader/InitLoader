#!/usr/bin/env python3
"""Generate an animated SVG language overview from public GitHub repositories."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


COLORS = {
    "Assembly": "#6E4C13",
    "Batchfile": "#C1F12E",
    "C": "#A8B9CC",
    "C#": "#9B4F96",
    "C++": "#F34B7D",
    "CMake": "#DA3434",
    "CSS": "#663399",
    "HTML": "#E34C26",
    "Java": "#B07219",
    "JavaScript": "#F1E05A",
    "Pascal": "#E3F171",
    "PowerShell": "#012456",
    "Python": "#3572A5",
    "Shell": "#89E051",
    "Yacc": "#4B6C4B",
}


def github_json(url: str, token: str | None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "InitLoader-profile-visuals",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def repository_languages(username: str, token: str | None, include_forks: bool) -> tuple[dict[str, int], int]:
    totals: dict[str, int] = {}
    repository_count = 0
    page = 1
    while True:
        url = f"https://api.github.com/users/{quote(username)}/repos?type=owner&per_page=100&page={page}"
        repositories = github_json(url, token)
        if not isinstance(repositories, list) or not repositories:
            break
        for repository in repositories:
            if not isinstance(repository, dict) or repository.get("archived"):
                continue
            if repository.get("fork") and not include_forks:
                continue
            languages = github_json(str(repository["languages_url"]), token)
            if not isinstance(languages, dict) or not languages:
                continue
            repository_count += 1
            for language, byte_count in languages.items():
                totals[str(language)] = totals.get(str(language), 0) + int(byte_count)
        if len(repositories) < 100:
            break
        page += 1
    return totals, repository_count


def language_color(language: str) -> str:
    if language in COLORS:
        return COLORS[language]
    hue = int(hashlib.sha1(language.encode("utf-8")).hexdigest()[:4], 16) % 360
    return f"hsl({hue} 62% 58%)"


def format_size(byte_count: int) -> str:
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{byte_count} B"


def render_svg(username: str, totals: dict[str, int], repository_count: int, include_forks: bool) -> str:
    total_bytes = sum(totals.values())
    if not total_bytes:
        raise RuntimeError("No language data was returned by GitHub")

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    visible = ranked[:9]
    remainder = sum(value for _, value in ranked[9:])
    if remainder:
        visible.append(("Other", remainder))

    bar_x, bar_width = 70.0, 1060.0
    segments: list[str] = []
    cursor = bar_x
    for index, (language, byte_count) in enumerate(visible):
        width = bar_width * byte_count / total_bytes
        if index == len(visible) - 1:
            width = bar_x + bar_width - cursor
        segments.append(
            f'<rect x="{cursor:.2f}" y="150" width="{width:.2f}" height="20" '
            f'fill="{language_color(language)}" />'
        )
        cursor += width

    entries: list[str] = []
    for index, (language, byte_count) in enumerate(visible):
        column, row = divmod(index, 5)
        x = 90 + column * 550
        y = 218 + row * 42
        percent = byte_count / total_bytes * 100
        escaped = html.escape(language)
        delay = 0.85 + index * 0.1
        entries.append(
            f'<g class="entry" style="animation-delay:{delay:.2f}s">'
            f'<circle cx="{x}" cy="{y - 5}" r="6" fill="{language_color(language)}" />'
            f'<text class="language" x="{x + 18}" y="{y}">{escaped}</text>'
            f'<text class="percent" x="{x + 490}" y="{y}" text-anchor="end">{percent:.2f}%</text>'
            "</g>"
        )

    fork_note = "含 Fork · forks included" if include_forks else "不含 Fork · forks excluded"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="470" viewBox="0 0 1200 470" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(username)} language footprint</title>
  <desc id="desc">Animated language distribution by file size across public repositories</desc>
  <defs>
    <linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#22d3ee"/><stop offset=".5" stop-color="#8b5cf6"/><stop offset="1" stop-color="#ec4899"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <clipPath id="bar-shape"><rect x="70" y="150" width="1060" height="20" rx="10"/></clipPath>
    <clipPath id="bar-reveal"><rect x="70" y="148" width="0" height="24"><animate attributeName="width" from="0" to="1060" dur="1.5s" begin=".35s" fill="freeze" calcMode="spline" keySplines=".22 1 .36 1"/></rect></clipPath>
    <style>
      :root{{color-scheme:dark light;--bg:#0d1117;--panel:#111827;--text:#e6edf3;--muted:#8b98a9;--line:#263244}}
      @media(prefers-color-scheme:light){{:root{{--bg:#ffffff;--panel:#f8fafc;--text:#172033;--muted:#64748b;--line:#d8dee9}}}}
      text{{font-family:"Segoe UI",Inter,Arial,sans-serif}}
      .title{{fill:var(--text);font-size:28px;font-weight:700;letter-spacing:.4px}}
      .subtitle,.meta{{fill:var(--muted);font-size:15px}}
      .language{{fill:var(--text);font-size:18px;font-weight:600}}
      .percent{{fill:var(--muted);font-size:17px;font-variant-numeric:tabular-nums}}
      .fade,.entry{{opacity:0;animation:fade-in .65s cubic-bezier(.22,1,.36,1) forwards}}
      @keyframes fade-in{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
      @media(prefers-reduced-motion:reduce){{.fade,.entry{{opacity:1;animation:none}}}}
    </style>
  </defs>
  <rect x="2" y="2" width="1196" height="466" rx="22" fill="var(--bg)" stroke="url(#border)" stroke-width="2"/>
  <rect x="22" y="22" width="1156" height="426" rx="16" fill="var(--panel)" opacity=".62" stroke="var(--line)"/>
  <g class="fade" style="animation-delay:.05s">
    <text class="title" x="70" y="76">总体语言分布 / LANGUAGE FOOTPRINT</text>
    <text class="subtitle" x="70" y="108">公开仓库文件体积统计 · {repository_count} repositories · {html.escape(fork_note)}</text>
    <text class="meta" x="1130" y="76" text-anchor="end">{format_size(total_bytes)} TRACKED</text>
    <circle cx="1118" cy="105" r="5" fill="#22c55e" filter="url(#glow)"/><text class="meta" x="1105" y="110" text-anchor="end">SCAN COMPLETE</text>
  </g>
  <rect x="70" y="150" width="1060" height="20" rx="10" fill="var(--line)"/>
  <g clip-path="url(#bar-shape)"><g clip-path="url(#bar-reveal)">{''.join(segments)}</g></g>
  {''.join(entries)}
  <g class="fade" style="animation-delay:1.85s">
    <line x1="70" y1="420" x2="1130" y2="420" stroke="var(--line)"/>
    <text class="meta" x="70" y="444">按 GitHub Linguist 检测的文件字节汇总 · percentages by detected file size</text>
    <text class="meta" x="1130" y="444" text-anchor="end">Updated {generated}</text>
  </g>
</svg>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-forks", action="store_true")
    args = parser.parse_args()

    totals, repository_count = repository_languages(
        args.username,
        os.environ.get("GITHUB_TOKEN"),
        args.include_forks,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render_svg(args.username, totals, repository_count, args.include_forks),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
