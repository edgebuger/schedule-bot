"""Работа с расписанием ВСАМК.

Сайт отдаёт всё расписание одним запросом:
    https://vsamk.ru/wp-json/vsamk-schedule/v1/current

В ответе:
    records[] — все пары всех групп: дата, группа, номер пары, предмет,
                преподаватель, кабинет, признак замены;
    weeks[]   — недели с перечнем опубликованных дат;
    replacements[] — замены пар (в records они уже применены).

Здесь мы просто вытаскиваем из этого куска расписание своей группы
и подставляем время звонков.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from config import (
    BELLS,
    CACHE_TTL,
    COLLEGE_TZ,
    GROUP,
    REQUEST_TIMEOUT,
    SCHEDULE_API,
    USER_AGENT,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
LAST_GOOD_FILE = DATA_DIR / "last_good.json"

STATUS_MARKS = {
    "changed": "🔁 замена",
    "already_in_base": "🔁 замена",
    "added": "🆕 добавлено",
    "cancelled": "❌ отменена",
    "pdf_updated": "📄 уточнено",
}


@dataclass
class Lesson:
    number: str = ""
    start: str = ""
    end: str = ""
    subject: str = ""
    teacher: str = ""
    room: str = ""
    status: str = ""

    @property
    def mark(self) -> str:
        return STATUS_MARKS.get(self.status, "")


# --- сетевая часть --------------------------------------------------------

_cache: tuple[float, dict] | None = None


def _slim(data: dict) -> dict:
    """Оставляем только то, что нужно боту, чтобы кэш на диске был лёгким."""
    return {
        "generated_at": data.get("generated_at"),
        "timezone": data.get("timezone"),
        "weeks": data.get("weeks", []),
        "records": [r for r in data.get("records", []) if r.get("group") == GROUP],
        "replacements": [x for x in data.get("replacements", []) if x.get("group") == GROUP],
    }


def _save_last_good(data: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LAST_GOOD_FILE.write_text(
            json.dumps(_slim(data), ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _load_last_good() -> dict | None:
    if not LAST_GOOD_FILE.exists():
        return None
    try:
        return json.loads(LAST_GOOD_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def fetch_data(force: bool = False) -> dict:
    """Качает расписание. Если сеть отвалилась — отдаёт последний удачный ответ."""
    global _cache

    if not force and _cache and time.monotonic() - _cache[0] < CACHE_TTL:
        return _cache[1]

    try:
        response = httpx.get(
            SCHEDULE_API,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data.get("records"), list):
            raise ValueError("в ответе API нет списка records")
    except Exception:
        saved = _load_last_good()
        if saved:
            return saved
        raise

    _cache = (time.monotonic(), data)
    _save_last_good(data)
    return data


# --- даты -----------------------------------------------------------------

def today() -> dt.date:
    """Сегодняшняя дата по часовому поясу колледжа."""
    return dt.datetime.now(COLLEGE_TZ).date()


def published_dates(data: dict | None = None) -> set[str]:
    data = data if data is not None else fetch_data()
    dates: set[str] = set()
    for week in data.get("weeks", []):
        dates.update(week.get("published_dates") or [])
    return dates


def is_published(day: dt.date, data: dict | None = None) -> bool:
    return day.isoformat() in published_dates(data)


def next_published_after(day: dt.date, data: dict | None = None) -> dt.date | None:
    """Ближайшая опубликованная дата строго после day."""
    dates = published_dates(data)
    for offset in range(1, 30):
        candidate = day + dt.timedelta(days=offset)
        if candidate.isoformat() in dates:
            return candidate
    return None


# --- расписание -----------------------------------------------------------

def get_day_lessons(day: dt.date | None = None, data: dict | None = None) -> list[Lesson]:
    day = day or today()
    data = data if data is not None else fetch_data()

    rows = [
        r
        for r in data.get("records", [])
        if r.get("group") == GROUP and r.get("date") == day.isoformat()
    ]
    rows.sort(key=lambda r: r.get("slot") or 0)

    lessons: list[Lesson] = []
    for row in rows:
        if row.get("empty"):
            continue
        slot = row.get("slot")
        start, end = BELLS.get(slot, ("", ""))
        lessons.append(
            Lesson(
                number=str(row.get("printed_pair") or slot or ""),
                start=start,
                end=end,
                subject=(row.get("subject") or "").strip(),
                teacher=(row.get("teacher") or "").strip(),
                room=(row.get("room") or "").strip(),
                status=(row.get("status") or "").strip(),
            )
        )
    return lessons


def get_week(monday: dt.date | None = None, data: dict | None = None) -> dict[int, list[Lesson]]:
    monday = monday or (today() - dt.timedelta(days=today().weekday()))
    data = data if data is not None else fetch_data()

    week: dict[int, list[Lesson]] = {}
    for offset in range(7):
        day = monday + dt.timedelta(days=offset)
        week[offset] = get_day_lessons(day, data)
    return week


def changes_for(day: dt.date, data: dict | None = None) -> list[str]:
    """Тексты замен, которые коснулись группы в этот день."""
    data = data if data is not None else fetch_data()
    key = day.isoformat()
    out: list[str] = []
    for item in data.get("replacements", []):
        if item.get("date") != key:
            continue
        reason = item.get("reason") or ""
        pair = item.get("to_pair") or item.get("from_pair") or ""
        out.append(f"Пара {pair}: {reason}" if reason else f"Пара {pair}: замена")
    return out