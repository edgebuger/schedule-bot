"""Состояние бота в файле state.json (лежит прямо в репозитории).

Когда бот что-то меняет — файл перезаписывается, и воркфлоу потом
коммитит его обратно. Поэтому между запусками всё помнится.
"""

from __future__ import annotations

import json
from pathlib import Path

from config import STATE_FILE

DEFAULT_STATE = {
    "subscribers": [],
    "last_digest": "",
    "update_offset": 0,
}

_dirty = False


def load() -> dict:
    path = Path(STATE_FILE)
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_STATE)

    state = dict(DEFAULT_STATE)
    if isinstance(data, dict):
        state.update(data)

    subs = state.get("subscribers")
    state["subscribers"] = [int(x) for x in subs if str(x).lstrip("-").isdigit()] if isinstance(subs, list) else []
    try:
        state["update_offset"] = int(state.get("update_offset") or 0)
    except (TypeError, ValueError):
        state["update_offset"] = 0
    return state


def save(state: dict) -> bool:
    """Пишет состояние. Возвращает True, если файл изменился."""
    global _dirty

    path = Path(STATE_FILE)
    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""

    if payload == previous:
        return False

    path.write_text(payload, encoding="utf-8")
    _dirty = True
    return True


def is_dirty() -> bool:
    return _dirty