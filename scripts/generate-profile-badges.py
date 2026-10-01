import base64
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


WAKATIME_API_KEY = os.environ.get("WAKATIME_API_KEY")

GITHUB_USERNAME = "gislainecosta"

PROFILE_VIEWS_BADGE_PATH = Path("assets/profile-views-badge.svg")
WAKATIME_BADGE_PATH = Path("assets/wakatime-badge.svg")
README_PATH = Path("README.md")

PROFILE_VIEWS_COLOR = "#8a2be2"
WAKATIME_COLOR = "#007ec6"
LABEL_COLOR = "#555555"

KOMAREV_URL = (
    "https://komarev.com/ghpvc/"
    f"?username={GITHUB_USERNAME}"
    "&label=Visitantes"
    "&color=blueviolet"
    "&style=flat"
    "&base=0"
)

WAKATIME_ALL_TIME_URL = (
    "https://wakatime.com/api/v1/users/current/all_time_since_today"
)


def ensure_output_directory() -> None:
    PROFILE_VIEWS_BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)


def format_integer_pt_br(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def format_wakatime_duration(total_seconds: float) -> str:
    total_minutes = int(total_seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    formatted_hours = format_integer_pt_br(hours)

    if minutes:
        return f"{formatted_hours} h {minutes} min"

    return f"{formatted_hours} h"


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    request_headers = {
        "Accept": "image/svg+xml,text/plain,*/*",
        "User-Agent": "gislainecosta-profile-badges/1.0",
    }

    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        headers=request_headers,
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return response.read().decode("utf-8")


def extract_komarev_count(svg: str) -> int:
    aria_match = re.search(
        r'aria-label=["\'][^"\']*?:\s*([\d,]+)["\']',
        svg,
        flags=re.IGNORECASE,
    )

    if aria_match:
        return int(
            aria_match.group(1).replace(",", "")
        )

    title_match = re.search(
        r"<title>\s*[^<]*?:\s*([\d,]+)\s*</title>",
        svg,
        flags=re.IGNORECASE,
    )

    if title_match:
        return int(
            title_match.group(1).replace(",", "")
        )

    text_nodes = re.findall(
        r"<text\b[^>]*>(.*?)</text>",
        svg,
        flags=re.IGNORECASE | re.DOTALL,
    )

    candidates: list[int] = []

    for raw_value in text_nodes:
        value = re.sub(
            r"<[^>]+>",
            "",
            raw_value,
        )

        value = html.unescape(
            value
        ).strip()

        if re.fullmatch(
            r"\d{1,3}(?:,\d{3})*|\d+",
            value,
        ):
            candidates.append(
                int(value.replace(",", ""))
            )

    if candidates:
        return candidates[-1]

    raise ValueError(
        "Não foi possível localizar a contagem "
        "no SVG do Komarev."
    )


def fetch_profile_views() -> int:
    svg = fetch_text(KOMAREV_URL)
    return extract_komarev_count(svg)


def fetch_wakatime_all_time_seconds() -> float:
    if not WAKATIME_API_KEY:
        raise RuntimeError(
            "WAKATIME_API_KEY is not configured."
        )

    token = base64.b64encode(
        WAKATIME_API_KEY.encode("utf-8")
    ).decode("utf-8")

    payload_text = fetch_text(
        WAKATIME_ALL_TIME_URL,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        },
    )

    payload = json.loads(payload_text)

    data = payload.get("data") or {}

    total_seconds = float(
        data.get("total_seconds") or 0
    )

    if total_seconds <= 0:
        raise ValueError(
            "O WakaTime não retornou "
            "um total_seconds válido."
        )

    return total_seconds


def estimate_text_width(text: str) -> int:
    return max(
        42,
        int(round(len(text) * 6.6 + 14)),
    )


def build_badge(
    *,
    label: str,
    message: str,
    message_color: str,
) -> str:
    label_width = estimate_text_width(label)
    message_width = estimate_text_width(message)

    total_width = (
        label_width
        + message_width
    )

    label_x = label_width / 2

    message_x = (
        label_width
        + message_width / 2
    )

    safe_label = html.escape(label)
    safe_message = html.escape(message)

    safe_aria = html.escape(
        f"{label}: {message}",
        quote=True,
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{safe_aria}">
  <title>{safe_aria}</title>

  <linearGradient id="s" x2="0" y2="100%">
    <stop
      offset="0"
      stop-color="#ffffff"
      stop-opacity=".10"
    />
    <stop
      offset="1"
      stop-opacity=".10"
    />
  </linearGradient>

  <clipPath id="r">
    <rect
      width="{total_width}"
      height="20"
      rx="3"
    />
  </clipPath>

  <g clip-path="url(#r)">
    <rect
      width="{label_width}"
      height="20"
      fill="{LABEL_COLOR}"
    />

    <rect
      x="{label_width}"
      width="{message_width}"
      height="20"
      fill="{message_color}"
    />

    <rect
      width="{total_width}"
      height="20"
      fill="url(#s)"
    />
  </g>

  <g
    fill="#ffffff"
    text-anchor="middle"
    font-family="Verdana,DejaVu Sans,sans-serif"
    font-size="11"
  >
    <text
      x="{label_x:.1f}"
      y="15"
      fill="#010101"
      fill-opacity=".30"
    >{safe_label}</text>

    <text
      x="{label_x:.1f}"
      y="14"
    >{safe_label}</text>

    <text
      x="{message_x:.1f}"
      y="15"
      fill="#010101"
      fill-opacity=".30"
    >{safe_message}</text>

    <text
      x="{message_x:.1f}"
      y="14"
    >{safe_message}</text>
  </g>
</svg>
"""


def update_readme_cache_busters() -> None:
    if not README_PATH.exists():
        return

    content = README_PATH.read_text(
        encoding="utf-8"
    )

    cache_token = dt.datetime.now(
        dt.timezone.utc
    ).strftime("%Y%m%d%H%M%S")

    dynamic_assets = (
        "profile-views-badge.svg",
        "wakatime-badge.svg",
        "wakatime-stats.svg",
    )

    updated = content

    for asset_name in dynamic_assets:
        pattern = (
            rf"({re.escape(asset_name)})"
            rf"(?:\?v=[^\"')\s>]+)?"
        )

        updated = re.sub(
            pattern,
            rf"\1?v={cache_token}",
            updated,
        )

    if updated != content:
        README_PATH.write_text(
            updated,
            encoding="utf-8",
        )


def main() -> None:
    ensure_output_directory()

    profile_views = fetch_profile_views()

    wakatime_seconds = (
        fetch_wakatime_all_time_seconds()
    )

    profile_views_message = (
        format_integer_pt_br(profile_views)
    )

    wakatime_message = (
        format_wakatime_duration(
            wakatime_seconds
        )
    )

    PROFILE_VIEWS_BADGE_PATH.write_text(
        build_badge(
            label="Visitantes",
            message=profile_views_message,
            message_color=PROFILE_VIEWS_COLOR,
        ),
        encoding="utf-8",
    )

    WAKATIME_BADGE_PATH.write_text(
        build_badge(
            label="WakaTime",
            message=wakatime_message,
            message_color=WAKATIME_COLOR,
        ),
        encoding="utf-8",
    )

    update_readme_cache_busters()

    print(
        "Badges gerados:",
        f"Visitantes={profile_views_message}",
        f"WakaTime={wakatime_message}",
    )


if __name__ == "__main__":
    try:
        main()

    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Erro HTTP ao atualizar badges: "
            f"{error.code}"
        ) from error

    except urllib.error.URLError as error:
        raise SystemExit(
            f"Erro de conexão ao atualizar badges: "
            f"{error.reason}"
        ) from error

    except Exception as error:
        raise SystemExit(
            f"Erro ao atualizar badges: {error}"
        ) from error
