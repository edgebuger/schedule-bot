"""Превращает список пар в читаемое сообщение для Telegram."""

from __future__ import annotations

import datetime as dt
from html import escape

from config import GROUP
from parser import Lesson, changes_for

WEEKDAYS = (
    "Понедельник", "Вторник", "Среда",
    "Четверг", "Пятница", "Суббота", "Воскресенье",
)

MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _esc(text: str) -> str:
    return escape(text, quote=False)


def format_day(lessons: list[Lesson], day: dt.date) -> str:
    header = f"📅 {WEEKDAYS[day.weekday()].capitalize()}, {day.day} {MONTHS[day.month - 1]}"

    if not lessons:
        return f"{header}\n\n🎉 Пар нет — отдыхай!"

    blocks: list[str] = [f"{header} · группа {GROUP}"]

    for index, lesson in enumerate(lessons, start=1):
        number = lesson.number if lesson.number.isdigit() else str(index)
        mark = f" {lesson.mark}" if lesson.mark else ""
        blocks.append(f"<b>{number}. {_esc(lesson.subject)}{mark}</b>")

        details: list[str] = []
        if lesson.start and lesson.end:
            details.append(f"🕐 {lesson.start}–{lesson.end}")
        if lesson.room:
            details.append(f"📍 {_esc(lesson.room)}")
        if details:
            blocks.append("   " + "   ".join(details))

        if lesson.teacher:
            blocks.append(f"   👤 {_esc(lesson.teacher)}")

    try:
        notes = changes_for(day)
    except Exception:  # noqa: BLE001 — заметки не должны ломать сообщение
        notes = []
    if notes:
        blocks.append("🔁 <i>Замены: " + "; ".join(_esc(n) for n in notes) + "</i>")

    return "\n\n".join(blocks)


def format_week(days: dict[int, list[Lesson]], monday: dt.date) -> str:
    """days — ключ: смещение от понедельника (0..6)."""
    chunks = [f"🗓 Неделя с {monday.day} {MONTHS[monday.month - 1]} · {GROUP}"]

    for offset in range(7):
        weekday = (monday.weekday() + offset) % 7
        day = monday + dt.timedelta(days=offset)
        lessons = days.get(offset, [])
        date_label = f"{day.day} {MONTHS[day.month - 1]}"

        if not lessons:
            chunks.append(f"<b>{WEEKDAYS[weekday]}, {date_label}</b> — пар нет")
            continue

        items = []
        for index, lesson in enumerate(lessons, start=1):
            number = lesson.number if lesson.number.isdigit() else str(index)
            time_label = f" {lesson.start}–{lesson.end}" if lesson.start and lesson.end else ""
            mark = f" {lesson.mark}" if lesson.mark else ""
            room = f" · {lesson.room}" if lesson.room else ""
            items.append(f"   {number}. {_esc(lesson.subject)}{mark}{time_label}{room}")

        chunks.append(f"<b>{WEEKDAYS[weekday]}, {date_label}</b>\n" + "\n".join(items))

    return "\n\n".join(chunks)


def format_unpublished(day: dt.date, next_day: dt.date | None) -> str:
    text = (
        f"📅 {WEEKDAYS[day.weekday()].capitalize()}, {day.day} {MONTHS[day.month - 1]}\n\n"
        "⏳ Расписание на этот день ещё не опубликовано."
    )
    if next_day:
        text += (
            f"\nБлижайшая опубликованная дата — "
            f"{WEEKDAYS[next_day.weekday()].lower()}, "
            f"{next_day.day} {MONTHS[next_day.month - 1]}."
        )
    return text