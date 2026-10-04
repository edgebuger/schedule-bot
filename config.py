"""Настройки бота.

Читаются из переменных окружения, затем из .env, затем дефолты.
На GitHub Actions значения приходят через secrets/переменные — файл .env не нужен.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Telegram -------------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Обычный SOCKS5/HTTP-прокси. На GitHub Actions не нужен: с серверов GitHub
# api.telegram.org доступен напрямую.
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()

# --- Расписание -----------------------------------------------------------

GROUP = os.getenv("GROUP", "ОММ-102").strip()
SCHEDULE_API = os.getenv(
    "SCHEDULE_API", "https://vsamk.ru/wp-json/vsamk-schedule/v1/current"
).strip()
SCHEDULE_URL = os.getenv("SCHEDULE_URL", "https://vsamk.ru/education/raspisanie/").strip()

# Часовой пояс колледжа: по нему определяется «сегодняшний» день.
COLLEGE_TIMEZONE = os.getenv("COLLEGE_TIMEZONE", "Asia/Yekaterinburg").strip()
COLLEGE_TZ = ZoneInfo(COLLEGE_TIMEZONE)

DEFAULT_BELLS: dict[int, tuple[str, str]] = {
    1: ("08:00", "09:20"),
    2: ("09:30", "10:50"),
    3: ("11:30", "12:50"),
    4: ("13:00", "14:20"),
    5: ("14:30", "15:50"),
}


def _load_bells() -> dict[int, tuple[str, str]]:
    raw = os.getenv("BELLS", "").strip()
    if not raw:
        return dict(DEFAULT_BELLS)
    try:
        parsed = json.loads(raw)
        return {int(k): (str(v[0]), str(v[1])) for k, v in parsed.items()}
    except (ValueError, KeyError, IndexError, TypeError):
        return dict(DEFAULT_BELLS)


BELLS = _load_bells()

# --- Рассылка -------------------------------------------------------------

SEND_TIME = os.getenv("SEND_TIME", "06:00").strip()
TIMEZONE = os.getenv("TIMEZONE", "Asia/Yekaterinburg").strip()
TZ = ZoneInfo(TIMEZONE)

SEND_ON_WEEKENDS = os.getenv("SEND_ON_WEEKENDS", "0") == "1"
SEND_EMPTY_DAYS = os.getenv("SEND_EMPTY_DAYS", "1") == "1"

# --- Сеть -----------------------------------------------------------------

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
USER_AGENT = os.getenv("USER_AGENT", DEFAULT_USER_AGENT)

# --- Состояние ------------------------------------------------------------

# Бот хранит подписчиков и смещение в Telegram прямо в репозитории,
# поэтому на хостинге не нужно ни базы данных, ни внешнего хранилища.
STATE_FILE = Path(os.getenv("STATE_FILE", str(BASE_DIR / "state.json")))