from pages.product_page import ProductPage


def test_product_normalize_lowercases_and_strips() -> None:
    assert ProductPage._normalize('  LARGE ') == 'large'


def test_accessory_variant_detection() -> None:
    page = object().__new__(ProductPage)
    assert page._is_accessory_variant('Shoe laces for runners')
    assert not page._is_accessory_variant('Men running shoes')


def test_placeholder_option_detection() -> None:
    page = object().__new__(ProductPage)
    assert page._is_placeholder_option('Please select size')
    assert not page._is_placeholder_option('Size 10')
