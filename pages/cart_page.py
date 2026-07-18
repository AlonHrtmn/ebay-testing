import os
import time

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage
from utils.exceptions import EbayVerificationRequired
from utils.helpers import parse_price


class CartPage(BasePage):
    CART_URL = "https://cart.ebay.com/"
    CART_HOST_MARKERS = ("cart.payments.ebay.com", "cart.ebay.com")
    MAX_REMOVE_ATTEMPTS = 15
    VERIFICATION_TIMEOUT_MS = int(os.getenv("EBAY_VERIFICATION_TIMEOUT_MS", "60000"))

    REMOVE_ITEM_SELECTOR = (
        "button:has-text('Remove'), "
        "button[aria-label*='Remove'], "
        "a:has-text('Remove'), "
        "[data-testid='cart-remove-item']"
    )

    SUBTOTAL_SCRIPT = r"""
    () => {
        const currencyPricePattern = /(?:ILS|\$|\u20aa|\u00a3|GBP|EUR)\s*\d+(?:[.,]\d+)?/gi;
        const elements = [...document.querySelectorAll('*')];

        const priceFromContainer = (element) => {
            const parentText = element.parentElement?.innerText || '';
            const matches = parentText.match(currencyPricePattern);
            return matches?.at(-1) || '';
        };

        const subtotalLabels = [
            /^(?:items?|item\s*subtotal)\s*(?:\(\d+\))?$/i,
            /^subtotal/i,
        ];

        for (const labelPattern of subtotalLabels) {
            for (let i = elements.length - 1; i >= 0; i--) {
                const text = (elements[i].innerText || '').trim();
                if (text.length > 100 || !labelPattern.test(text)) continue;

                const price = priceFromContainer(elements[i]);
                if (price) return price;
            }
        }

        const bodyText = document.body.innerText || '';
        const subtotalMatches = bodyText.match(
            /Subtotal\s*\(?\d*\s*items?\)?\s*(?:ILS|\$|\u20aa|\u00a3|GBP|EUR)\s*\d+(?:[.,]\d+)?/gi
        );
        if (subtotalMatches?.length) {
            return subtotalMatches[0];
        }

        const summary = document.querySelector('[data-testid="cart-summary"]');
        if (summary) {
            const matches = (summary.innerText || '').match(currencyPricePattern);
            return matches?.at(-1) || '';
        }

        return '';
    }
    """

    CART_IMAGES_READY_SCRIPT = r"""
    (expectedCount) => {
        const placeholderTerms = [
            's.gif',
            'spacer',
            'placeholder',
            'noimage',
            'no-image',
            'no_image',
            'blank',
            'transparent',
            'loading',
            'lazy-load',
            'pixel.'
        ];

        const isRealImage = (img) => {
            const source = (
                img.currentSrc ||
                img.src ||
                img.dataset.src ||
                img.dataset.original ||
                img.dataset.lazySrc ||
                ''
            ).toLowerCase();
            const rect = img.getBoundingClientRect();

            return Boolean(source) &&
                !placeholderTerms.some((term) => source.includes(term)) &&
                rect.width >= 40 &&
                rect.height >= 40 &&
                (img.naturalWidth || img.width || 0) >= 40 &&
                (img.naturalHeight || img.height || 0) >= 40;
        };

        const images = [...document.querySelectorAll('img')];
        return images.filter(isRealImage).length >= expectedCount;
    }
    """

    def open(self) -> None:
        self.logger.info("Navigating to %s", self.CART_URL)
        try:
            self.page.goto(self.CART_URL, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            if "net::ERR_ABORTED" not in str(exc) or not self.is_cart_page():
                raise
            self.logger.warning(
                "Cart navigation was aborted after reaching an eBay cart URL: %s",
                self.page.url,
            )

        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=self.DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            if not self.is_cart_page():
                raise
            self.logger.warning("Cart DOM ready wait did not complete: %s", exc)

        self.pause(3000)
        self.raise_if_verification_required()

    def is_cart_page(self) -> bool:
        return any(marker in self.page.url for marker in self.CART_HOST_MARKERS)

    def raise_if_verification_required(self) -> None:
        if not self.is_verification_page():
            return

        is_headless = (
            os.getenv("PLAYWRIGHT_HEADLESS") == "1"
            or os.getenv("EBAY_HEADLESS") == "1"
            or "CI" in os.environ
        )
        if is_headless:
            self.logger.warning("eBay verification page detected in headless mode. Aborting immediately.")
            raise EbayVerificationRequired(
                "eBay served a human-verification page while opening the cart."
            )

        self.logger.warning(
            "eBay verification page detected; waiting up to %s seconds for manual completion.",
            self.VERIFICATION_TIMEOUT_MS // 1000,
        )

        deadline = time.monotonic() + (self.VERIFICATION_TIMEOUT_MS / 1000)
        while time.monotonic() < deadline:
            self.pause(1000)
            if not self.is_verification_page():
                self.logger.info("eBay verification completed; continuing cart flow.")
                return

        raise EbayVerificationRequired(
            "eBay served a human-verification page while opening the cart."
        )

    def is_verification_page(self) -> bool:
        page_text = ""
        try:
            page_text = self.page.locator("body").inner_text(timeout=2000)
        except Exception:
            return "/splashui/" in self.page.url

        is_challenge_url = "/splashui/" in self.page.url
        is_challenge_text = "Please verify yourself" in page_text or "I am human" in page_text
        return is_challenge_url or is_challenge_text

    def clear_cart(self) -> None:
        self.logger.info("Checking whether the cart contains stale items.")
        try:
            self.open()
        except PlaywrightError as exc:
            if "net::ERR_ABORTED" not in str(exc):
                raise
            self.logger.warning(
                "Skipping cart cleanup because eBay aborted empty-cart navigation: %s",
                exc,
            )
            return

        removed_count = 0
        for _ in range(self.MAX_REMOVE_ATTEMPTS):
            remove_button = self.locator(self.REMOVE_ITEM_SELECTOR).first
            if remove_button.count() == 0 or not remove_button.is_visible():
                break

            try:
                remove_button.click()
                removed_count += 1
                self.pause(2500)
            except Exception as exc:
                self.logger.warning("Could not remove cart item: %s", exc)
                self.pause(1000)

        if removed_count:
            self.logger.info("Removed %s stale cart item(s).", removed_count)
        else:
            self.logger.info("Cart is already empty.")

    def get_subtotal_text(self) -> str:
        subtotal_text = self.page.evaluate(self.SUBTOTAL_SCRIPT) or ""
        self.logger.info("Extracted subtotal text: '%s'", subtotal_text)
        return subtotal_text

    def get_subtotal(self) -> float:
        self.logger.info("Opening shopping cart to retrieve subtotal.")
        self.open()
        subtotal = parse_price(self.get_subtotal_text())

        if subtotal <= 0.0:
            self.logger.error("Could not retrieve a positive cart subtotal.")

        return subtotal

    def wait_for_cart_item_images(self, expected_count: int) -> None:
        self.logger.info("Waiting for %s cart item image(s) to load.", expected_count)
        images = self.page.locator("img").all()

        for image in images:
            try:
                image.scroll_into_view_if_needed(timeout=2000)
                self.pause(250)
            except Exception:
                continue

        self.page.evaluate("window.scrollTo(0, 0)")

        try:
            self.page.wait_for_function(
                self.CART_IMAGES_READY_SCRIPT,
                arg=expected_count,
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
        except Exception as exc:
            self.logger.warning("Cart images were not all ready before screenshot: %s", exc)

    def assert_cart_total_not_exceeds(self, budget_per_item: float, items_count: int) -> None:
        self.logger.info(
            "Validating cart subtotal against budget_per_item=%s, items_count=%s",
            budget_per_item,
            items_count,
        )
        actual_total = self.get_subtotal()
        max_allowed = budget_per_item * items_count

        self.wait_for_cart_item_images(items_count)
        self.take_screenshot("cart_page_validation.png")

        assert actual_total > 0.0, "Cart subtotal could not be retrieved."
        assert actual_total <= max_allowed, (
            f"Cart total ({actual_total}) exceeds the allowed budget ({max_allowed})."
        )
        self.logger.info("Cart total is within budget: %s <= %s", actual_total, max_allowed)

    # Backward-compatible API expected by the current tests.
    def assertCartTotalNotExceeds(self, budget_per_item: float, items_count: int) -> None:
        self.assert_cart_total_not_exceeds(budget_per_item, items_count)
