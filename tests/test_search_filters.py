from pages.search_page import SearchPage


def test_shoe_search_rejects_shoelace_accessories():
    assert not SearchPage.title_matches_shoe_intent("2 pairs round flat shoelaces for sneakers")


def test_shoe_search_rejects_german_shoelace_accessories():
    assert not SearchPage.title_matches_shoe_intent("Schnuersenkel rund flach 60cm fuer Sneaker Schuhe")


def test_shoe_search_rejects_shoe_care_and_repair_products():
    assert not SearchPage.title_matches_shoe_intent(
        "Angelus acrylic shoes boots handbags leather paint dye scarlet red"
    )
    assert not SearchPage.title_matches_shoe_intent("Shoe care repair polish for boots and sneakers")


def test_shoe_search_accepts_real_footwear_titles():
    assert SearchPage.title_matches_shoe_intent("Nike Air Max sneakers men size 11")
    assert SearchPage.title_matches_shoe_intent("Women leather ankle boots US shoe size 8")


def test_search_rejects_placeholder_image_urls():
    assert not SearchPage.is_real_image_url("https://ir.ebaystatic.com/pictures/aw/pics/s.gif")
    assert not SearchPage.is_real_image_url("https://example.com/no-image-placeholder.png")


def test_search_accepts_real_image_urls():
    assert SearchPage.is_real_image_url("https://i.ebayimg.com/images/g/example/s-l500.jpg")


def test_search_url_encodes_query_terms():
    assert SearchPage.search_url("running shoes") == "https://www.ebay.com/sch/i.html?_nkw=running+shoes"
