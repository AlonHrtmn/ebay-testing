from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from utils.logger import setup_logger


class BasePage:
    """Shared Playwright helpers for all page objects."""

    DEFAULT_TIMEOUT_MS = 10_000
    SHORT_TIMEOUT_MS = 5_000
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

    def __init__(self, page: Page):
        self.page = page
        self.logger = setup_logger(self.__class__.__name__)

    def navigate(self, url: str, wait_until: str = "load") -> None:
        self.logger.info("Navigating to %s", url)
        self.page.goto(url, wait_until=wait_until)

    def wait_for_page_ready(self, timeout: int = DEFAULT_TIMEOUT_MS) -> None:
        self.page.wait_for_load_state("load", timeout=timeout)

    def pause(self, milliseconds: int) -> None:
        self.page.wait_for_timeout(milliseconds)

    def take_screenshot(self, name: str) -> str:
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        path = self.SCREENSHOTS_DIR / name
        self.page.screenshot(path=str(path), full_page=True)
        self.logger.info("Screenshot saved to %s", path)
        return str(path)

    def locator(self, selector: str) -> Locator:
        return self.page.locator(selector)

    def visible_locator(
        self,
        selector: str,
        timeout: int = DEFAULT_TIMEOUT_MS,
    ) -> Optional[Locator]:
        loc = self.locator(selector)
        try:
            loc.first.wait_for(state="visible", timeout=timeout)
            return loc.first
        except PlaywrightTimeoutError:
            self.logger.warning("Element was not visible before timeout: %s", selector)
            return None

    def has_visible_element(self, selector: str, timeout: int = DEFAULT_TIMEOUT_MS) -> bool:
        return self.visible_locator(selector, timeout=timeout) is not None

    def click_element(self, selector: str, timeout: int = SHORT_TIMEOUT_MS) -> None:
        element = self.visible_locator(selector, timeout=timeout)
        if element is None:
            raise AssertionError(f"Cannot click invisible or missing element: {selector}")
        element.click()
        self.logger.info("Clicked element: %s", selector)

    def fill_input(self, selector: str, value: str, timeout: int = SHORT_TIMEOUT_MS) -> None:
        element = self.visible_locator(selector, timeout=timeout)
        if element is None:
            raise AssertionError(f"Cannot fill invisible or missing input: {selector}")
        element.fill(value)
        self.logger.info("Filled input: %s", selector)

    def click_first_available(
        self,
        selectors: list[str],
        timeout: int = SHORT_TIMEOUT_MS,
    ) -> bool:
        for selector in selectors:
            element = self.visible_locator(selector, timeout=timeout)
            if element is not None:
                element.click()
                self.logger.info("Clicked first available selector: %s", selector)
                return True
        return False

    # Backward-compatible method used by existing page objects.
    def wait_for_element(self, selector: str, timeout: int = DEFAULT_TIMEOUT_MS) -> bool:
        return self.has_visible_element(selector, timeout=timeout)
