from pages.base_page import BasePage


class LoginPage(BasePage):
    EBAY_HOME_URL = "https://www.ebay.com"
    LOGIN_URL = "https://signin.ebay.com"

    LOGIN_IDENTIFIER_SELECTORS = (
        "#userid",
        "input[type='email']",
        "input[name='userid']",
        "input[name='username']",
    )

    HOME_SEARCH_SELECTORS = (
        "input#gh-ac",
        "input[aria-label*='Search' i]",
        "input[type='search']",
        "input[type='text']",
    )

    def open_login_page(self) -> None:
        """
        Open the eBay sign-in page and verify that the
        expected sign-in UI is available.
        """
        self.logger.info("Opening eBay sign-in page.")

        self.navigate(self.LOGIN_URL)
        self.assert_login_page_ready()

        self.logger.info("eBay sign-in page is ready.")

    def assert_login_page_ready(self) -> None:
        """
        Verify that the eBay sign-in page contains a known
        login identifier field.
        """
        self.wait_for_visible(
            ",".join(self.LOGIN_IDENTIFIER_SELECTORS),
            timeout=self.DEFAULT_TIMEOUT_MS,
        )

    def start_guest_session(self) -> bool:
        """
        Open the eBay home page and verify that the
        browsing session is usable.
        """
        self.logger.info(
            "Starting eBay guest session."
        )

        self.navigate(self.EBAY_HOME_URL)

        self.wait_for_visible(
            ",".join(self.HOME_SEARCH_SELECTORS),
            timeout=self.DEFAULT_TIMEOUT_MS,
        )

        self.logger.info(
            "Guest session established."
        )

        return True

    def login_stub(
        self,
        username: str = "",
        password: str = "",
    ) -> bool:
        """
        Assignment-safe identification/session step.

        Real credential submission is intentionally skipped
        because eBay sign-in may trigger CAPTCHA or MFA flows,
        which make public-site automation non-deterministic.
        """

        if username and password:
            self.logger.info(
                "Credentials were supplied; "
                "verifying that the sign-in page is reachable."
            )

            self.open_login_page()

        return self.start_guest_session()