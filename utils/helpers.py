import re


def parse_price(price_str: str) -> float:
    """
    Parses a price string (e.g. '$220.00', 'ILS 1,500.50', '₪220 to ₪250') 
    into a clean float value.
    """
    if not price_str:
        return 0.0
    
    cleaned = price_str.strip().lower()
    
    # Handle ranges by taking the first price (starting/minimum price)
    cleaned = re.split(r"\s+to\s+|\s+[–—-]\s+", cleaned, maxsplit=1)[0]
        
    # Remove non-essential characters (keep digits, dots, commas, and minus sign)
    cleaned = re.sub(r"[^\d.,+-]", "", cleaned)
    
    if not cleaned:
        return 0.0
        
    # Standardize commas and decimals
    if "," in cleaned and "." in cleaned:
        # The right-most separator is normally the decimal separator.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # e.g., 220,50 (comma decimal separator) vs 1,220 (comma thousand separator)
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
            
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_price_and_currency(price_str: str) -> tuple[float, str | None]:
    """
    Parses a price string into a numeric amount and currency code.
    Returns (amount, currency) where currency may be None if unknown.
    """
    if not price_str:
        return 0.0, None

    normalized = price_str.strip()
    currency_match = re.search(
        r"(?:\b(ILS|USD|EUR|GBP|AUD|CAD|NZD)\b|AU\s*\$|US\s*\$|CA\s*\$|NZ\s*\$|\$|₪|€|£)",
        normalized,
        re.IGNORECASE,
    )

    currency = None
    if currency_match:
        token = currency_match.group(1) or currency_match.group(0)
        token = token.strip().upper().replace(" ", "")

        if token in {"ILS", "₪"}:
            currency = "ILS"
        elif token in {"EUR", "€"}:
            currency = "EUR"
        elif token in {"GBP", "£"}:
            currency = "GBP"
        elif token in {"AUD", "AU$"}:
            currency = "AUD"
        elif token in {"CAD", "CA$"}:
            currency = "CAD"
        elif token in {"NZD", "NZ$"}:
            currency = "NZD"
        elif token in {"USD", "US$", "$"}:
            currency = "USD"

    return parse_price(price_str), currency


DEFAULT_EXCHANGE_RATES = {
    ("USD", "ILS"): 3.7,
    ("ILS", "USD"): 0.27,
    ("USD", "EUR"): 0.93,
    ("EUR", "USD"): 1.08,
    ("USD", "GBP"): 0.79,
    ("GBP", "USD"): 1.27,
    ("USD", "AUD"): 1.50,
    ("AUD", "USD"): 0.67,
    ("USD", "CAD"): 1.36,
    ("CAD", "USD"): 0.74,
    ("USD", "NZD"): 1.60,
    ("NZD", "USD"): 0.63,
}


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    exchange_rates: dict[tuple[str, str], float] | None = None,
) -> float:
    """
    Converts an amount from one currency to another using exchange rates.
    """
    if from_currency.upper() == to_currency.upper():
        return amount

    rates = exchange_rates or DEFAULT_EXCHANGE_RATES
    key = (from_currency.upper(), to_currency.upper())

    if key not in rates:
        raise ValueError(
            f"No exchange rate available for {from_currency} -> {to_currency}."
        )

    return amount * rates[key]
