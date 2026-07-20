import random
from typing import Literal, Optional

from playwright.sync_api import Locator, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage
from pages.search_page import SearchPage
from utils.helpers import parse_price


class ProductPageError(Exception):
    """Base exception for ProductPage failures."""


class ProductValidationError(ProductPageError):
    """Raised when a product does not satisfy validation rules."""


class VariantSelectionError(ProductPageError):
    """Raised when required variants cannot be selected."""


class ProductPriceUnavailableError(ProductPageError):
    """Raised when the selected SKU price cannot be determined."""


class ProductOverBudgetError(ProductPageError):
    """Raised when the selected SKU exceeds the configured budget."""


class AddToCartError(ProductPageError):
    """Raised when the Add to Cart action cannot be completed."""


class ProductPage(BasePage):
    CUSTOM_VARIANT_BUTTONS = "button[aria-haspopup='listbox']"

    NATIVE_VARIANT_SELECTS = (
        "select[id^='msku-sel-'], "
        "select.msku-sel, "
        "select[name*='sku' i], "
        "select[id*='sku' i]"
    )

    ADD_TO_CART_SELECTORS = (
        "#isCartBtn_btn, "
        "#atcRedesignId_btn, "
        "[data-testid='x-atc-action'] a, "
        "[data-testid='x-atc-action'] button, "
        "a:has-text('Add to cart'), "
        "button:has-text('Add to cart'), "
        "[data-testid*='add-to-cart'], "
        "button[id*='add-to-cart'], "
        "button[class*='add-to-cart'], "
        "a[data-testid*='add-to-cart']"
    )

    CART_POPUP_CLOSE = (
        "#lightbox-close, "
        ".vi-overlay-close, "
        "button.shoptile-close-btn, "
        "button[aria-label='Close overlay'], "
        "button[aria-label='Close dialog']"
    )

    PRODUCT_IMAGE_SELECTORS = (
        "#PicturePanel img, "
        "[data-testid='ux-image-carousel-container'] img, "
        ".ux-image-carousel-item img, "
        ".ux-image-grid img, "
        "img[src*='i.ebayimg.com']"
    )

    PRICE_SELECTORS = (
        ".x-price-primary, "
        "[data-testid='x-price-primary'], "
        ".vi-price, "
        "#prcIsum, "
        "#mm-saleDscPrc, "
        "[itemprop='price']"
    )

    ACCESSORY_KEYWORDS = (
        "insole",
        "insoles",
        "lace",
        "laces",
        "shoelace",
        "shoelaces",
        "sock",
        "socks",
        "pad",
        "pads",
        "insert",
        "inserts",
        "cushion",
        "cushions",
        "protector",
        "protectors",
    )

    PLACEHOLDER_OPTION_TERMS = (
        "select",
        "choose",
        "please select",
    )

    VARIANT_UPDATE_TIMEOUT_MS = 8000

    @staticmethod
    def _normalize(value: Optional[str]) -> str:
        return (value or "").strip().casefold()

    def _is_accessory_variant(self, text: str) -> bool:
        normalized = self._normalize(text)
        return any(
            keyword in normalized
            for keyword in self.ACCESSORY_KEYWORDS
        )

    def _is_placeholder_option(self, text: str) -> bool:
        normalized = self._normalize(text)
        return any(
            term in normalized
            for term in self.PLACEHOLDER_OPTION_TERMS
        )

    def product_has_real_image(self) -> bool:
        try:
            self.page.wait_for_selector(
                self.PRODUCT_IMAGE_SELECTORS,
                state="attached",
                timeout=5000,
            )
        except PlaywrightTimeoutError:
            self.logger.warning("No product image selector appeared.")
            return False

        images = self.page.locator(self.PRODUCT_IMAGE_SELECTORS)

        for index in range(images.count()):
            image = images.nth(index)

            try:
                if not image.is_visible():
                    continue

                image_url = SearchPage.first_image_url(image)
                if not SearchPage.is_real_image_url(image_url):
                    continue

                valid_dimensions = image.evaluate(
                    """
                    img => {
                        const rect = img.getBoundingClientRect();
                        const width = img.naturalWidth || img.width || 0;
                        const height = img.naturalHeight || img.height || 0;

                        return (
                            rect.width >= 80 &&
                            rect.height >= 80 &&
                            width >= 80 &&
                            height >= 80
                        );
                    }
                    """
                )

                if valid_dimensions:
                    return True

            except Exception:
                continue

        return False

    def _get_custom_variant_buttons(self) -> list[Locator]:
        result: list[Locator] = []
        buttons = self.page.locator(self.CUSTOM_VARIANT_BUTTONS)

        for index in range(buttons.count()):
            button = buttons.nth(index)

            try:
                if not button.is_visible():
                    continue

                html = button.evaluate(
                    """
                    el => {
                        const parts = [
                            el.outerHTML || '',
                            el.parentElement?.outerHTML || '',
                            el.closest('[class*="sku"], [id*="sku"]')?.outerHTML || ''
                        ];
                        return parts.join(' ').toLowerCase();
                    }
                    """
                )

                if "sku" in html or "msku" in html:
                    result.append(button)

            except Exception:
                continue

        return result

    def _get_valid_custom_options(
        self,
        button: Locator,
    ) -> list[Locator]:
        aria_controls = button.get_attribute("aria-controls")
        if not aria_controls:
            return []

        options = self.page.locator(
            f"[id='{aria_controls}'] [role='option']"
        )

        valid: list[Locator] = []

        for index in range(options.count()):
            option = options.nth(index)

            try:
                text = (
                    option.inner_text()
                    or option.text_content()
                    or ""
                ).strip()

                classes = self._normalize(
                    option.get_attribute("class")
                )

                disabled = (
                    option.get_attribute("aria-disabled") == "true"
                    or "disabled" in classes
                )

                if disabled:
                    continue

                if not text or self._is_placeholder_option(text):
                    continue

                if self._is_accessory_variant(text):
                    self.logger.info(
                        "Skipping accessory variant option: '%s'",
                        text,
                    )
                    continue

                valid.append(option)

            except Exception:
                continue

        return valid

    def _wait_for_variant_update(self) -> None:
        try:
            self.page.wait_for_function(
                r"""
                () => {
                    const busy = [
                        ...document.querySelectorAll(
                            '[aria-busy="true"], .ux-loading-overlay, .loading-spinner, .spinner'
                        )
                    ];

                    return busy.every(el => {
                        const style = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return (
                            style.display === 'none' ||
                            style.visibility === 'hidden' ||
                            rect.width === 0 ||
                            rect.height === 0
                        );
                    });
                }
                """,
                timeout=self.VARIANT_UPDATE_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            self.pause(250)

    def _select_custom_variants(self) -> bool:
        initial_buttons = self._get_custom_variant_buttons()
        if not initial_buttons:
            return False

        self.logger.info(
            "Found %s custom variant dropdown(s).",
            len(initial_buttons),
        )

        for variant_index in range(len(initial_buttons)):
            buttons = self._get_custom_variant_buttons()

            if variant_index >= len(buttons):
                break

            button = buttons[variant_index]

            try:
                self.dismiss_blocking_overlays(
                    f"opening custom variant {variant_index + 1}"
                )
                button.click(timeout=5000)

                aria_controls = button.get_attribute("aria-controls")
                if aria_controls:
                    try:
                        self.page.locator(
                            f"[id='{aria_controls}']"
                        ).wait_for(
                            state="visible",
                            timeout=2500,
                        )
                    except PlaywrightTimeoutError:
                        pass

                options = self._get_valid_custom_options(button)
                if not options:
                    self.page.keyboard.press("Escape")
                    raise VariantSelectionError(
                        f"No valid options found for custom variant "
                        f"{variant_index + 1}."
                    )

                chosen = random.choice(options)
                chosen_text = (
                    chosen.inner_text()
                    or chosen.text_content()
                    or ""
                ).strip()

                self.logger.info(
                    "Selecting custom variant %s: '%s'",
                    variant_index + 1,
                    chosen_text,
                )

                chosen.click(timeout=5000)
                self._wait_for_variant_update()

            except VariantSelectionError:
                raise
            except Exception as exc:
                try:
                    self.page.keyboard.press("Escape")
                except Exception:
                    pass
                raise VariantSelectionError(
                    f"Failed selecting custom variant "
                    f"{variant_index + 1}: {exc}"
                ) from exc

        return True

    def _get_native_variant_selects(self) -> list[Locator]:
        result: list[Locator] = []
        selects = self.page.locator(self.NATIVE_VARIANT_SELECTS)

        for index in range(selects.count()):
            select = selects.nth(index)
            try:
                if select.is_visible():
                    result.append(select)
            except Exception:
                continue

        return result

    def _get_valid_native_values(
        self,
        select: Locator,
    ) -> list[str]:
        values: list[str] = []
        options = select.locator("option")

        for index in range(options.count()):
            option = options.nth(index)

            value = (
                option.get_attribute("value")
                or ""
            ).strip()

            text = (
                option.text_content()
                or option.inner_text()
                or ""
            ).strip()

            if option.get_attribute("disabled") is not None:
                continue

            if not value or value == "-1":
                continue

            if self._is_placeholder_option(text):
                continue

            if self._is_accessory_variant(text):
                self.logger.info(
                    "Skipping accessory native option: '%s'",
                    text,
                )
                continue

            values.append(value)

        return values

    def _select_native_variants(self) -> bool:
        initial_selects = self._get_native_variant_selects()
        if not initial_selects:
            return False

        self.logger.info(
            "Found %s native variant dropdown(s).",
            len(initial_selects),
        )

        for variant_index in range(len(initial_selects)):
            selects = self._get_native_variant_selects()

            if variant_index >= len(selects):
                break

            select = selects[variant_index]
            values = self._get_valid_native_values(select)

            if not values:
                raise VariantSelectionError(
                    f"No valid options found for native variant "
                    f"{variant_index + 1}."
                )

            chosen_value = random.choice(values)

            try:
                self.logger.info(
                    "Selecting native variant %s value '%s'.",
                    variant_index + 1,
                    chosen_value,
                )
                select.select_option(value=chosen_value)
                self._wait_for_variant_update()
            except Exception as exc:
                raise VariantSelectionError(
                    f"Failed selecting native variant "
                    f"{variant_index + 1}: {exc}"
                ) from exc

        return True

    def select_random_variants(self) -> None:
        self.dismiss_blocking_overlays("before variant selection")

        # Prefer the visible custom UI. Native selects are used only
        # when no custom variant UI is available, preventing duplicates.
        if self._select_custom_variants():
            return

        self._select_native_variants()

    def get_product_price(self) -> Optional[float]:
        prices = self.page.locator(self.PRICE_SELECTORS)

        for index in range(prices.count()):
            element = prices.nth(index)

            try:
                if not element.is_visible():
                    continue

                text = (
                    element.inner_text()
                    or element.text_content()
                    or ""
                ).strip()

                if not text:
                    continue

                value = parse_price(text)
                if value > 0:
                    self.logger.info(
                        "Product price parsed: %s (raw='%s')",
                        value,
                        text,
                    )
                    return float(value)

            except Exception:
                continue

        # Narrow fallback only inside the summary area.
        try:
            text = self.page.evaluate(
                r"""
                () => {
                    const root = document.querySelector('#RightSummaryPanel');
                    if (!root) return '';

                    const selectors = [
                        '.x-price-primary',
                        '[data-testid="x-price-primary"]',
                        '[itemprop="price"]',
                        '.vi-price'
                    ];

                    for (const selector of selectors) {
                        const el = root.querySelector(selector);
                        const text = (el?.innerText || el?.textContent || '').trim();
                        if (text) return text;
                    }

                    const body = root.innerText || '';
                    const match = body.match(
                        /(?:ILS|US\s*\$|\$|₪|£|GBP|EUR|€)\s*\d+(?:[.,]\d+)?/i
                    );
                    return match?.[0] || '';
                }
                """
            )

            if text:
                value = parse_price(text)
                if value > 0:
                    return float(value)

        except Exception as exc:
            self.logger.warning(
                "Could not determine product price: %s",
                exc,
            )

        return None

    def _find_add_to_cart_button(
        self,
        timeout_ms: int = 10000,
    ) -> Optional[Locator]:
        attempts = max(1, timeout_ms // 250)

        for attempt in range(attempts):
            roles: list[Literal["button", "link"]] = [
                "button",
                "link",
            ]

            for role in roles:
                locator = self.page.get_by_role(
                    role,
                    name="Add to cart",
                    exact=False,
                )

                try:
                    if (
                        locator.count() > 0
                        and locator.first.is_visible()
                        and locator.first.is_enabled()
                    ):
                        self.logger.info(
                            "Found Add to Cart using role '%s' "
                            "(attempt %s).",
                            role,
                            attempt + 1,
                        )
                        return locator.first
                except Exception:
                    pass

            fallback = self.page.locator(
                self.ADD_TO_CART_SELECTORS
            )

            for index in range(fallback.count()):
                candidate = fallback.nth(index)

                try:
                    if (
                        candidate.is_visible()
                        and candidate.is_enabled()
                    ):
                        self.logger.info(
                            "Found Add to Cart fallback "
                            "(attempt %s, candidate %s).",
                            attempt + 1,
                            index,
                        )
                        return candidate
                except Exception:
                    continue

            self.pause(250)

        return None

    def _wait_for_add_to_cart_reaction(
        self,
        timeout_ms: int = 10000,
    ) -> None:
        """
        ProductPage only verifies the immediate UI reaction.
        CartPage remains the authority for final cart validation.
        """
        script = r"""
        () => {
            const text = (document.body.innerText || '').toLowerCase();

            const successText =
                text.includes('added to your cart') ||
                text.includes('added to cart') ||
                text.includes('view in cart');

            const dialog = [...document.querySelectorAll('[role="dialog"]')]
                .some(el => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });

            const variantError =
                text.includes('please select') &&
                (
                    text.includes('size') ||
                    text.includes('color') ||
                    text.includes('colour') ||
                    text.includes('variation')
                );

            const busy = [...document.querySelectorAll(
                '[aria-busy="true"], .ux-loading-overlay, .loading-spinner, .spinner, .lightbox-dialog__window--loading'
            )].some(el => {
                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            });

            return {
                success: (successText || dialog) && !busy,
                variantError
            };
        }
        """

        attempts = max(1, timeout_ms // 250)

        for _ in range(attempts):
            try:
                result = self.page.evaluate(script) or {}

                if result.get("variantError"):
                    raise AddToCartError(
                        "eBay rejected Add to Cart because a required "
                        "variant was not selected."
                    )

                if result.get("success"):
                    return

            except AddToCartError:
                raise
            except Exception:
                pass

            self.pause(250)

        self.logger.warning(
            "No explicit Add to Cart confirmation was detected. "
            "Continuing because CartPage performs final validation."
        )

    def _close_cart_popup_if_present(self) -> None:
        close_buttons = self.page.locator(
            self.CART_POPUP_CLOSE
        )

        for index in range(close_buttons.count()):
            button = close_buttons.nth(index)

            try:
                if not button.is_visible():
                    continue

                button.click(timeout=3000)
                self.logger.info("Closed cart overlay/popup.")
                return

            except Exception:
                continue

    def add_to_cart(
        self,
        max_price: Optional[float] = None,
        screenshot_name: Optional[str] = None,
        require_real_image: bool = True,
    ) -> None:
        self.logger.info("Preparing product for Add to Cart.")

        self.dismiss_blocking_overlays(
            "before product validation"
        )

        if require_real_image and not self.product_has_real_image():
            raise ProductValidationError(
                "Product does not have a verifiable real image."
            )

        # Variants must be chosen before checking the final SKU price.
        self.select_random_variants()

        if max_price is not None:
            current_price = self.get_product_price()

            if current_price is None:
                raise ProductPriceUnavailableError(
                    "Could not determine the selected product price."
                )

            if current_price > max_price:
                raise ProductOverBudgetError(
                    f"Selected product price {current_price:.2f} "
                    f"exceeds budget limit {max_price:.2f}."
                )

        button = self._find_add_to_cart_button()

        if button is None:
            raise AddToCartError(
                "Add to Cart button was not found or actionable."
            )

        self.dismiss_blocking_overlays(
            "before Add to Cart click"
        )

        try:
            button.click(timeout=5000)
        except Exception as exc:
            raise AddToCartError(
                f"Failed clicking Add to Cart: {exc}"
            ) from exc

        self.logger.info("Clicked Add to Cart.")

        self._wait_for_add_to_cart_reaction()

        if screenshot_name:
            self.take_screenshot(screenshot_name)

        self._close_cart_popup_if_present()

    def add_items_to_cart(
        self,
        urls: list[str],
        max_price: Optional[float] = None,
        desired_count: Optional[int] = None,
        require_real_image: bool = True,
    ) -> int:
        self.logger.info(
            "Starting add_items_to_cart for %s candidate item(s).",
            len(urls),
        )

        target_count = (
            desired_count
            if desired_count is not None
            else len(urls)
        )

        if target_count < 0:
            raise ValueError(
                "desired_count cannot be negative."
            )

        added_count = 0

        for index, url in enumerate(urls):
            if added_count >= target_count:
                break

            self.logger.info(
                "Processing item %s/%s: %s",
                index + 1,
                len(urls),
                url,
            )

            try:
                self.navigate(url)
                self.dismiss_blocking_overlays(
                    "after product page load"
                )

                screenshot_name = (
                    f"item_{added_count + 1}_added.png"
                )

                self.add_to_cart(
                    max_price=max_price,
                    screenshot_name=screenshot_name,
                    require_real_image=require_real_image,
                )

                added_count += 1

            except (
                ProductValidationError,
                VariantSelectionError,
                ProductPriceUnavailableError,
                ProductOverBudgetError,
                AddToCartError,
            ) as exc:
                self.logger.warning(
                    "Skipping candidate %s: %s",
                    url,
                    exc,
                )
                self._take_failure_screenshot(index)

            except Exception as exc:
                self.logger.exception(
                    "Unexpected failure while adding %s: %s",
                    url,
                    exc,
                )
                self._take_failure_screenshot(index)

            remaining = len(urls) - index - 1

            if (
                added_count < target_count
                and remaining > 0
            ):
                self.logger.info(
                    "Need %s more item(s); %s backup candidate(s) remain.",
                    target_count - added_count,
                    remaining,
                )

        return added_count

    def _take_failure_screenshot(
        self,
        index: int,
    ) -> None:
        try:
            self.take_screenshot(
                f"item_{index + 1}_failure.png"
            )
        except Exception as exc:
            self.logger.warning(
                "Could not take failure screenshot: %s",
                exc,
            )

    def assert_items_added_to_cart(
        self,
        urls: list[str],
        max_price: Optional[float] = None,
        desired_count: Optional[int] = None,
        require_real_image: bool = True,
    ) -> int:
        items_added = self.add_items_to_cart(
            urls=urls,
            max_price=max_price,
            desired_count=desired_count,
            require_real_image=require_real_image,
        )

        assert items_added > 0, (
            "Cart failed: no items were successfully added."
        )

        if desired_count is not None:
            assert items_added == desired_count, (
                f"Cart added {items_added} item(s), "
                f"expected {desired_count}."
            )

        return items_added

    # Backward-compatible API expected by current tests.
    def addItemsToCart(
        self,
        urls: list,
        max_price: Optional[float] = None,
        desired_count: Optional[int] = None,
    ) -> int:
        return self.add_items_to_cart(
            urls=urls,
            max_price=max_price,
            desired_count=desired_count,
        )

    def assertItemsAddedToCart(
        self,
        urls: list,
        max_price: Optional[float] = None,
        desired_count: Optional[int] = None,
    ) -> int:
        return self.assert_items_added_to_cart(
            urls=urls,
            max_price=max_price,
            desired_count=desired_count,
        )
