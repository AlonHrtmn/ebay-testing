from pages.search_page import SearchPage


def test_normalize_words_removes_special_chars() -> None:
    assert SearchPage.normalize_words("New Listing: Men's Sneakers!") == "new listing men s sneakers"


def test_contains_any_keyword_matches_exact_word() -> None:
    assert SearchPage.contains_any_keyword("running shoes", {"shoe", "boot"})
    assert not SearchPage.contains_any_keyword("runningness", {"shoe", "boot"})


def test_is_accessory_text_detects_accessory_keywords() -> None:
    assert SearchPage.is_accessory_text("shoe laces for sneakers")
    assert SearchPage.is_accessory_text("sports shoe cleaner")
    assert not SearchPage.is_accessory_text("men s running shoes")


def test_is_shoe_query_detects_shoe_queries() -> None:
    assert SearchPage.is_shoe_query("running shoes")
    assert not SearchPage.is_shoe_query("shoe cleaner")


def test_is_real_image_url_rejects_placeholder() -> None:
    assert SearchPage.is_real_image_url("https://i.ebayimg.com/images/g/abc123/s-l1600.jpg")
    assert not SearchPage.is_real_image_url("https://ir.ebaystatic.com/pictures/aw/pics/placeholder.gif")
