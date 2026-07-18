import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "test_data.json"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load the automation configuration from JSON."""
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def positive_float(config: dict[str, Any], name: str, default: float) -> float:
    try:
        value = float(config.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config value '{name}' must be a number.") from exc
    if value <= 0:
        raise ValueError(f"Config value '{name}' must be greater than 0.")
    return value


def positive_int(config: dict[str, Any], name: str, default: int) -> int:
    try:
        value = int(config.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config value '{name}' must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"Config value '{name}' must be greater than 0.")
    return value
