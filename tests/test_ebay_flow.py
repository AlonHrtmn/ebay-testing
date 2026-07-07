import os
import json
import time

import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage
from utils.exceptions import EbayVerificationRequired


def load_test_data():
    """Reads input configurations from config/test_data.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "test_data.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def test_ebay_shopping_flow(page: Page):
    start_time = time.perf_counter()

    def progress(message: str) -> None:
        elapsed = format_elapsed(time.perf_counter() - start_time)
        print(f"\n[eBay flow {elapsed}] {message}", flush=True)

    # Load parameters
    data = load_test_data()
    search_query = data.get("search_query", "shoes")
    max_price = data.get("max_price", 220.0)
    item_limit = data.get("item_limit", 5)
    username = data.get("username", "")
    password = data.get("password", "")

    # Instantiate POM components
    login_page = LoginPage(page)
    search_page = SearchPage(page)
    product_page = ProductPage(page)
    cart_page = CartPage(page)

    try:
        progress(
            "Starting shopping flow: "
            f"searching for '{search_query}', max price {max_price}, target items {item_limit}."
        )

        # Step 1: Identification / session setup
        progress("Opening eBay guest session.")
        login_page.login_stub(username, password)
        progress("Guest session is ready.")

        # Fresh Playwright contexts normally start with an empty guest cart.
        # Keep pre-run cart cleanup opt-in because extra cart visits can trigger verification.
        if os.getenv("EBAY_CLEAR_CART_BEFORE_RUN") == "1":
            progress("Clearing existing cart items before the test run.")
            cart_page.clear_cart()
            progress("Cart cleanup finished.")

        # Step 2: Search and gather matching URLs with price constraint and pagination.
        progress(
            f"Searching eBay for '{search_query}' under {max_price}; "
            f"collecting up to {item_limit} matching item sample(s)."
        )
        urls = search_page.assertSearchItemsFound(search_query, max_price, item_limit)
        progress(f"Collected {len(urls)} '{search_query}' sample URL(s) that match the price filter.")

        # Step 3: Add all retrieved items to the cart, handling variants randomly if present.
        progress("Opening collected samples and adding valid items to the cart.")
        items_added = product_page.assertItemsAddedToCart(
            urls,
            max_price=max_price,
            desired_count=item_limit,
        )
        progress(f"Added {items_added} item(s) to the cart.")

        # Step 4: Open cart page, retrieve subtotal, and verify budget limit.
        progress(f"Checking cart subtotal does not exceed {max_price * items_added}.")
        cart_page.assertCartTotalNotExceeds(max_price, items_added)
        progress("Cart total passed the budget check. Test flow complete.")
    except EbayVerificationRequired as exc:
        progress(f"eBay verification interrupted the flow: {exc}")
        pytest.skip(str(exc))
