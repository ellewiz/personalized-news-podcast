import json
from typing import Any

from . import config

_DEFAULT_STATE = {"seen_guids": [], "episodes": []}


def load_state() -> dict[str, Any]:
    if not config.STATE_PATH.exists():
        return {"seen_guids": [], "episodes": []}
    with open(config.STATE_PATH) as f:
        data = json.load(f)
    data.setdefault("seen_guids", [])
    data.setdefault("episodes", [])
    return data


def save_state(state: dict[str, Any]) -> None:
    config.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)
