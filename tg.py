"""Минимальный клиент Telegram Bot API.

aiogram тут не нужен: на GitHub Actions бот не висит постоянно, а просыпается
по расписанию, опрашивает накопившиеся команды и отключается.
"""

from __future__ import annotations

import logging

import httpx

from config import BOT_TOKEN, REQUEST_TIMEOUT, TELEGRAM_PROXY

log = logging.getLogger(__name__)

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            proxy=TELEGRAM_PROXY or None,
        )
    return _client


def _call(method: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = client().post(url, data=params)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 — воркфлоу не должен падать
        log.warning("Telegram %s не ответил: %s", method, exc)
        return {"ok": False, "description": str(exc)}

    if not payload.get("ok"):
        log.warning("Telegram %s вернул ошибку: %s", method, payload.get("description"))
    return payload


def get_me() -> dict:
    return _call("getMe")


def send(chat_id: int, text: str) -> bool:
    result = _call(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return bool(result.get("ok"))


def get_updates(offset: int) -> list[dict]:
    """Забирает накопленные команды. timeout=0 — не ждём новые."""
    result = _call("getUpdates", offset=offset, timeout=0, allowed_updates='["message"]')
    return result.get("result") or []