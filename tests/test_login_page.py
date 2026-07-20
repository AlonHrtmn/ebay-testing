import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.login_page import LoginPage


def test_assert_login_page_ready_finds_login_identifier(page: Page) -> None:
    page.set_content(
        '<input id="userid" type="text" aria-label="Email or username">'
    )
    login_page = LoginPage(page)

    login_page.assert_login_page_ready()


def test_assert_login_page_ready_raises_when_missing(page: Page) -> None:
    page.set_content('<div>No login fields are present</div>')
    login_page = LoginPage(page)

    with pytest.raises(PlaywrightTimeoutError):
        login_page.assert_login_page_ready()


def test_login_stub_calls_open_login_page_with_credentials(page: Page, monkeypatch) -> None:
    login_page = LoginPage(page)
    called = {
        "open_login_page": False,
        "start_guest_session": False,
    }

    def fake_open_login_page() -> None:
        called["open_login_page"] = True

    def fake_start_guest_session() -> bool:
        called["start_guest_session"] = True
        return True

    monkeypatch.setattr(login_page, "open_login_page", fake_open_login_page)
    monkeypatch.setattr(login_page, "start_guest_session", fake_start_guest_session)

    assert login_page.login_stub("user@example.com", "password") is True
    assert called["open_login_page"] is True
    assert called["start_guest_session"] is True
