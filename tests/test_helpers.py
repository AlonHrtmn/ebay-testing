import pytest

from utils.config import positive_float, positive_int
from utils.helpers import parse_price


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$220.00", 220.0),
        ("ILS 1,220.50", 1220.5),
        ("EUR 1.220,50", 1220.5),
        ("EUR 220,50", 220.5),
        ("$20.00 to $30.00", 20.0),
        ("$20.00 - $30.00", 20.0),
        ("", 0.0),
    ],
)
def test_parse_price(text: str, expected: float) -> None:
    assert parse_price(text) == expected


def test_positive_config_values() -> None:
    config = {"max_price": "220.5", "item_limit": "5"}

    assert positive_float(config, "max_price", 1.0) == 220.5
    assert positive_int(config, "item_limit", 1) == 5


@pytest.mark.parametrize("value", [0, -1, "invalid", None])
def test_positive_float_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        positive_float({"max_price": value}, "max_price", 1.0)
