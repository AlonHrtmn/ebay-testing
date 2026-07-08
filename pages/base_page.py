import re
from pathlib import Path
from typing import Literal, Optional
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError
from utils.logger import setup_logger

Selector = str


class BasePage:
    """Shared Playwright helpers for all page objects."""

    DEFAULT_TIMEOUT_MS = 10_000
    SHORT_TIMEOUT_MS = 5_000
    FALLBACK_SELECTOR_TIMEOUT_MS = 1_000
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
    BLOCKING_OVERLAY_SELECTORS = (
        "[data-testid='x-onboarding-modal'][aria-hidden='false']",
        ".x-onboarding-modal[aria-hidden='false']",
        ".lightbox-dialog[aria-modal='true']",
        "[role='dialog'][aria-modal='true']",
    )
    OVERLAY_DISMISS_SELECTORS = (
        "button[aria-label='Close']",
        "button[aria-label='Close dialog']",
        "button[aria-label='Close overlay']",
        "button[aria-label*='close' i]",
        "#lightbox-close",
        ".vi-overlay-close",
        "button:has-text('Got it')",
        "button:has-text('Continue')",
        "button:has-text('No thanks')",
        "button:has-text('Maybe later')",
        "button:has-text('Skip')",
    )

    def __init__(self, page: Page):
        self.page = page
        self.logger = setup_logger(self.__class__.__name__)

    def navigate(
        self,
        url: str,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] | None = "load",
        timeout: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.logger.info("Navigating to %s", url)
        self.page.goto(url, wait_until=wait_until, timeout=timeout)

    def wait_for_page_ready(
        self,
        timeout: int = DEFAULT_TIMEOUT_MS,
        state: Literal["domcontentloaded", "load", "networkidle"] = "load",
    ) -> None:
        self.page.wait_for_load_state(state, timeout=timeout)

    def pause(self, milliseconds: int) -> None:
        self.page.wait_for_timeout(milliseconds)

    def take_screenshot(self, name: str) -> str:
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        path = self.SCREENSHOTS_DIR / name
        self.page.screenshot(path=str(path), full_page=True)
        self.logger.info("Screenshot saved to %s", path)
        return str(path)

    def locator(self, selector: Selector) -> Locator:
        return self.page.locator(selector)

    def first_visible_locator(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
        warn_on_timeout: bool = True,
    ) -> Optional[Locator]:
        loc = self.locator(selector)
        try:
            loc.first.wait_for(state="visible", timeout=timeout)
            return loc.first
        except PlaywrightTimeoutError:
            if warn_on_timeout:
                self.logger.warning("Element was not visible before timeout: %s", selector)
            return None

    # Backward-compatible alias. New code should use first_visible_locator().
    def visible_locator(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
        warn_on_timeout: bool = True,
    ) -> Optional[Locator]:
        return self.first_visible_locator(
            selector,
            timeout=timeout,
            warn_on_timeout=warn_on_timeout,
        )

    def has_visible_element(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
        warn_on_timeout: bool = True,
    ) -> bool:
        return self.first_visible_locator(
            selector,
            timeout=timeout,
            warn_on_timeout=warn_on_timeout,
        ) is not None

    def click_element(self, selector: Selector, timeout: int = SHORT_TIMEOUT_MS) -> None:
        element = self.first_visible_locator(selector, timeout=timeout)
        if element is None:
            self.take_failure_screenshot("missing_click_target", selector)
            raise AssertionError(f"Cannot click invisible or missing element: {selector}")
        element.click()
        self.logger.info("Clicked element: %s", selector)

    def fill_input(self, selector: Selector, value: str, timeout: int = SHORT_TIMEOUT_MS) -> None:
        element = self.first_visible_locator(selector, timeout=timeout)
        if element is None:
            self.take_failure_screenshot("missing_input", selector)
            raise AssertionError(f"Cannot fill invisible or missing input: {selector}")
        element.fill(value)
        self.logger.info("Filled input: %s", selector)

    def click_first_available(
        self,
        selectors: list[Selector],
        timeout_per_selector: int = FALLBACK_SELECTOR_TIMEOUT_MS,
        timeout: Optional[int] = None,
    ) -> bool:
        if timeout is not None:
            timeout_per_selector = timeout

        for selector in selectors:
            element = self.first_visible_locator(
                selector,
                timeout=timeout_per_selector,
                warn_on_timeout=False,
            )
            if element is not None:
                element.click()
                self.logger.info("Clicked first available selector: %s", selector)
                return True
        self.logger.info("No fallback selectors were visible: %s", selectors)
        return False

    def dismiss_blocking_overlays(self, reason: str = "page action") -> bool:
        """
        Dismiss eBay lightboxes that can intercept pointer events.

        eBay sometimes shows an onboarding/info modal after product navigation. It is
        unrelated to the shopping flow, but Playwright correctly refuses to click
        controls behind it unless we close it first.
        """
        dismissed = False

        for overlay_selector in self.BLOCKING_OVERLAY_SELECTORS:
            overlay = self.locator(overlay_selector).first
            try:
                if overlay.count() == 0 or not overlay.is_visible(timeout=500):
                    continue
            except Exception:
                continue

            for dismiss_selector in self.OVERLAY_DISMISS_SELECTORS:
                dismiss_button = overlay.locator(dismiss_selector).first
                try:
                    if dismiss_button.count() > 0 and dismiss_button.is_visible(timeout=500):
                        dismiss_button.click(timeout=2000)
                        self.pause(500)
                        self.logger.info(
                            "Dismissed blocking overlay before %s using selector: %s",
                            reason,
                            dismiss_selector,
                        )
                        dismissed = True
                        break
                except Exception:
                    continue

            try:
                if overlay.is_visible(timeout=500):
                    self.page.keyboard.press("Escape")
                    self.pause(500)
                    dismissed = True
                    self.logger.info("Dismissed blocking overlay before %s using Escape.", reason)
            except Exception:
                pass

        return dismissed

    def take_failure_screenshot(self, prefix: str, selector: Selector) -> None:
        safe_selector = re.sub(r"[^A-Za-z0-9_.-]+", "_", selector).strip("_")[:80]
        screenshot_name = f"{prefix}_{safe_selector or 'selector'}.png"
        try:
            self.take_screenshot(screenshot_name)
        except Exception as exc:
            self.logger.warning("Could not capture failure screenshot: %s", exc)

    # Backward-compatible method used by existing page objects.
    def wait_for_element(self, selector: Selector, timeout: int = DEFAULT_TIMEOUT_MS) -> bool:
        return self.has_visible_element(selector, timeout=timeout)
