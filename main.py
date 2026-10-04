"""Точка входа бота для GitHub Actions (и для запуска вручную из консоли).

Логика одного запуска:
  1. ответить на команды, которые накопились, пока бот «спал»;
  2. если подошло время и сегодня ещё не слали — разослать расписание.

Оба шага занимают по паре секунд, поэтому воркфлоу можно запускать часто.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

import config
import state as st
import tg
from formatter import format_day, format_unpublished, format_week
from parser import (
    fetch_data,
    get_day_lessons,
    get_week,
    is_published,
    next_published_after,
    today,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("schedule-bot")

HELP = (
    f"<b>Бот присылает расписание группы {config.GROUP}</b>\n\n"
    "<b>Команды</b>\n"
    "/today — расписание на сегодня\n"
    "/tomorrow — на ближайший опубликованный день\n"
    "/all — на неделю\n"
    "/off — отключить ежедневную рассылку\n"
    "/on — включить обратно\n"
    "/help — эта справка"
)


# --- отправка -------------------------------------------------------------

def send_day(chat_id: int, day: dt.date) -> None:
    try:
        data = fetch_data()
        published = is_published(day, data)
        lessons = get_day_lessons(day, data) if published else []
        next_day = None if published else next_published_after(day, data)
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось получить расписание: %s", exc)
        tg.send(chat_id, f"⚠️ Не смог загрузить расписание: {exc}")
        return

    if not published:
        tg.send(chat_id, format_unpublished(day, next_day))
        return

    if not lessons and not config.SEND_EMPTY_DAYS:
        return

    tg.send(chat_id, format_day(lessons, day))


def send_week(chat_id: int) -> None:
    try:
        data = fetch_data()
        monday = today() - dt.timedelta(days=today().weekday())
        tg.send(chat_id, format_week(get_week(monday, data), monday))
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось получить недельное расписание: %s", exc)
        tg.send(chat_id, f"⚠️ Не смог загрузить расписание: {exc}")


# --- команды --------------------------------------------------------------

def handle_command(chat_id: int, text: str, current: dict) -> None:
    command = text.split()[0].lower().split("@")[0]

    if command == "/start":
        if chat_id not in current["subscribers"]:
            current["subscribers"].append(chat_id)
        tg.send(
            chat_id,
            f"Привет! 👋 Буду присылать расписание группы <b>{config.GROUP}</b>.\n\n"
            f"Каждый день примерно в <b>{config.SEND_TIME}</b> ({config.TIMEZONE}).\n\n" + HELP,
        )

    elif command == "/on":
        if chat_id not in current["subscribers"]:
            current["subscribers"].append(chat_id)
        tg.send(chat_id, f"✅ Рассылка включена. Жди сообщение в <b>{config.SEND_TIME}</b>.")

    elif command == "/off":
        current["subscribers"] = [c for c in current["subscribers"] if c != chat_id]
        tg.send(chat_id, "🔕 Рассылка отключена. Включить обратно — /on")

    elif command == "/today":
        send_day(chat_id, today())

    elif command == "/tomorrow":
        send_day(chat_id, today() + dt.timedelta(days=1))

    elif command in ("/all", "/week"):
        send_week(chat_id)

    elif command == "/help":
        tg.send(chat_id, HELP)

    else:
        tg.send(chat_id, "Не знаю такую команду. Напиши /help")


def process_commands(current: dict) -> None:
    updates = tg.get_updates(current["update_offset"])
    if not updates:
        return

    log.info("Новых команд: %s", len(updates))
    for update in updates:
        current["update_offset"] = update["update_id"] + 1

        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            continue

        log.info("Команда от %s: %s", chat_id, text)
        try:
            handle_command(chat_id, text, current)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось обработать команду %s", text)

    st.save(current)


# --- ежедневная рассылка --------------------------------------------------

def digest_due(now: dt.datetime) -> bool:
    if st.load()["last_digest"] == now.date().isoformat():
        return False
    if now.weekday() == 6 and not config.SEND_ON_WEEKENDS:
        return False
    hour, minute = (int(part) for part in config.SEND_TIME.split(":"))
    return (now.hour, now.minute) >= (hour, minute)


def run_digest(now: dt.datetime) -> None:
    current = st.load()
    subscribers = current["subscribers"]

    log.info("Рассылка на %s, подписчиков: %s", now.date(), len(subscribers))

    if subscribers:
        for chat_id in subscribers:
            send_day(chat_id, now.date())

    current["last_digest"] = now.date().isoformat()
    st.save(current)


# --- запуск ---------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Бот с расписанием ВСАМК")
    parser.add_argument("--force-digest", action="store_true", help="разослать прямо сейчас")
    parser.add_argument("--now", help="считать текущим временем это значение (ГГГГ-ММ-ДДЧЧ:ММ)")
    args = parser.parse_args()

    if not config.BOT_TOKEN:
        log.error("BOT_TOKEN не задан")
        return 1

    if args.now:
        now = dt.datetime.strptime(args.now, "%Y-%m-%d%H:%M").replace(tzinfo=config.TZ)
    else:
        now = dt.datetime.now(config.TZ)

    log.info("Старт: %s (%s), группа %s", now, config.TIMEZONE, config.GROUP)

    me = tg.get_me()
    if not me.get("ok"):
        log.error("Telegram недоступен. Проверь токен и доступ к api.telegram.org.")
        return 1
    log.info("Бот на связи: @%s", me["result"].get("username"))

    current = st.load()

    process_commands(current)

    if args.force_digest:
        run_digest(now)
    elif digest_due(now):
        run_digest(now)
    else:
        log.info("Рассылка пока не нужна")

    st.save(current)
    log.info("Готово. Состояние изменено: %s", st.is_dirty())
    return 0


if __name__ == "__main__":
    sys.exit(main())