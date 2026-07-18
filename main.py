import os
import time
from typing import Optional

from playwright.sync_api import sync_playwright
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage
from utils.config import load_config, positive_float, positive_int


# --- Top-Level Function Signatures Required by Assignment ---

def login(page, username: str = "", password: str = "") -> bool:
    """
    Executes the identification / session establishment step (הזדהות).
    """
    login_page = LoginPage(page)
    return login_page.login_stub(username, password)

def searchItemsByNameUnderPrice(page, query: str, max_price: float, limit: int = 5) -> list:
    """
    Searches for items matching query and filters links that cost <= max_price.
    Navigates pages if necessary.
    """
    search_page = SearchPage(page)
    return search_page.searchItemsByNameUnderPrice(query, max_price, limit)

def addItemsToCart(
    page,
    urls: list,
    max_price: Optional[float] = None,
    desired_count: Optional[int] = None,
) -> int:
    """
    Navigates to each item URL, handles option selects, and clicks Add to Cart.
    Saves screenshot of each.
    """
    product_page = ProductPage(page)
    return product_page.addItemsToCart(urls, max_price=max_price, desired_count=desired_count)

def assertCartTotalNotExceeds(page, budget_per_item: float, items_count: int):
    """
    Opens the cart page, parses the subtotal, and asserts that it is within budget.
    """
    cart_page = CartPage(page)
    cart_page.assertCartTotalNotExceeds(budget_per_item, items_count)

def clear_cart(page):
    """
    Clears the shopping cart to avoid stale cart state.
    """
    cart_page = CartPage(page)
    cart_page.clear_cart()

def page_is_open(page) -> bool:
    return page is not None and not page.is_closed()

def format_elapsed(seconds: float) -> str:
    """Formats elapsed seconds as HH:MM:SS."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

# --- Standalone Script Execution ---

def main():
    start_time = time.perf_counter()

    def log(message: str = "") -> None:
        elapsed = format_elapsed(time.perf_counter() - start_time)
        print(f"[elapsed {elapsed}] {message}" if message else "")

    log("Loading test configuration...")
    config = load_config()
    query = str(config.get("search_query", "shoes")).strip() or "shoes"
    max_price = positive_float(config, "max_price", 220.0)
    limit = positive_int(config, "item_limit", 5)
    username = str(config.get("username", ""))
    password = str(config.get("password", ""))
    headless = env_flag("EBAY_HEADLESS", env_flag("PLAYWRIGHT_HEADLESS", False))
    
    log(
        "Starting eBay automation flow: "
        f"search='{query}', max item price={max_price}, target items={limit}."
    )
    if headless:
        log("Headless browser mode is ON; progress will be reported in this terminal.")
    else:
        log("Headed browser mode is ON; you can watch the browser while terminal timing continues.")
    
    browser = None
    page = None

    with sync_playwright() as p:
        mode_name = "headless" if headless else "headed"
        log(f"Launching Chromium in {mode_name} mode...")
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=0 if headless else 500,  # Slow only when the browser is visible.
            args=["--start-maximized"],
        )
        
        # Create a realistic browser context.
        log("Creating browser context with eBay-friendly locale, timezone, and viewport settings...")
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            # record_video_dir="videos/",
            device_scale_factor=1,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)
        
        try:
            # Step 1: Identification (הזדהות)
            log("\n--- Step 1: Starting guest/login session setup ---")
            step_start = time.perf_counter()
            login(page, username, password)
            log(f"Step 1 complete: browser session is ready in {format_elapsed(time.perf_counter() - step_start)}.")
            
            if os.getenv("EBAY_CLEAR_CART_BEFORE_RUN") == "1":
                log("\n--- Clearing shopping cart before adding new items ---")
                step_start = time.perf_counter()
                clear_cart(page)
                log(f"Cart cleanup complete in {format_elapsed(time.perf_counter() - step_start)}.")
            
            # Step 2: Search
            log(
                "\n--- Step 2: Searching eBay "
                f"for '{query}' under {max_price}, collecting backup samples "
                f"for {limit} target item(s) ---"
            )
            step_start = time.perf_counter()
            urls = searchItemsByNameUnderPrice(page, query, max_price, limit)

            if not urls:
                log("No items matched the search criteria. Exiting.")
                return
            
            log(
                f"Step 2 complete: collected {len(urls)} matching item URL(s) "
                f"in {format_elapsed(time.perf_counter() - step_start)}; "
                f"will add the first {limit} that work."
            )
            
                
            # Step 3: Add to Cart
            log(
                "\n--- Step 3: Opening each selected item, choosing valid options, "
                "and adding to cart ---"
            )
            step_start = time.perf_counter()
            items_added = addItemsToCart(page, urls, max_price, desired_count=limit)
            log(
                f"Step 3 complete: successfully added {items_added} item(s) "
                f"in {format_elapsed(time.perf_counter() - step_start)}."
            )
            
            # Step 4: Verify Cart Subtotal
            log(
                "\n--- Step 4: Opening cart and checking subtotal against "
                f"overall budget {max_price * items_added} ---"
            )
            step_start = time.perf_counter()
            assertCartTotalNotExceeds(page, max_price, items_added)
            log(f"Step 4 complete: cart subtotal verified in {format_elapsed(time.perf_counter() - step_start)}.")
            
            log("\nFlow completed successfully! Keeping browser open for 3 seconds...")
            page.wait_for_timeout(3000)
            
        except Exception as e:
            log(f"\nExecution encountered an error: {e}")
            if page_is_open(page):
                try:
                    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
                    os.makedirs(screenshots_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshots_dir, "main_error.png")
                    page.screenshot(path=screenshot_path, full_page=True)
                    log(f"Error screenshot saved to: {screenshot_path}")
                except Exception as screenshot_error:
                    log(f"Could not capture error screenshot: {screenshot_error}")
                page.wait_for_timeout(5000) # Give you time to look at the screen on error
            else:
                log("Browser page is already closed; skipping error pause.")
            raise
            
        finally:
            log("Closing browser context...")
            if browser is not None and browser.is_connected():
                browser.close()
            log(f"Total elapsed time: {format_elapsed(time.perf_counter() - start_time)}.")

if __name__ == "__main__":
    main()
