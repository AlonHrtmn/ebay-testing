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
