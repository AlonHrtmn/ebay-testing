import random
from playwright.sync_api import Page
from pages.base_page import BasePage

class ProductPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Selectors for variant dropdowns (eBay usually uses select elements with classes or IDs starting with 'msku-sel')
        self.variant_selects = "select[id^='msku-sel-'], select.msku-sel"
        self.add_to_cart_btn = "#isCartBtn_btn, #atcRedesignId_btn, [data-testid='x-atc-action'] a, a:has-text('Add to cart')"
        self.cart_popup_close = "#lightbox-close, .vi-overlay-close, button.shoptile-close-btn, button[aria-label='Close overlay'], button[aria-label='Close dialog']"

    def select_random_variants(self):
        """
        Detects if there are any variant selectors on the page (both custom listbox buttons
        and native select dropdowns) and selects a random valid option for each.
        """
        # 1. Custom listbox dropdowns (modern eBay)
        buttons = self.page.locator("button[aria-haspopup='listbox']").all()
        variant_buttons = []
        for btn in buttons:
            if not btn.is_visible():
                continue
            # Check if this button is within a SKU/variant wrapper
            parent_html = btn.evaluate("el => el.parentElement ? el.parentElement.outerHTML : ''")
            is_variant = "sku" in parent_html.lower() or "msku" in parent_html.lower()
            if is_variant:
                variant_buttons.append(btn)
                
        if len(variant_buttons) > 0:
            self.logger.info(f"Found {len(variant_buttons)} custom variant dropdowns to select.")
            for index, btn in enumerate(variant_buttons):
                btn_text = btn.inner_text() or ""
                self.logger.info(f"Dropdown {index+1}: Click to open '{btn_text.strip()}'")
                
                try:
                    btn.click()
                    self.page.wait_for_timeout(1000)
                    
                    aria_controls = btn.get_attribute("aria-controls")
                    if aria_controls:
                        # Find all option elements under the controls container
                        options = self.page.locator(f"[id='{aria_controls}'] .listbox__option[role='option']").all()
                        valid_options = []
                        for opt in options:
                            val = opt.get_attribute("data-sku-value-name") or ""
                            opt_text = opt.inner_text() or ""
                            is_disabled = opt.get_attribute("aria-disabled") == "true" or "disabled" in (opt.get_attribute("class") or "").lower()
                            
                            # Skip select/placeholder options
                            if "select" in opt_text.lower() or not val:
                                continue
                                
                            # Skip options that are for accessories instead of shoes (e.g. insoles, laces, socks, pads)
                            if any(kw in opt_text.lower() for kw in ["insole", "laces", "socks", "pad", "insert", "cushion", "protector"]):
                                self.logger.info(f"Skipping custom accessory variant option: '{opt_text.strip()}'")
                                continue
                                
                            if not is_disabled:
                                valid_options.append(opt)
                                
                        if valid_options:
                            chosen_opt = random.choice(valid_options)
                            chosen_text = chosen_opt.inner_text() or ""
                            self.logger.info(f"Dropdown {index+1}: Selecting option '{chosen_text.strip()}'")
                            chosen_opt.click()
                            self.page.wait_for_timeout(2000) # Wait for page updates / price recalculations
                        else:
                            self.logger.warning(f"Dropdown {index+1}: No valid options found.")
                except Exception as e:
                    self.logger.error(f"Failed to handle custom dropdown {index+1}: {e}")
                    
        # 2. Fallback to native select dropdowns if they exist
        selects = self.page.locator("select").all()
        # Filter select elements that are visible and look like variant selectors
        variant_selects = []
        for sel in selects:
            if not sel.is_visible():
                continue
            name = sel.get_attribute("name") or ""
            id_val = sel.get_attribute("id") or ""
            # Exclude category, feedback, and other common non-variant selects
            if "feedback" in name.lower() or "gh-cat" in id_val or "category" in name.lower():
                continue
            variant_selects.append(sel)
            
        if len(variant_selects) > 0:
            self.logger.info(f"Found {len(variant_selects)} native variant dropdowns to select.")
            for index, select in enumerate(variant_selects):
                options_locator = select.locator("option")
                option_values = []
                for i in range(options_locator.count()):
                    val = options_locator.nth(i).get_attribute("value")
                    txt = options_locator.nth(i).text_content() or options_locator.nth(i).inner_text() or ""
                    
                    if val and val != "-1" and "select" not in txt.lower():
                        # Skip option values that are for accessories (e.g. insoles, laces, socks, pads)
                        if any(kw in txt.lower() for kw in ["insole", "laces", "socks", "pad", "insert", "cushion", "protector"]):
                            self.logger.info(f"Skipping native accessory variant option: '{txt.strip()}'")
                            continue
                        option_values.append(val)
                        
                if option_values:
                    chosen_val = random.choice(option_values)
                    self.logger.info(f"Native Dropdown {index+1}: Selecting option value '{chosen_val}'")
                    try:
                        select.select_option(value=chosen_val)
                        self.page.wait_for_timeout(1000)
                    except Exception as e:
                        self.logger.warning(f"Failed to select native option {chosen_val}: {e}")

    def add_to_cart(self, screenshot_name=None):
        self.logger.info("Adding item to cart...")
        
        # Check and select variants first
        self.select_random_variants()
        
        # Look for the Add to Cart button using the Playwright-native role-based selector
        # We try roles first (button/link), then fall back to standard CSS selectors if needed
        atc_button = None
        
        for role in ["button", "link"]:
            loc = self.page.get_by_role(role, name="Add to cart", exact=True)
            if loc.count() > 0 and loc.first.is_visible():
                atc_button = loc.first
                self.logger.info(f"Found Add to Cart button using Playwright role: '{role}'")
                break
                
        # CSS selector fallbacks if role fails
        if not atc_button:
            for selector in ["#isCartBtn_btn", "#atcRedesignId_btn", "[data-testid='x-atc-action'] a"]:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    atc_button = loc.first
                    self.logger.info(f"Found Add to Cart button using fallback selector: {selector}")
                    break
                
        if atc_button:
            atc_button.click()
            self.page.wait_for_load_state("load")
            self.logger.info("Clicked Add to Cart button.")
            
            # Wait for overlay popup to initiate and show
            self.page.wait_for_timeout(1500)
            
            # Wait for any active spinner loaders on the page to hide
            spinner_selectors = [
                ".ux-loading-overlay", ".loading-spinner", ".spinner", ".shoptile-loader", 
                "div[class*='loading']", "div[class*='spinner']", "svg[class*='spinner']"
            ]
            for spinner in spinner_selectors:
                try:
                    loc = self.page.locator(spinner)
                    if loc.count() > 0 and loc.first.is_visible():
                        self.logger.info(f"Waiting for loading spinner to hide: {spinner}")
                        loc.first.wait_for(state="hidden", timeout=5000)
                except Exception:
                    pass
            
            # Allow a small extra delay for the image inside the popup/drawer to render fully
            self.page.wait_for_timeout(2500)
            
            # Take the screenshot while the overlay/flyout is open
            if screenshot_name:
                self.take_screenshot(screenshot_name)
            
            # Handle potential overlay popup/modals that might block subsequent actions
            # e.g., "Add protection plan" or "Go to cart" popups
            close_btn = self.page.locator(self.cart_popup_close)
            if close_btn.count() > 0 and close_btn.first.is_visible():
                close_btn.first.click()
                self.page.wait_for_timeout(1000) # Wait for fade-out animation
                self.logger.info("Closed cart overlay/popup.")
        else:
            self.logger.error("Add to Cart button was not found or is not visible.")
            raise Exception("Add to Cart button not found on product page")
 
    def addItemsToCart(self, urls: list) -> int:
        self.logger.info(f"Starting addItemsToCart for {len(urls)} items.")
        added_count = 0
        
        for idx, url in enumerate(urls):
            self.logger.info(f"Processing item {idx+1}/{len(urls)}: {url}")
            try:
                self.navigate(url)
                screenshot_name = f"item_{idx+1}_added.png"
                self.add_to_cart(screenshot_name=screenshot_name)
                added_count += 1
            except Exception as e:
                self.logger.error(f"Failed to add item {url} to cart: {e}")
                # We save a screenshot on failure to diagnose
                self.take_screenshot(f"item_{idx+1}_failure.png")
                
        return added_count

    def assertItemsAddedToCart(self, urls: list) -> int:
        """
        Navigates to each item, adds to cart, and asserts that at least one item was added successfully.
        """
        self.logger.info("Executing addItemsToCart and asserting at least one item was added successfully...")
        items_added = self.addItemsToCart(urls)
        assert items_added > 0, "Cart failed: No items were successfully added to the cart."
        return items_added
