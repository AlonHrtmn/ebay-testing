import pytest
import os

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Overrides default browser context arguments in pytest-playwright.
    Configures a realistic User-Agent, language locale, and window size 
    to bypass anti-bot detection systems.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "locale": "en-US",
        "timezone_id": "America/New_York"
    }

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture screenshots on test failure.
    If a test fails, it captures the current state of the page and 
    saves it to the screenshots directory.
    """
    outcome = yield
    rep = outcome.get_result()
    
    # We only capture screenshots when the test step fails
    if rep.when == "call" and rep.failed:
        page = item.funcargs.get("page")
        if page:
            try:
                screenshots_dir = os.path.join(os.path.dirname(item.fspath), "..", "screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshots_dir, f"failure_{item.name}.png")
                page.screenshot(path=screenshot_path)
                print(f"\n[Test Failure] Screenshot saved to: {screenshot_path}")
            except Exception as e:
                print(f"\n[Test Failure] Could not capture screenshot: {e}")
