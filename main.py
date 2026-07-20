import os
import time
import traceback
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage
from utils.config import load_config


# ---------------------------------------------------------------------------
# Assignment-required top-level functions
# ---------------------------------------------------------------------------

def login(page: Page, username: str = "", password: str = "") -> bool:
    """
    Executes the identification / session establishment step (הזדהות).
    """
    return LoginPage(page).login_stub(username, password)


def searchItemsByNameUnderPrice(
    page: Page,
    query: str,
    max_price: float,
    limit: int = 5,
) -> list:
    """
    Searches for items matching query and filters item URLs whose price
    is <= max_price.
    """
    return SearchPage(page).searchItemsByNameUnderPrice(
        query,
        max_price,
        limit,
    )


def addItemsToCart(
    page: Page,
    urls: list,
    max_price: Optional[float] = None,
    desired_count: Optional[int] = None,
) -> int:
    """
    Navigates to each item URL, handles required options,
    and adds valid items to the cart.
    """
    return ProductPage(page).addItemsToCart(
        urls,
        max_price=max_price,
        desired_count=desired_count,
    )


def assertCartTotalNotExceeds(
    page: Page,
    budget_per_item: float,
    items_count: int,
) -> None:
    """
    Opens the cart and verifies that its subtotal does not exceed
    budget_per_item * items_count.
    """
    CartPage(page).assertCartTotalNotExceeds(
        budget_per_item,
        items_count,
    )


def clear_cart(page: Page) -> None:
    """
    Clears the shopping cart to avoid stale state between runs.
    """
    CartPage(page).clear_cart()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def page_is_open(page: Optional[Page]) -> bool:
    return page is not None and not page.is_closed()


def format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def create_artifact_directories() -> tuple[Path, Path]:
    base_dir = Path(__file__).resolve().parent

    screenshots_dir = base_dir / "screenshots"
    traces_dir = base_dir / "traces"

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    return screenshots_dir, traces_dir


