import re
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from playwright.sync_api import (
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from utils.logger import setup_logger


Selector = str


class BasePage:
    """Shared Playwright helpers for page objects."""

    DEFAULT_TIMEOUT_MS = 10_000
    SHORT_TIMEOUT_MS = 5_000
    NAVIGATION_TIMEOUT_MS = 30_000
    OPTIONAL_UI_TIMEOUT_MS = 750

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

    # Keep this list restricted to known nuisance overlays.
    BLOCKING_OVERLAY_SELECTORS = (
        "[data-testid='x-onboarding-modal'][aria-hidden='false']",
        ".x-onboarding-modal[aria-hidden='false']",
        ".lightbox-dialog[aria-modal='true']",
    )

    OVERLAY_DISMISS_SELECTORS = (
        "button[aria-label='Close']",
        "button[aria-label='Close dialog']",
        "button[aria-label='Close overlay']",
        "button[aria-label*='close' i]",
        "#lightbox-close",
        ".vi-overlay-close",
        "button:has-text('Got it')",
        "button:has-text('No thanks')",
        "button:has-text('Maybe later')",
        "button:has-text('Skip')",
    )

    def __init__(self, page: Page):
        self.page = page
        self.logger = setup_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(
        self,
        url: str,
        wait_until: Literal[
            "commit",
            "domcontentloaded",
            "load",
            "networkidle",
        ] = "domcontentloaded",
        timeout: int = NAVIGATION_TIMEOUT_MS,
    ) -> None:
        self.logger.info("Navigating to %s", url)

        self.page.goto(
            url,
            wait_until=wait_until,
            timeout=timeout,
        )

    def wait_for_page_ready(
        self,
        timeout: int = DEFAULT_TIMEOUT_MS,
        state: Literal[
            "domcontentloaded",
            "load",
            "networkidle",
        ] = "domcontentloaded",
    ) -> None:
        self.page.wait_for_load_state(
            state,
            timeout=timeout,
        )

    def pause(self, milliseconds: int) -> None:
        """Wait briefly for UI transitions that have no observable state."""
        self.page.wait_for_timeout(milliseconds)

    # ------------------------------------------------------------------
    # Locators
    # ------------------------------------------------------------------

    def locator(self, selector: Selector) -> Locator:
        return self.page.locator(selector)

    def wait_for_visible(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
    ) -> Locator:
        """
        Wait for a locator to become visible.

        Raises PlaywrightTimeoutError if the element does not appear.
        """

        element = self.locator(selector)

        element.wait_for(
            state="visible",
            timeout=timeout,
        )

        return element

    def first_visible_locator(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
        warn_on_timeout: bool = True,
    ) -> Optional[Locator]:
        """
        Returns the first visible matching locator.

        Use only when selecting the first matching element is intentional.
        """

        element = self.locator(selector).first

        try:
            element.wait_for(
                state="visible",
                timeout=timeout,
            )

            return element

        except PlaywrightTimeoutError:

            if warn_on_timeout:
                self.logger.warning(
                    "Element was not visible before timeout: %s",
                    selector,
                )

            return None

    def is_visible(
        self,
        selector: Selector,
        timeout: int = OPTIONAL_UI_TIMEOUT_MS,
    ) -> bool:
        """
        Quick visibility check for optional UI.
        """

        try:
            return self.locator(selector).first.is_visible(
                timeout=timeout
            )

        except PlaywrightTimeoutError:
            return False

    def has_visible_element(
        self,
        selector: Selector,
        timeout: int = DEFAULT_TIMEOUT_MS,
        warn_on_timeout: bool = True,
    ) -> bool:
        """Return whether at least one matching element becomes visible."""
        return self.first_visible_locator(
            selector,
            timeout=timeout,
            warn_on_timeout=warn_on_timeout,
        ) is not None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def click_element(
        self,
        selector: Selector,
        timeout: int = SHORT_TIMEOUT_MS,
    ) -> None:

        element = self.locator(selector)

        try:
            element.click(timeout=timeout)

        except PlaywrightTimeoutError:

            self.take_failure_screenshot(
                "click_failed",
                selector,
            )

            raise AssertionError(
                "Could not click element within "
                f"{timeout} ms: {selector}"
            )

        self.logger.info(
            "Clicked element: %s",
            selector,
        )

    def fill_input(
        self,
        selector: Selector,
        value: str,
        timeout: int = SHORT_TIMEOUT_MS,
    ) -> None:

        element = self.locator(selector)

        try:
            element.fill(
                value,
                timeout=timeout,
            )

        except PlaywrightTimeoutError:

            self.take_failure_screenshot(
                "fill_failed",
                selector,
            )

            raise AssertionError(
                "Could not fill input within "
                f"{timeout} ms: {selector}"
            )

        self.logger.info(
            "Filled input: %s",
            selector,
        )

    def click_first_available(
        self,
        selectors: list[Selector],
        timeout_per_selector: int = OPTIONAL_UI_TIMEOUT_MS,
    ) -> bool:
        """
        Click the first visible selector from a known set of valid UI variants.
        """

        for selector in selectors:

            element = self.first_visible_locator(
                selector,
                timeout=timeout_per_selector,
                warn_on_timeout=False,
            )

            if element is None:
                continue

            try:
                element.click(
                    timeout=self.SHORT_TIMEOUT_MS
                )

                self.logger.info(
                    "Clicked fallback selector: %s",
                    selector,
                )

                return True

            except PlaywrightTimeoutError:

                self.logger.debug(
                    "Selector became visible but "
                    "was not actionable: %s",
                    selector,
                )

        return False

    # ------------------------------------------------------------------
    # Overlay handling
    # ------------------------------------------------------------------

    def dismiss_blocking_overlays(
        self,
        reason: str = "page action",
    ) -> bool:

        dismissed_any = False

        for overlay_selector in self.BLOCKING_OVERLAY_SELECTORS:

            overlay = self.locator(
                overlay_selector
            ).first

            try:
                if not overlay.is_visible(
                    timeout=self.OPTIONAL_UI_TIMEOUT_MS
                ):
                    continue

            except PlaywrightTimeoutError:
                continue

            self.logger.info(
                "Blocking overlay detected before %s: %s",
                reason,
                overlay_selector,
            )

            dismissed = False

            for dismiss_selector in self.OVERLAY_DISMISS_SELECTORS:

                dismiss_button = overlay.locator(
                    dismiss_selector
                ).first

                try:
                    if not dismiss_button.is_visible(
                        timeout=self.OPTIONAL_UI_TIMEOUT_MS
                    ):
                        continue

                    dismiss_button.click(
                        timeout=self.SHORT_TIMEOUT_MS
                    )

                    overlay.wait_for(
                        state="hidden",
                        timeout=self.SHORT_TIMEOUT_MS,
                    )

                    self.logger.info(
                        "Dismissed overlay before %s "
                        "using selector: %s",
                        reason,
                        dismiss_selector,
                    )

                    dismissed = True
                    dismissed_any = True
                    break

                except PlaywrightTimeoutError:
                    continue

                except PlaywrightError as exc:

                    self.logger.debug(
                        "Overlay dismissal attempt failed "
                        "for selector %s: %s",
                        dismiss_selector,
                        exc,
                    )

            if not dismissed:

                self.logger.warning(
                    "Known blocking overlay could not "
                    "be dismissed before %s: %s",
                    reason,
                    overlay_selector,
                )

        return dismissed_any

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def take_screenshot(
        self,
        name: str,
    ) -> str:

        self.SCREENSHOTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = self.SCREENSHOTS_DIR / name

        self.page.screenshot(
            path=str(path),
            full_page=True,
        )

        self.logger.info(
            "Screenshot saved to %s",
            path,
        )

        return str(path)

    def take_failure_screenshot(
        self,
        prefix: str,
        detail: str = "",
    ) -> Optional[str]:

        safe_detail = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            detail,
        ).strip("_")[:80]

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        filename = (
            f"{prefix}_"
            f"{safe_detail or 'failure'}_"
            f"{timestamp}.png"
        )

        try:
            return self.take_screenshot(filename)

        except PlaywrightError as exc:

            self.logger.warning(
                "Could not capture failure screenshot: %s",
                exc,
            )

            return None
