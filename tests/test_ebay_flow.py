import os
import json
from playwright.sync_api import Page
from pages.login_page import LoginPage
from pages.search_page import SearchPage
from pages.product_page import ProductPage
from pages.cart_page import CartPage

def load_test_data():
    """Reads input configurations from config/test_data.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "test_data.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_ebay_shopping_flow(page: Page):
    # Load parameters
    data = load_test_data()
    search_query = data.get("search_query", "shoes")
    max_price = data.get("max_price", 220.0)
    item_limit = data.get("item_limit", 5)
    username = data.get("username", "")
    password = data.get("password", "")
    
    # Instantiate POM components
    login_page = LoginPage(page)
    search_page = SearchPage(page)
    product_page = ProductPage(page)
    cart_page = CartPage(page)
    
    # Step 1: Identification (הזדהות)
    login_page.login_stub(username, password)
    
    # Step 2: Search and gather matching URLs (with price constraint and pagination)
    urls = search_page.assertSearchItemsFound(search_query, max_price, item_limit)
    
    # Step 3: Add all retrieved items to the cart (handling variants randomly if present)
    items_added = product_page.assertItemsAddedToCart(urls)
    
    # Step 4: Open cart page, retrieve subtotal, and verify budget limit
    cart_page.assertCartTotalNotExceeds(max_price, items_added)
