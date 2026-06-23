import re
from playwright.sync_api import Page
from pages.base_page import BasePage
from utils.helpers import parse_price

class CartPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.cart_url = "https://cart.payments.ebay.com/"

    def clear_cart(self):
        self.logger.info("Checking if cart needs to be cleared from previous runs...")
        self.navigate(self.cart_url)
        self.page.wait_for_load_state("load")
        self.page.wait_for_timeout(3000)
        
        # Locate all remove buttons or links
        remove_buttons = self.page.locator("button:has-text('Remove'), button[aria-label*='Remove'], a:has-text('Remove'), [data-testid='cart-remove-item']").all()
        
        if len(remove_buttons) > 0:
            self.logger.info(f"Found {len(remove_buttons)} items in cart. Clearing them to prevent stale cart state...")
            for btn in remove_buttons:
                try:
                    if btn.is_visible():
                        btn.click()
                        self.page.wait_for_timeout(2000)
                except Exception as e:
                    self.logger.warning(f"Could not click remove button: {e}")
            self.logger.info("Cart cleared successfully.")
        else:
            self.logger.info("Cart is already empty. Starting fresh run.")

    def get_subtotal(self) -> float:
        self.logger.info("Opening shopping cart to retrieve subtotal...")
        self.navigate(self.cart_url)
        self.page.wait_for_load_state("load")
        self.page.wait_for_timeout(3000) # Wait for cart details to fully render and calculate
        
        # JS-based parser to find "Items (X)" or "Subtotal" label and its corresponding price
        js_code = """
        () => {
            // Find all elements in the DOM
            let allElems = document.querySelectorAll('*');
            
            // Prioritize "Items (X)" or "Items" label to get item-only subtotal without shipping
            for (let i = allElems.length - 1; i >= 0; i--) {
                let elem = allElems[i];
                let text = (elem.innerText || '').trim();
                if (text && /^(?:Items?|Item\\s*subtotal)\\s*(?:\\(\\d+\\))?$/i.test(text) && text.length < 50) {
                    let parent = elem.parentElement;
                    if (parent) {
                        let parentText = parent.innerText || '';
                        let matches = parentText.match(/(?:ILS|\\$|₪|£)\\s*\\d+(?:[.,]\\d+)?/gi);
                        if (matches && matches.length > 0) {
                            return matches[matches.length - 1];
                        }
                    }
                }
            }
            
            // Fallback to "Subtotal" label
            for (let i = allElems.length - 1; i >= 0; i--) {
                let elem = allElems[i];
                if (elem.innerText && elem.innerText.includes('Subtotal') && elem.innerText.length < 100) {
                    let parent = elem.parentElement;
                    if (parent) {
                        let parentText = parent.innerText || '';
                        let matches = parentText.match(/(?:ILS|\\$|₪|£)\\s*\\d+(?:[.,]\\d+)?/gi);
                        if (matches && matches.length > 0) {
                            // Take the last match since the price is typically placed after the label
                            return matches[matches.length - 1];
                        }
                    }
                }
            }
            
            // Fallback 1: search page body text for patterns like "Subtotal (X items): ILS Y.YY"
            let bodyText = document.body.innerText || '';
            let matches = bodyText.match(/Subtotal\\s*\\(?\\d*\\s*items?\\)?\\s*(?:ILS|\\$|₪|£)\\s*\\d+(?:[.,]\\d+)?/gi);
            if (matches && matches.length > 0) {
                return matches[0];
            }
            
            // Fallback 2: search within elements that look like order summaries
            let summary = document.querySelector('[data-testid="cart-summary"]');
            if (summary) {
                let text = summary.innerText || '';
                let matches = text.match(/(?:ILS|\\$|₪|£)\\s*\\d+(?:[.,]\\d+)?/gi);
                if (matches && matches.length > 0) {
                    return matches[matches.length - 1];
                }
            }
            
            return "";
        }
        """
        
        subtotal_text = self.page.evaluate(js_code)
        self.logger.info(f"Extracted subtotal text using robust DOM parser: '{subtotal_text}'")
        
        if not subtotal_text:
            self.logger.error("Could not find any subtotal elements on the cart page.")
            subtotal_text = "0.0"
            
        return parse_price(subtotal_text)

    def assertCartTotalNotExceeds(self, budget_per_item: float, items_count: int):
        self.logger.info(f"Executing assertCartTotalNotExceeds: budget_per_item={budget_per_item}, items_count={items_count}")
        
        actual_total = self.get_subtotal()
        max_allowed = budget_per_item * items_count
        
        self.logger.info(f"Cart Subtotal: {actual_total}. Max Allowed Budget: {max_allowed} ({budget_per_item} * {items_count})")
        
        # Take a screenshot of the cart page
        self.take_screenshot("cart_page_validation.png")
        
        # Perform assertion
        assert actual_total > 0.0, "Assertion Failed! Cart subtotal could not be retrieved (is 0.0)."
        assert actual_total <= max_allowed, (
            f"Assertion Failed! Cart total ({actual_total}) exceeds the allowed budget of ({max_allowed})."
        )
        self.logger.info("Assertion Passed! Cart total is within the budget.")
