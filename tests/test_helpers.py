import pytest

from utils.config import positive_float, positive_int
from utils.helpers import (
    convert_currency,
    parse_price,
    parse_price_and_currency,
)


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


@pytest.mark.parametrize(
    ("text", "expected_amount", "expected_currency"),
    [
        ("$220.00", 220.0, "USD"),
        ("ILS 1,220.50", 1220.5, "ILS"),
        ("EUR 1.220,50", 1220.5, "EUR"),
        ("£100.00", 100.0, "GBP"),
        ("US $99.99", 99.99, "USD"),
        ("₪250", 250.0, "ILS"),
        ("100", 100.0, None),
        ("", 0.0, None),
    ],
)
def test_parse_price_and_currency(
    text: str,
    expected_amount: float,
    expected_currency: str | None,
) -> None:
    amount, currency = parse_price_and_currency(text)
    assert amount == expected_amount
    assert currency == expected_currency


@pytest.mark.parametrize(
    ("amount", "from_currency", "to_currency", "expected"),
    [
        (100.0, "USD", "ILS", 370.0),
        (370.0, "ILS", "USD", 99.9),
        (100.0, "USD", "EUR", 93.0),
        (100.0, "EUR", "USD", 108.0),
        (100.0, "GBP", "USD", 127.0),
    ],
)
def test_convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    expected: float,
) -> None:
    assert convert_currency(
        amount,
        from_currency,
        to_currency,
    ) == expected


def test_positive_config_values() -> None:
    config = {"max_price": "220.5", "item_limit": "5"}

    assert positive_float(config, "max_price", 1.0) == 220.5
    assert positive_int(config, "item_limit", 1) == 5


@pytest.mark.parametrize("value", [0, -1, "invalid", None])
def test_positive_float_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        positive_float({"max_price": value}, "max_price", 1.0)
