import base64
import datetime as dt
import html
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


API_KEY = os.environ.get("WAKATIME_API_KEY")
OUTPUT_PATH = Path("assets/wakatime-stats.svg")

CARD_WIDTH = 500
CARD_HEIGHT = 300
CARD_BACKGROUND = "#20232a"
CARD_PRIMARY = "#61dafb"
CARD_MUTED = "#ffffff"

DONUT_COLORS = ["#61dafb", "#3b82f6", "#f6d32d", "#f97316", "#8bc34a"]


def ensure_output_directory() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def format_duration(seconds: float) -> str:
    total_minutes = int(round(seconds / 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours and minutes:
        return f"{hours} h {minutes} min"

    if hours:
        return f"{hours} h"

    return f"{minutes} min"


def split_duration_for_donut(seconds: float) -> tuple[str, str]:
    total_minutes = int(round(seconds / 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours and minutes:
        return f"{hours} h", f"{minutes} min"

    if hours:
        return f"{hours} h", ""

    return f"{minutes} min", ""


def format_date(value: dt.date) -> str:
    months = [
        "jan.",
        "fev.",
        "mar.",
        "abr.",
        "mai.",
        "jun.",
        "jul.",
        "ago.",
        "set.",
        "out.",
        "nov.",
        "dez.",
    ]
    return f"{value.day:02d} {months[value.month - 1]} {value.year}"


def polar_to_cartesian(cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
    angle_rad = math.radians(angle_deg)
    x = cx + radius * math.cos(angle_rad)
    y = cy + radius * math.sin(angle_rad)
    return x, y


def describe_ring_segment(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    start_outer = polar_to_cartesian(cx, cy, outer_radius, start_angle)
    end_outer = polar_to_cartesian(cx, cy, outer_radius, end_angle)
    start_inner = polar_to_cartesian(cx, cy, inner_radius, start_angle)
    end_inner = polar_to_cartesian(cx, cy, inner_radius, end_angle)

    large_arc_flag = 1 if (end_angle - start_angle) > 180 else 0

    return (
        f"M {start_outer[0]:.2f} {start_outer[1]:.2f} "
        f"A {outer_radius} {outer_radius} 0 {large_arc_flag} 1 {end_outer[0]:.2f} {end_outer[1]:.2f} "
        f"L {end_inner[0]:.2f} {end_inner[1]:.2f} "
        f"A {inner_radius} {inner_radius} 0 {large_arc_flag} 0 {start_inner[0]:.2f} {start_inner[1]:.2f} Z"
    )


def write_placeholder_card(message: str = "Atualizando estatísticas...") -> None:
    ensure_output_directory()
    safe_message = html.escape(message)

    svg = f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 24px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .text {{
      font: 600 16px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.92;
    }}
    .muted {{
      font: 500 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.68;
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="36" y="54" class="title">WakaTime</text>
  <text x="36" y="112" class="text">{safe_message}</text>
  <text x="36" y="142" class="muted">O card será preenchido automaticamente pelo GitHub Actions.</text>

  <circle cx="396" cy="156" r="62" fill="#161b22" />
  <circle cx="396" cy="156" r="40" fill="{CARD_BACKGROUND}" />
  <text x="396" y="148" text-anchor="middle" class="muted">WakaTime</text>
  <text x="396" y="170" text-anchor="middle" class="text">...</text>

  <circle cx="48" cy="220" r="6" fill="{CARD_PRIMARY}" />
  <text x="64" y="225" class="muted">Aguardando dados do WakaTime</text>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Generated placeholder card at {OUTPUT_PATH}")


def fetch_wakatime_summaries(start: dt.date, end: dt.date) -> dict:
    if not API_KEY:
        raise RuntimeError("WAKATIME_API_KEY is not configured.")

    url = (
        "https://wakatime.com/api/v1/users/current/summaries"
        f"?start={start.isoformat()}&end={end.isoformat()}"
    )

    token = base64.b64encode(API_KEY.encode("utf-8")).decode("utf-8")

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_languages(payload: dict) -> dict[str, float]:
    languages: dict[str, float] = {}

    for day in payload.get("data", []):
        for language in day.get("languages", []):
            name = language.get("name") or "Outros"
            seconds = float(language.get("total_seconds") or 0)

            if seconds <= 0:
                continue

            languages[name] = languages.get(name, 0) + seconds

    return languages


def build_donut_segments(
    items: list[tuple[str, float]],
    total_seconds: float,
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
) -> str:
    if not items or total_seconds <= 0:
        return ""

    gap_deg = 3 if len(items) > 1 else 0
    total_gap = gap_deg * len(items)
    usable_degrees = max(0, 360 - total_gap)

    current_angle = -90
    segments: list[str] = []

    for index, (_, seconds) in enumerate(items):
        percentage = seconds / total_seconds
        sweep = usable_degrees * percentage

        start_angle = current_angle
        end_angle = current_angle + sweep

        path = describe_ring_segment(
            cx=cx,
            cy=cy,
            outer_radius=outer_radius,
            inner_radius=inner_radius,
            start_angle=start_angle,
            end_angle=end_angle,
        )

        color = DONUT_COLORS[index % len(DONUT_COLORS)]
        segments.append(f'<path d="{path}" fill="{color}" />')

        current_angle = end_angle + gap_deg

    return "\n  ".join(segments)


def build_wakatime_card(
    *,
    start: dt.date,
    end: dt.date,
    languages: dict[str, float],
) -> str:
    total_seconds = sum(languages.values())
    top_languages = sorted(
        languages.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]

    if total_seconds <= 0 or not top_languages:
        return build_empty_card(start=start, end=end)

    legend_rows: list[str] = []
    for index, (name, seconds) in enumerate(top_languages):
        color = DONUT_COLORS[index % len(DONUT_COLORS)]
        percent = (seconds / total_seconds) * 100
        row_y = 124 + index * 30

        safe_name = html.escape(name)
        safe_duration = html.escape(format_duration(seconds))

        legend_rows.append(
            f"""
  <circle cx="48" cy="{row_y - 5}" r="6" fill="{color}" />
  <text x="64" y="{row_y}" class="label">{safe_name}</text>
  <text x="168" y="{row_y}" class="value">{safe_duration}</text>
  <text x="276" y="{row_y}" class="percent">{percent:.1f}%</text>
"""
        )

    donut_svg = build_donut_segments(
        items=top_languages,
        total_seconds=total_seconds,
        cx=392,
        cy=166,
        outer_radius=66,
        inner_radius=42,
    )

    total_line_1, total_line_2 = split_duration_for_donut(total_seconds)

    total_line_2_svg = ""
    if total_line_2:
        total_line_2_svg = f'<text x="392" y="188" class="donutValueSecondary">{html.escape(total_line_2)}</text>'

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 24px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .subtitle {{
      font: 600 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.82;
    }}
    .label {{
      font: 700 12px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
    }}
    .value {{
      font: 600 11px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.92;
    }}
    .percent {{
      font: 700 11px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.82;
      text-anchor: end;
    }}
    .donutLabel {{
      font: 600 11px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.72;
      text-anchor: middle;
    }}
    .donutValuePrimary {{
      font: 700 14px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
      text-anchor: middle;
    }}
    .donutValueSecondary {{
      font: 700 13px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
      text-anchor: middle;
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="36" y="50" class="title">WakaTime</text>
  <text x="36" y="76" class="subtitle">De {html.escape(format_date(start))} até {html.escape(format_date(end))}</text>

  {"".join(legend_rows)}

  <circle cx="392" cy="166" r="66" fill="#161b22" />
  {donut_svg}
  <circle cx="392" cy="166" r="42" fill="{CARD_BACKGROUND}" />
  <text x="392" y="150" class="donutLabel">Tempo total</text>
  <text x="392" y="172" class="donutValuePrimary">{html.escape(total_line_1)}</text>
  {total_line_2_svg}
</svg>
"""


def build_empty_card(*, start: dt.date, end: dt.date) -> str:
    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 24px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .subtitle {{
      font: 600 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.82;
    }}
    .text {{
      font: 600 15px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.92;
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="36" y="50" class="title">WakaTime</text>
  <text x="36" y="76" class="subtitle">De {html.escape(format_date(start))} até {html.escape(format_date(end))}</text>

  <text x="36" y="138" class="text">Nenhuma atividade registrada no período.</text>
  <text x="36" y="166" class="subtitle">O card será atualizado automaticamente quando houver dados.</text>

  <circle cx="392" cy="166" r="66" fill="#161b22" />
  <circle cx="392" cy="166" r="42" fill="{CARD_BACKGROUND}" />
  <text x="392" y="160" text-anchor="middle" class="subtitle">Tempo total</text>
  <text x="392" y="180" text-anchor="middle" class="text">0 min</text>
</svg>
"""


def main() -> None:
    ensure_output_directory()

    today = dt.date.today()
    start = today - dt.timedelta(days=365)

    try:
        payload = fetch_wakatime_summaries(start=start, end=today)
        languages = collect_languages(payload)

        svg = build_wakatime_card(
            start=start,
            end=today,
            languages=languages,
        )

        OUTPUT_PATH.write_text(svg, encoding="utf-8")
        print(f"Generated WakaTime card at {OUTPUT_PATH}")

    except urllib.error.HTTPError as error:
        message = f"Erro ao consultar WakaTime: HTTP {error.code}"
        print(message, file=sys.stderr)
        write_placeholder_card(message)

    except urllib.error.URLError as error:
        message = f"Erro de conexão com WakaTime: {error.reason}"
        print(message, file=sys.stderr)
        write_placeholder_card("Erro temporário ao consultar o WakaTime.")

    except Exception as error:
        print(f"Unexpected error: {error}", file=sys.stderr)
        write_placeholder_card("Atualizando estatísticas...")


if __name__ == "__main__":
    main()
