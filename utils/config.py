from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "test_data.json"


@dataclass(frozen=True)
class TestConfig:
    search_query: str
    max_price: float
    item_limit: int
    username: str
    password: str


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> TestConfig:

    with path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)

    search_query = str(data.get("search_query", "")).strip()
    if not search_query:
        raise ValueError("'search_query' cannot be empty.")

    max_price = positive_float(data, "max_price", 0)
    if max_price <= 0:
        raise ValueError("'max_price' must be greater than 0.")

    item_limit = positive_int(data, "item_limit", 0)
    if item_limit <= 0:
        raise ValueError("'item_limit' must be greater than 0.")

    return TestConfig(
        search_query=search_query,
        max_price=max_price,
        item_limit=item_limit,
        username=str(data.get("username", "")).strip(),
        password=str(data.get("password", "")),
    )


def positive_float(config: dict[str, Any], name: str, default: float) -> float:
    try:
        value = float(config.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' must be a number.") from exc

    if value <= 0:
        raise ValueError(f"'{name}' must be greater than 0.")

    return value

def positive_int(config: dict[str, Any], name: str, default: int) -> int:
    try:
        value = int(config.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config value '{name}' must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"Config value '{name}' must be greater than 0.")
    return value
