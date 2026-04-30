import base64
import datetime as dt
import html
import json
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


def write_placeholder_card(message: str = "Atualizando estatísticas...") -> None:
    ensure_output_directory()

    safe_message = html.escape(message)

    svg = f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 26px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .text {{
      font: 600 16px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.9;
    }}
    .muted {{
      font: 500 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.65;
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="40" y="64" class="title">WakaTime</text>
  <text x="40" y="120" class="text">{safe_message}</text>
  <text x="40" y="150" class="muted">O card será preenchido automaticamente pelo GitHub Actions.</text>

  <rect x="40" y="190" width="420" height="12" rx="6" fill="#161b22" />
  <rect x="40" y="190" width="160" height="12" rx="6" fill="{CARD_PRIMARY}" opacity="0.85" />

  <circle cx="52" cy="235" r="6" fill="{CARD_PRIMARY}" />
  <text x="68" y="240" class="muted">Aguardando dados do WakaTime</text>
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

    colors = ["#61dafb", "#3178c6", "#f7df1e", "#e34f26", "#8cc84b"]

    bar_x = 42
    bar_y = 104
    bar_width = 430
    bar_height = 10
    current_x = bar_x

    bar_svg: list[str] = []
    rows_svg: list[str] = []

    for index, (_, seconds) in enumerate(top_languages):
        percent = seconds / total_seconds
        width = max(3, bar_width * percent)
        color = colors[index % len(colors)]

        bar_svg.append(
            f'<rect x="{current_x:.2f}" y="{bar_y}" width="{width:.2f}" '
            f'height="{bar_height}" rx="5" fill="{color}" />'
        )
        current_x += width

    for index, (name, seconds) in enumerate(top_languages):
        percent = seconds / total_seconds * 100
        color = colors[index % len(colors)]
        y = 146 + index * 30

        safe_name = html.escape(name)
        safe_duration = html.escape(format_duration(seconds))

        rows_svg.append(
            f"""
  <circle cx="52" cy="{y - 5}" r="6" fill="{color}" />
  <text x="68" y="{y}" class="label">{safe_name}</text>
  <text x="300" y="{y}" class="value">{safe_duration}</text>
  <text x="448" y="{y}" class="percent">{percent:.1f}%</text>
"""
        )

    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 26px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .subtitle {{
      font: 600 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.85;
    }}
    .label {{
      font: 600 15px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
    }}
    .value {{
      font: 600 14px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.9;
    }}
    .percent {{
      font: 600 14px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.75;
      text-anchor: end;
    }}
    .total {{
      font: 700 18px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="40" y="54" class="title">WakaTime</text>
  <text x="40" y="80" class="subtitle">De {html.escape(format_date(start))} até {html.escape(format_date(end))}</text>

  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="5" fill="#161b22" />
  {"".join(bar_svg)}

  {"".join(rows_svg)}

  <text x="40" y="270" class="subtitle">Tempo total</text>
  <text x="140" y="270" class="total">{html.escape(format_duration(total_seconds))}</text>
</svg>
"""


def build_empty_card(*, start: dt.date, end: dt.date) -> str:
    return f"""<svg width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{
      font: 700 26px Arial, Helvetica, sans-serif;
      fill: {CARD_PRIMARY};
    }}
    .subtitle {{
      font: 600 13px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.85;
    }}
    .text {{
      font: 600 16px Arial, Helvetica, sans-serif;
      fill: {CARD_MUTED};
      opacity: 0.9;
    }}
  </style>

  <rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="8" fill="{CARD_BACKGROUND}" />

  <text x="40" y="54" class="title">WakaTime</text>
  <text x="40" y="80" class="subtitle">De {html.escape(format_date(start))} até {html.escape(format_date(end))}</text>

  <text x="40" y="140" class="text">Nenhuma atividade registrada no período.</text>
  <text x="40" y="172" class="subtitle">O card será atualizado automaticamente quando houver dados.</text>

  <rect x="40" y="215" width="420" height="12" rx="6" fill="#161b22" />
  <rect x="40" y="215" width="80" height="12" rx="6" fill="{CARD_PRIMARY}" opacity="0.85" />
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
