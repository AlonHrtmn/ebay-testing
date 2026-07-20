import os
import time


import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage
from utils.exceptions import EbayVerificationRequired
from utils.config import load_config


class FlowTimer:
    def __init__(self) -> None:
        self.start_time = time.perf_counter()

    def progress(self, message: str) -> None:
        total_seconds = int(time.perf_counter() - self.start_time)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        print(
        f"\n[eBay flow {elapsed}] {message}",
        flush=True,
        )


def test_ebay_shopping_flow(page: Page) -> None:
    timer = FlowTimer()

    # Load validated configuration.
    config = load_config()

    # Instantiate Page Object Model components.
    login_page = LoginPage(page)
    search_page = SearchPage(page)
    product_page = ProductPage(page)
    cart_page = CartPage(page)

    try:
        timer.progress(
            "Starting shopping flow: "
            f"searching for '{config.search_query}', "
            f"max price {config.max_price:.2f}, "
            f"target items {config.item_limit}."
        )

        # Step 1: Identification / session setup.
        timer.progress("Opening eBay guest session.")

        login_page.login_stub(
            config.username,
            config.password,
        )

        timer.progress("Guest session is ready.")

        # Fresh Playwright contexts normally start with an empty guest cart.
        # Keep pre-run cart cleanup opt-in because extra cart visits
        # can trigger eBay verification.
        if os.getenv("EBAY_CLEAR_CART_BEFORE_RUN") == "1":
            timer.progress(
                "Clearing existing cart items before the test run."
            )

            cart_page.clear_cart()

            timer.progress("Cart cleanup finished.")

        # Step 2: Search and gather matching URLs.
        timer.progress(
            f"Searching eBay for '{config.search_query}' "
            f"under {config.max_price:.2f}; "
            f"collecting backup samples for "
            f"{config.item_limit} target item(s)."
        )

        urls = search_page.assertSearchItemsFound(
            config.search_query,
            config.max_price,
            config.item_limit,
        )

        assert urls, (
            f"No matching product URLs were found for "
            f"'{config.search_query}'."
        )

        timer.progress(
            f"Collected {len(urls)} "
            f"'{config.search_query}' sample URL(s) "
            f"that match the price filter; "
            f"will add the first {config.item_limit} that work."
        )

        # Step 3: Add valid retrieved items to the cart.
        timer.progress(
            "Opening collected samples and adding valid items "
            "to the cart."
        )

        items_added = product_page.assertItemsAddedToCart(
            urls,
            max_price=config.max_price,
            desired_count=config.item_limit,
        )

        assert items_added > 0, (
            "No items were added to the cart."
        )

        assert items_added <= config.item_limit, (
            f"Added {items_added} items, which exceeds "
            f"the requested limit of {config.item_limit}."
        )

        timer.progress(
            f"Added {items_added} item(s) to the cart."
        )

        # Step 4: Verify cart subtotal against the allowed budget.
        maximum_allowed_total = config.max_price * items_added

        timer.progress(
            f"Checking cart subtotal does not exceed "
            f"{maximum_allowed_total:.2f}."
        )

        cart_page.assertCartTotalNotExceeds(
            config.max_price,
            items_added,
        )

        timer.progress(
            "Cart total passed the budget check. "
            "Test flow complete."
        )

    except EbayVerificationRequired as exc:
        timer.progress(
            f"eBay verification interrupted the flow: {exc}"
        )

        pytest.skip(
            f"eBay verification required: {exc}"
        )