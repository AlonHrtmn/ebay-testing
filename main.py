import os
import json
from playwright.sync_api import sync_playwright
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage

def load_config():
    """Reads parameters from config/test_data.json"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "test_data.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

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

def addItemsToCart(page, urls: list, max_price: float = None, desired_count: int = None) -> int:
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

# --- Standalone Script Execution ---

def main():
    print("Loading test configuration...")
    config = load_config()
    query = config.get("search_query", "shoes")
    max_price = config.get("max_price", 220.0)
    limit = config.get("item_limit", 5)
    username = config.get("username", "")
    password = config.get("password", "")
    
    print(f"Starting eBay automation flow for '{query}' under budget {max_price}...")
    
    with sync_playwright() as p:
        # We launch the browser in HEADED mode to watch it run live
        print("Launching browser in headed mode...")
        browser = p.chromium.launch(
            headless=False, 
            slow_mo=500,  # Pause for 500ms between actions for viewing
            args=["--start-maximized"],
        )
        
        # Apply anti-bot configurations
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
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
            print("\n--- Step 1: Executing login (Identification) ---")
            login(page, username, password)
            
            if os.getenv("EBAY_CLEAR_CART_BEFORE_RUN") == "1":
                print("\n--- Clearing shopping cart before adding new items ---")
                clear_cart(page)
            
            # Step 2: Search
            print("\n--- Step 2: Executing searchItemsByNameUnderPrice ---")
            urls = searchItemsByNameUnderPrice(page, query, max_price, limit)

            if not urls:
                print("No items matched the search criteria. Exiting.")
                browser.close()
                return
            
            print(f"Collected {len(urls)} matching item URLs.")            
            
                
            # Step 3: Add to Cart
            print("\n--- Step 3: Executing addItemsToCart ---")
            items_added = addItemsToCart(page, urls, max_price, desired_count=limit)
            print(f"Successfully added {items_added} items to the cart.")
            
            # Step 4: Verify Cart Subtotal
            print("\n--- Step 4: Executing assertCartTotalNotExceeds ---")
            assertCartTotalNotExceeds(page, max_price, items_added)
            
            print("\nFlow completed successfully! Keeping browser open for 3 seconds...")
            page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"\nExecution encountered an error: {e}")
            page.wait_for_timeout(5000) # Give you time to look at the screen on error
            
        finally:
            print("Closing browser context...")
            browser.close()

if __name__ == "__main__":
    main()
