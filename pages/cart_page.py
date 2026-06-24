from playwright.sync_api import Page

from pages.base_page import BasePage
from utils.helpers import parse_price


class CartPage(BasePage):
    CART_URL = "https://cart.payments.ebay.com/"
    MAX_REMOVE_ATTEMPTS = 15

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

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self) -> None:
        self.navigate(self.CART_URL)
        self.wait_for_page_ready()
        self.pause(3000)

    def clear_cart(self) -> None:
        self.logger.info("Checking whether the cart contains stale items.")
        self.open()

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

    def assert_cart_total_not_exceeds(self, budget_per_item: float, items_count: int) -> None:
        self.logger.info(
            "Validating cart subtotal against budget_per_item=%s, items_count=%s",
            budget_per_item,
            items_count,
        )
        actual_total = self.get_subtotal()
        max_allowed = budget_per_item * items_count

        self.take_screenshot("cart_page_validation.png")

        assert actual_total > 0.0, "Cart subtotal could not be retrieved."
        assert actual_total <= max_allowed, (
            f"Cart total ({actual_total}) exceeds the allowed budget ({max_allowed})."
        )
        self.logger.info("Cart total is within budget: %s <= %s", actual_total, max_allowed)

    # Backward-compatible API expected by the current tests.
    def assertCartTotalNotExceeds(self, budget_per_item: float, items_count: int) -> None:
        self.assert_cart_total_not_exceeds(budget_per_item, items_count)
