"""Превращает список пар в читаемое сообщение для Telegram."""

from __future__ import annotations

import datetime as dt
from html import escape

from config import GROUP
from parser import Lesson

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


def _time_label(lesson: Lesson) -> str:
    return f"🕐 {lesson.start}–{lesson.end}" if lesson.start and lesson.end else ""


def _was_label(lesson: Lesson) -> str:
    """Строка «раньше было...» — только если предмет реально меняли."""
    if lesson.is_cancelled or not lesson.was_subject:
        return ""
    if lesson.was_subject == lesson.subject:
        return ""
    teacher = f" ({_esc(lesson.was_teacher)})" if lesson.was_teacher else ""
    return f"🔁 раньше: {_esc(lesson.was_subject)}{teacher}"


def format_day(lessons: list[Lesson], day: dt.date) -> str:
    header = f"📅 {WEEKDAYS[day.weekday()].capitalize()}, {day.day} {MONTHS[day.month - 1]}"

    if not lessons:
        return f"{header}\n\n🎉 Пар нет — отдыхай!"

    blocks: list[str] = [f"{header} · группа {GROUP}"]

    for index, lesson in enumerate(lessons, start=1):
        number = lesson.number if lesson.number.isdigit() else str(index)

        if lesson.is_cancelled:
            blocks.append(
                f"<b>{number}. {_esc(lesson.title)} ❌ отменена</b>\n"
                f"   {_time_label(lesson)}".rstrip()
            )
            continue

        mark = f" {lesson.mark}" if lesson.mark else ""
        blocks.append(f"<b>{number}. {_esc(lesson.title)}{mark}</b>")

        details = [_time_label(lesson)]
        if lesson.room:
            details.append(f"📍 {_esc(lesson.room)}")
        details = [item for item in details if item]
        if details:
            blocks.append("   " + "   ".join(details))

        if lesson.teacher:
            blocks.append(f"   👤 {_esc(lesson.teacher)}")

        was = _was_label(lesson)
        if was:
            blocks.append(f"   {was}")

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

        items: list[str] = []
        for index, lesson in enumerate(lessons, start=1):
            number = lesson.number if lesson.number.isdigit() else str(index)
            time_label = f" {_time_label(lesson)}" if _time_label(lesson) else ""

            if lesson.is_cancelled:
                items.append(f"   {number}. {_esc(lesson.title)} ❌ отменена")
                continue

            mark = f" {lesson.mark}" if lesson.mark else ""
            room = f" · {lesson.room}" if lesson.room else ""
            items.append(f"   {number}. {_esc(lesson.title)}{mark}{time_label}{room}")

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