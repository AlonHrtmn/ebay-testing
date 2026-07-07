from playwright.sync_api import Page

from pages.base_page import BasePage


class LoginPage(BasePage):
    EBAY_HOME_URL = "https://www.ebay.com"
    LOGIN_URL = "https://signin.ebay.com"

    def __init__(self, page: Page):
        super().__init__(page)

    def open_login_page(self) -> None:
        self.navigate(self.LOGIN_URL)
        self.wait_for_page_ready()

    def start_guest_session(self) -> bool:
        self.logger.info("Starting eBay guest session.")
        self.navigate(self.EBAY_HOME_URL, wait_until="domcontentloaded")
        self.wait_for_page_ready(state="domcontentloaded")
        self.take_screenshot("session_initialization.png")
        self.logger.info("Guest session established.")
        return True

    def login_stub(self, username: str = "", password: str = "") -> bool:
        """
        Assignment-safe identification step.

        Real credential submission is intentionally skipped because eBay sign-in
        can trigger CAPTCHA / MFA flows that make the automation non-deterministic.
        """
        if username and password:
            self.logger.info("Credentials supplied for %s; opening sign-in page only.", username)
            self.open_login_page()
            self.pause(1500)

        return self.start_guest_session()