def capture_failure_screenshot(
    page: Optional[Page],
    screenshots_dir: Path,
    log,
) -> None:
    if page is None:
        log("Browser page was not created; skipping screenshot.")
        return

    if page.is_closed():
        log("Browser page is closed; skipping screenshot.")
        return

    screenshot_path = screenshots_dir / "main_error.png"

    try:
        page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

        log(f"Error screenshot saved to: {screenshot_path}")

    except Exception as screenshot_error:
        log(
            "Could not capture error screenshot: "
            f"{screenshot_error}"
        )


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> None:
    start_time = time.perf_counter()

    def log(message: str = "") -> None:
        if not message:
            print()
            return

        elapsed = format_elapsed(
            time.perf_counter() - start_time
        )

        print(
            f"[elapsed {elapsed}] {message}",
            flush=True,
        )

    screenshots_dir, traces_dir = create_artifact_directories()

    log("Loading test configuration...")

    config = load_config()

    query = config.search_query
    max_price = config.max_price
    limit = config.item_limit
    username = config.username
    password = config.password

    is_ci = env_flag("CI", False)

    # CI should normally be headless.
    headless = env_flag(
        "EBAY_HEADLESS",
        env_flag(
            "PLAYWRIGHT_HEADLESS",
            is_ci,
        ),
    )

    clear_cart_before_run = env_flag(
        "EBAY_CLEAR_CART_BEFORE_RUN",
        False,
    )

    log(
        "Starting eBay automation flow: "
        f"search='{query}', "
        f"max item price={max_price}, "
        f"target items={limit}."
    )

    log(
        "Browser mode: "
        f"{'headless' if headless else 'headed'}."
    )

    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None

    trace_started = False
    flow_succeeded = False

    with sync_playwright() as playwright:

        try:
            # ---------------------------------------------------------------
            # Browser setup
            # ---------------------------------------------------------------

            log("Launching Chromium...")

            browser = playwright.chromium.launch(
                headless=headless,
                timeout=60_000,
                args=["--disable-gpu"],

                # slow_mo is useful only for visually debugging locally.
                slow_mo=0 if headless else 250,
            )

            log("Creating browser context...")

            context = browser.new_context(
                viewport={
                    "width": 1920,
                    "height": 1080,
                },
                locale="en-US",
            )

            # Capture a Playwright trace for debugging.
            context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
            )

            trace_started = True

            page = context.new_page()

            page.set_default_timeout(30_000)
            page.set_default_navigation_timeout(60_000)

            # ---------------------------------------------------------------
            # Step 1 - Login/session
            # ---------------------------------------------------------------

            log("--- Step 1: Starting guest/login session setup ---")

            step_start = time.perf_counter()

            login_success = login(
                page,
                username,
                password,
            )

            if not login_success:
                raise RuntimeError(
                    "Login/session setup did not complete successfully."
                )

            log(
                "Step 1 complete in "
                f"{format_elapsed(time.perf_counter() - step_start)}."
            )

            # ---------------------------------------------------------------
            # Optional cart cleanup
            # ---------------------------------------------------------------

            if clear_cart_before_run:
                log("--- Clearing shopping cart before run ---")

                step_start = time.perf_counter()

                clear_cart(page)

                log(
                    "Cart cleanup complete in "
                    f"{format_elapsed(time.perf_counter() - step_start)}."
                )

            # ---------------------------------------------------------------
            # Step 2 - Search
            # ---------------------------------------------------------------

            log(
                "--- Step 2: Searching eBay "
                f"for '{query}' under {max_price} ---"
            )

            step_start = time.perf_counter()

            urls = searchItemsByNameUnderPrice(
                page,
                query,
                max_price,
                limit,
            )

            if not urls:
                raise RuntimeError(
                    "No items matched the configured search criteria."
                )

            log(
                f"Step 2 complete: collected {len(urls)} "
                "candidate item URL(s) in "
                f"{format_elapsed(time.perf_counter() - step_start)}."
            )

            # ---------------------------------------------------------------
            # Step 3 - Add items
            # ---------------------------------------------------------------

            log("--- Step 3: Adding valid items to cart ---")

            step_start = time.perf_counter()

            items_added = addItemsToCart(
                page,
                urls,
                max_price=max_price,
                desired_count=limit,
            )

            if items_added <= 0:
                raise AssertionError(
                    "No items were successfully added to the cart."
                )

            if items_added < limit:
                log(
                    "Warning: requested "
                    f"{limit} item(s), but only "
                    f"{items_added} were successfully added."
                )

            log(
                f"Step 3 complete: added {items_added} item(s) in "
                f"{format_elapsed(time.perf_counter() - step_start)}."
            )

            # ---------------------------------------------------------------
            # Step 4 - Validate subtotal
            # ---------------------------------------------------------------

            expected_max_total = max_price * items_added

            log(
                "--- Step 4: Verifying cart subtotal "
                f"does not exceed {expected_max_total:.2f} ---"
            )

            step_start = time.perf_counter()

            assertCartTotalNotExceeds(
                page,
                max_price,
                items_added,
            )

            log(
                "Step 4 complete in "
                f"{format_elapsed(time.perf_counter() - step_start)}."
            )

            flow_succeeded = True

            log("Flow completed successfully.")

            # Optional pause only for manual local observation.
            if (
                not headless
                and not is_ci
                and env_flag("EBAY_PAUSE_AFTER_SUCCESS", False)
            ):
                log("Pausing briefly for local inspection...")
                page.wait_for_timeout(3000)

        except Exception as error:

            log(
                "Execution failed: "
                f"{type(error).__name__}: {error}"
            )

            # Useful in CI logs.
            traceback.print_exc()

            capture_failure_screenshot(
                page,
                screenshots_dir,
                log,
            )

            raise

        finally:

            # ---------------------------------------------------------------
            # Save trace
            # ---------------------------------------------------------------

            if context is not None and trace_started:

                trace_filename = (
                    "success_trace.zip"
                    if flow_succeeded
                    else "failure_trace.zip"
                )

                trace_path = traces_dir / trace_filename

                try:
                    context.tracing.stop(
                        path=str(trace_path)
                    )

                    log(
                        f"Playwright trace saved to: {trace_path}"
                    )

                except Exception as trace_error:
                    log(
                        "Could not save Playwright trace: "
                        f"{trace_error}"
                    )

            # ---------------------------------------------------------------
            # Cleanup
            # ---------------------------------------------------------------

            if context is not None:
                try:
                    context.close()
                except Exception as context_error:
                    log(
                        "Error while closing browser context: "
                        f"{context_error}"
                    )

            if (
                browser is not None
                and browser.is_connected()
            ):
                try:
                    browser.close()
                except Exception as browser_error:
                    log(
                        "Error while closing browser: "
                        f"{browser_error}"
                    )

            log(
                "Total elapsed time: "
                f"{format_elapsed(time.perf_counter() - start_time)}."
            )


if __name__ == "__main__":
    main()
