from playwright.sync_api import Page
from utils.logger import setup_logger

class BasePage:
    def __init__(self, page: Page):
        self.page = page
        self.logger = setup_logger(self.__class__.__name__)

    def navigate(self, url: str):
        self.logger.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="load")

    def take_screenshot(self, name: str):
        import os
        screenshots_dir = os.path.join(os.path.dirname(__file__), "..", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        path = os.path.join(screenshots_dir, name)
        self.page.screenshot(path=path)
        self.logger.info(f"Screenshot saved to {path}")
        return path

    def wait_for_element(self, selector: str, timeout: float = 10000):
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except Exception as e:
            self.logger.warning(f"Timeout waiting for element: {selector}")
            return False
            
    def click_element(self, selector: str, timeout: float = 5000):
        self.wait_for_element(selector, timeout)
        self.page.click(selector)
        self.logger.info(f"Clicked element: {selector}")

    def fill_input(self, selector: str, value: str, timeout: float = 5000):
        self.wait_for_element(selector, timeout)
        self.page.fill(selector, value)
        self.logger.info(f"Filled element {selector} with value")
