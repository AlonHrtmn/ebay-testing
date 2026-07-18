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
