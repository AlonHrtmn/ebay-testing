from pathlib import Path

import pytest
from playwright.sync_api import Page

from pages.base_page import BasePage


def test_locator_visibility_and_actions(page: Page) -> None:
    page.set_content(
        '<input id="query"><button id="submit">Search</button>'
    )
    base_page = BasePage(page)

    assert base_page.has_visible_element("#query", timeout=100)
    assert not base_page.has_visible_element(
        "#missing",
        timeout=50,
        warn_on_timeout=False,
    )

    base_page.fill_input("#query", "shoes")
    base_page.click_element("#submit")

    assert page.locator("#query").input_value() == "shoes"


def test_first_visible_locator_uses_first_match(page: Page) -> None:
    page.set_content("<button>First</button><button>Second</button>")
    base_page = BasePage(page)

    element = base_page.first_visible_locator("button", timeout=100)

    assert element is not None
    assert element.inner_text() == "First"


def test_click_first_available_uses_first_visible_fallback(page: Page) -> None:
    page.set_content(
        '<button id="hidden" style="display:none">Hidden</button>'
        '<button id="visible">Visible</button>'
    )
    base_page = BasePage(page)

    assert base_page.click_first_available(
        ["#missing", "#hidden", "#visible"],
        timeout_per_selector=50,
    )


def test_take_screenshot_creates_requested_file(
    page: Page,
    tmp_path: Path,
) -> None:
    page.set_content("<h1>Screenshot test</h1>")
    base_page = BasePage(page)
    base_page.SCREENSHOTS_DIR = tmp_path

    screenshot = base_page.take_screenshot("base_page.png")

    assert Path(screenshot) == tmp_path / "base_page.png"
    assert Path(screenshot).is_file()


def test_failed_click_raises_clear_assertion(page: Page) -> None:
    base_page = BasePage(page)
    base_page.take_failure_screenshot = lambda *args: None

    with pytest.raises(AssertionError, match="Could not click element"):
        base_page.click_element("#missing", timeout=50)
