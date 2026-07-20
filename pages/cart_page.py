import os
import time
from urllib.parse import urlparse

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)

from pages.base_page import BasePage
from utils.exceptions import EbayVerificationRequired
from utils.helpers import (
    convert_currency,
    parse_price,
    parse_price_and_currency,
)


class CartPage(BasePage):
    EXPECTED_CART_CURRENCY = "USD"
    CART_URL = "https://cart.ebay.com/"
    CART_HOST_MARKERS = (
        "cart.payments.ebay.com",
        "cart.ebay.com",
    )

    MAX_REMOVE_ATTEMPTS = 15

    VERIFICATION_TIMEOUT_MS = int(
        os.getenv(
            "EBAY_VERIFICATION_TIMEOUT_MS",
            "60000",
        )
    )

    REMOVE_ITEM_SELECTOR = (
        "button:has-text('Remove'), "
        "button[aria-label*='Remove'], "
        "a:has-text('Remove'), "
        "[data-testid='cart-remove-item']"
    )

    CART_ITEM_SELECTOR = (
        "[data-test-id='cart-item'], "
        "[data-testid='cart-item'], "
        ".cart-bucket-lineitem, "
        ".cart-item"
    )

    CART_ITEM_IMAGE_SELECTOR = (
        "[data-test-id='cart-item'] img, "
        "[data-testid='cart-item'] img, "
        ".cart-bucket-lineitem img, "
        ".cart-item img"
    )

    CART_READY_SCRIPT = r"""
    () => {
        const bodyText = (document.body?.innerText || '').toLowerCase();

        const hasCartContent =
            document.querySelector(
                '[data-testid="cart-summary"], '
                '[data-test-id="cart-item"], '
                '[data-testid="cart-item"], '
                '.cart-bucket-lineitem, '
                '.cart-item'
            ) !== null;

        const isEmpty =
            bodyText.includes('your cart is empty') ||
            bodyText.includes('shopping cart is empty');

        return document.readyState !== 'loading' &&
            (hasCartContent || isEmpty);
    }
    """

    SUBTOTAL_SCRIPT = r"""
    () => {
        const currencyPricePattern =
            /(?:ILS|\$|\u20aa|\u00a3|GBP|EUR|€)\s*\d+(?:[.,]\d+)?/gi;

        const visible = (el) => {
            if (!el) return false;
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                rect.width > 0 &&
                rect.height > 0
            );
        };

        const candidates = [
            '[data-testid="cart-summary"]',
            '[data-test-id="cart-summary"]',
            '.cart-summary',
            '.summary'
        ];

        for (const selector of candidates) {
            const root = document.querySelector(selector);
            if (!visible(root)) continue;

            const text = root.innerText || '';
            const lines = text
                .split('\n')
                .map(line => line.trim())
                .filter(Boolean);

            for (let i = 0; i < lines.length; i++) {
                if (!/^subtotal|^items?\s*subtotal/i.test(lines[i])) continue;

                for (let j = i; j < Math.min(i + 4, lines.length); j++) {
                    const match = lines[j].match(currencyPricePattern);
                    if (match?.length) return match.at(-1);
                }
            }

            const matches = text.match(currencyPricePattern);
            if (matches?.length) return matches.at(-1);
        }

        const elements = [...document.querySelectorAll('*')].filter(visible);

        const subtotalLabels = [
            /^(?:items?|item\s*subtotal)\s*(?:\(\d+\))?$/i,
            /^subtotal/i,
        ];

        for (const labelPattern of subtotalLabels) {
            for (let i = elements.length - 1; i >= 0; i--) {
                const text = (elements[i].innerText || '').trim();

                if (
                    !text ||
                    text.length > 100 ||
                    !labelPattern.test(text)
                ) {
                    continue;
                }

                const parentText =
                    elements[i].parentElement?.innerText || '';

                const matches =
                    parentText.match(currencyPricePattern);

                if (matches?.length) {
                    return matches.at(-1);
                }
            }
        }

        const bodyText = document.body?.innerText || '';

        const inlineMatch = bodyText.match(
            /Subtotal\s*\(?\d*\s*items?\)?\s*(?:ILS|\$|\u20aa|\u00a3|GBP|EUR|€)\s*\d+(?:[.,]\d+)?/i
        );

        return inlineMatch?.[0] || '';
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
                !placeholderTerms.some(
                    term => source.includes(term)
                ) &&
                rect.width >= 40 &&
                rect.height >= 40 &&
                (img.naturalWidth || img.width || 0) >= 40 &&
                (img.naturalHeight || img.height || 0) >= 40;
        };

        const preferredSelectors = [
            '[data-test-id="cart-item"] img',
            '[data-testid="cart-item"] img',
            '.cart-bucket-lineitem img',
            '.cart-item img'
        ];

        let images = [];

        for (const selector of preferredSelectors) {
            images.push(
                ...document.querySelectorAll(selector)
            );
        }

        if (!images.length) {
            images = [
                ...document.querySelectorAll(
                    'img[src*="ebayimg.com"]'
                )
            ];
        }

        const unique = [...new Set(images)];

        return unique.filter(isRealImage).length >= expectedCount;
    }
    """

    def open(self) -> None:
        self.logger.info(
            "Navigating to %s",
            self.CART_URL,
        )

        try:
            self.page.goto(
                self.CART_URL,
                wait_until="domcontentloaded",
            )
        except PlaywrightError as exc:
            if (
                "net::ERR_ABORTED" not in str(exc)
                or not self.is_cart_page()
            ):
                raise

            self.logger.warning(
                "Cart navigation aborted after reaching "
                "an eBay cart URL: %s",
                self.page.url,
            )

        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError as exc:
            if not self.is_cart_page():
                raise

            self.logger.warning(
                "Cart DOM ready wait did not complete: %s",
                exc,
            )

        self.raise_if_verification_required()
        self.wait_for_cart_ready()

    def wait_for_cart_ready(self) -> None:
        try:
            self.page.wait_for_function(
                self.CART_READY_SCRIPT,
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
        except Exception as exc:
            self.logger.warning(
                "Cart-specific readiness condition "
                "did not complete: %s",
                exc,
            )

    def is_cart_page(self) -> bool:
        parsed = urlparse(self.page.url or "")

        return any(
            parsed.netloc.endswith(marker)
            for marker in self.CART_HOST_MARKERS
        )

    def raise_if_verification_required(self) -> None:
        if not self.is_verification_page():
            return

        is_headless = (
            os.getenv("PLAYWRIGHT_HEADLESS") == "1"
            or os.getenv("EBAY_HEADLESS") == "1"
            or "CI" in os.environ
        )

        if is_headless:
            self.logger.warning(
                "eBay verification page detected "
                "in headless mode. Aborting immediately."
            )
            raise EbayVerificationRequired(
                "eBay served a human-verification page "
                "while opening the cart."
            )

        self.logger.warning(
            "eBay verification detected; waiting up to "
            "%s seconds for manual completion.",
            self.VERIFICATION_TIMEOUT_MS // 1000,
        )

        deadline = (
            time.monotonic()
            + self.VERIFICATION_TIMEOUT_MS / 1000
        )

        while time.monotonic() < deadline:
            self.pause(1000)

            if not self.is_verification_page():
                self.logger.info(
                    "eBay verification completed; "
                    "continuing cart flow."
                )
                return

        raise EbayVerificationRequired(
            "eBay served a human-verification page "
            "while opening the cart."
        )

    def is_verification_page(self) -> bool:
        try:
            page_text = self.page.locator(
                "body"
            ).inner_text(
                timeout=2000
            )
        except Exception:
            return "/splashui/" in self.page.url

        lower = page_text.lower()

        return (
            "/splashui/" in self.page.url
            or "please verify yourself" in lower
            or "i am human" in lower
        )

    def clear_cart(self) -> None:
        self.logger.info(
            "Checking whether the cart contains stale items."
        )

        try:
            self.open()
        except PlaywrightError as exc:
            if "net::ERR_ABORTED" not in str(exc):
                raise

            self.logger.warning(
                "Skipping cart cleanup because eBay "
                "aborted empty-cart navigation: %s",
                exc,
            )
            return

        removed_count = 0

        for _ in range(self.MAX_REMOVE_ATTEMPTS):
            remove_button = self.first_visible_locator(
                self.REMOVE_ITEM_SELECTOR,
                timeout=1000,
                warn_on_timeout=False,
            )

            if remove_button is None:
                break

            before_count = self.page.evaluate(
                """
                () => {
                    const buttons = document.querySelectorAll(
                        "button, a, [data-testid='cart-remove-item']"
                    );

                    return [...buttons].filter(el => {
                        const text = (
                            el.innerText ||
                            el.getAttribute('aria-label') ||
                            ''
                        ).toLowerCase();

                        const rect = el.getBoundingClientRect();

                        return (
                            text.includes('remove') &&
                            rect.width > 0 &&
                            rect.height > 0
                        );
                    }).length;
                }
                """,
            )

            try:
                remove_button.click()
                removed_count += 1

                try:
                    self.page.wait_for_function(
                        """
                        previousCount => {
                            const buttons = document.querySelectorAll(
                                "button, a, [data-testid='cart-remove-item']"
                            );

                            const visibleRemove = [...buttons].filter(el => {
                                const text = (
                                    el.innerText ||
                                    el.getAttribute('aria-label') ||
                                    ''
                                ).toLowerCase();

                                const rect = el.getBoundingClientRect();

                                return (
                                    text.includes('remove') &&
                                    rect.width > 0 &&
                                    rect.height > 0
                                );
                            });

                            return visibleRemove.length < previousCount;
                        }
                        """,
                        arg=before_count,
                        timeout=5000,
                    )
                except Exception:
                    self.pause(500)

            except Exception as exc:
                self.logger.warning(
                    "Could not remove cart item: %s",
                    exc,
                )
                self.pause(500)

        if removed_count:
            self.logger.info(
                "Removed %s stale cart item(s).",
                removed_count,
            )
        else:
            self.logger.info(
                "Cart is already empty."
            )

    def get_subtotal_text(self) -> str:
        subtotal_text = (
            self.page.evaluate(
                self.SUBTOTAL_SCRIPT
            )
            or ""
        )

        self.logger.info(
            "Extracted subtotal text: '%s'",
            subtotal_text,
        )

        return subtotal_text

    def get_subtotal(self) -> float:
        self.logger.info(
            "Opening shopping cart to retrieve subtotal."
        )

        self.open()

        subtotal = parse_price(
            self.get_subtotal_text()
        )

        if subtotal <= 0.0:
            self.logger.error(
                "Could not retrieve a positive cart subtotal."
            )

        return subtotal

    def get_subtotal_amount_and_currency(self) -> tuple[float, str | None]:
        self.logger.info(
            "Opening shopping cart to retrieve subtotal amount and currency."
        )

        self.open()

        subtotal_text = self.get_subtotal_text()
        amount, currency = parse_price_and_currency(subtotal_text)

        if amount <= 0.0:
            self.logger.error(
                "Could not retrieve a positive cart subtotal."
            )

        if currency is None:
            self.logger.warning(
                "Could not determine cart currency from subtotal text: %s",
                subtotal_text,
            )

        return amount, currency

    def wait_for_cart_item_images(
        self,
        expected_count: int,
    ) -> None:
        if expected_count <= 0:
            return

        self.logger.info(
            "Waiting for %s cart item image(s) to load.",
            expected_count,
        )

        images = self.page.locator(
            self.CART_ITEM_IMAGE_SELECTOR
        )

        if images.count() == 0:
            images = self.page.locator(
                "img[src*='ebayimg.com']"
            )

        for index in range(
            min(images.count(), expected_count * 3)
        ):
            image = images.nth(index)

            try:
                image.scroll_into_view_if_needed(
                    timeout=2000
                )
            except Exception:
                continue

        self.page.evaluate(
            "window.scrollTo(0, 0)"
        )

        try:
            self.page.wait_for_function(
                self.CART_IMAGES_READY_SCRIPT,
                arg=expected_count,
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
        except Exception as exc:
            self.logger.warning(
                "Cart images were not all ready "
                "before screenshot: %s",
                exc,
            )

    def assert_cart_total_not_exceeds(
        self,
        budget_per_item: float,
        items_count: int,
        budget_currency: str = "USD",
    ) -> None:
        self.logger.info(
            "Validating cart subtotal against "
            "budget_per_item=%s, items_count=%s, budget_currency=%s",
            budget_per_item,
            items_count,
            budget_currency,
        )

        assert items_count > 0, (
            "items_count must be greater than zero."
        )

        actual_total, actual_currency = (
            self.get_subtotal_amount_and_currency()
        )
        max_allowed = (
            budget_per_item * items_count
        )

        if actual_currency is None:
            raise AssertionError(
                "Could not determine the cart subtotal currency. "
                "Budget comparison requires a known currency."
            )

        if actual_currency != budget_currency:
            try:
                converted_total = convert_currency(
                    actual_total,
                    actual_currency,
                    budget_currency,
                )
            except ValueError as exc:
                raise AssertionError(
                    "Could not compare cart subtotal across currencies: "
                    f"{exc} Raw subtotal: {actual_currency} {actual_total}"
                ) from exc

            self.logger.info(
                "Converted cart subtotal from %s %s to %s %s.",
                actual_total,
                actual_currency,
                budget_currency,
                converted_total,
            )
            actual_total = converted_total

        self.wait_for_cart_item_images(
            items_count
        )

        self.take_screenshot(
            "cart_page_validation.png"
        )

        assert actual_total > 0.0, (
            "Cart subtotal could not be retrieved."
        )

        assert actual_total <= max_allowed, (
            f"Cart total ({actual_total:.2f} {budget_currency}) exceeds "
            f"the allowed budget ({max_allowed:.2f} {budget_currency})."
        )

        self.logger.info(
            "Cart total is within budget: %s <= %s",
            actual_total,
            max_allowed,
        )

    # Backward-compatible API expected by current tests.
    def assertCartTotalNotExceeds(
        self,
        budget_per_item: float,
        items_count: int,
        budget_currency: str = "USD",
    ) -> None:
        self.assert_cart_total_not_exceeds(
            budget_per_item,
            items_count,
            budget_currency=budget_currency,
        )
