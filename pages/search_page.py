import re
from playwright.sync_api import Page
from pages.base_page import BasePage
from utils.helpers import parse_price

class SearchPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.search_input = "#gh-ac"
        self.price_max_input_name = "_udhi"
        # Support various next-page selectors dynamically
        self.next_page_btn = "a.pagination__next, a[aria-label='Go to next search page'], a[aria-label='Next page'], a.pagination__next-icon"

    def execute_search(self, query: str):
        self.logger.info(f"Searching for: {query}")
        self.fill_input(self.search_input, query)
        # Playwright way: locate the button by its role and accessible name
        search_btn = self.page.get_by_role("button", name="Search", exact=True)
        search_btn.wait_for(state="visible", timeout=5000)
        search_btn.click()
        self.page.wait_for_load_state("load")
        
        # Apply the "Buy It Now" filter to avoid auction items that cannot be added to the cart
        try:
            buy_it_now_btn = self.page.locator("a:has-text('Buy It Now'), a[aria-label='Buy It Now']")
            if buy_it_now_btn.count() > 0:
                self.logger.info("Clicking 'Buy It Now' filter to exclude auctions...")
                buy_it_now_btn.first.click()
                self.page.wait_for_load_state("load")
                self.page.wait_for_timeout(2000)
        except Exception as e:
            self.logger.warning(f"Could not apply 'Buy It Now' filter: {e}")

    def apply_max_price_filter(self, max_price: float):
        self.logger.info(f"Applying max price filter: {max_price}")
        max_price_selector = f"input[name='{self.price_max_input_name}']"
        
        if self.wait_for_element(max_price_selector, timeout=3000):
            try:
                self.fill_input(max_price_selector, str(int(max_price)))
                self.page.press(max_price_selector, "Enter")
                self.page.wait_for_load_state("load")
                self.logger.info("Successfully applied price filter via input submit")
                return True
            except Exception as e:
                self.logger.warning(f"Failed to apply price filter via input: {e}")
        
        self.logger.info("Proceeding with search results (clean prices will filter by max_price client-side)")
        return False

    def searchItemsByNameUnderPrice(self, query: str, max_price: float, limit: int = 5) -> list:
        self.logger.info(f"Executing searchItemsByNameUnderPrice: query={query}, max_price={max_price}, limit={limit}")
        
        # Check if the query is shoe-related
        shoe_keywords_query = ['shoe', 'sneaker', 'boot', 'sandal', 'slipper', 'clog', 'footwear', 'loafer', 'flat', 'oxford', 'mule', 'slide']
        is_shoe_query = any(kw in query.lower() for kw in shoe_keywords_query)
        
        SHOE_KEYWORDS = [
            'shoe', 'shoes', 'sneaker', 'sneakers', 'boot', 'boots', 'sandal', 'sandals', 
            'slipper', 'slippers', 'clog', 'clogs', 'footwear', 'loafer', 'loafers', 
            'flats', 'flat', 'oxford', 'oxfords', 'mule', 'mules', 'slides', 'runner', 
            'runners', 'trainer', 'trainers', 'slip-on', 'slip-ons', 'bootie', 'booties',
            'cleats', 'brogue', 'brogues', 'pump', 'pumps', 'heels'
        ]
        
        ACCESSORY_KEYWORDS = [
            'sock', 'socks', 'laces', 'horn', 'horns', 'polish', 'cleaner', 
            'cleaners', 'brush', 'brushes', 'spray', 'shield', 'shields', 'protector', 
            'tree', 'trees', 'rack', 'racks', 'organizer', 'organizers', 'box', 'boxes', 
            'bag', 'bags', 'insole', 'insoles', 'insert', 'inserts', 'cushion', 'cushions', 
            'keychain', 'keyring', 'charm', 'charms', 'sticker', 'stickers', 'display', 
            'hanger', 'deodorizer', 'remover', 'storage', 'stand', 'cabinet',
            'shirt', 'shirts', 't-shirt', 't-shirts', 'tshirt', 'tshirts', 'tee', 'tees', 
            'hoodie', 'hoodies', 'sweatshirt', 'sweatshirts', 'jacket', 'jackets', 'pants', 
            'shorts', 'cap', 'caps', 'hat', 'hats', 'beanie', 'beanies', 'clothing', 'apparel', 
            'costume', 'costumes', 'dress', 'dresses', 'skirt', 'skirts', 'jeans', 'towel', 'towels'
        ]
        
        # Avoid redundant home page navigation if we are already there
        if "ebay.com" not in self.page.url:
            self.navigate("https://www.ebay.com")
        self.execute_search(query)
        self.apply_max_price_filter(max_price)
        
        all_candidate_urls = []
        page_num = 1
        
        while len(all_candidate_urls) < limit or (page_num < 3 and len(all_candidate_urls) < 15):
            self.logger.info(f"Scanning search result page {page_num}...")
            
            # Wait for search results to load using XPath (class-independent)
            try:
                self.page.wait_for_selector("xpath=//a[contains(@href, '/itm/')]", state="attached", timeout=10000)
            except Exception as e:
                self.logger.warning(f"Timeout waiting for item elements on page {page_num}: {e}")
                self.take_screenshot(f"search_timeout_page_{page_num}.png")
                break
                
            # Locate all /itm/ links on the page using XPath
            links = self.page.locator("xpath=//a[contains(@href, '/itm/')]").all()
            self.logger.info(f"Found {len(links)} item links using XPath on page {page_num}")
            
            page_added = 0
            for link_loc in links:
                url = link_loc.get_attribute("href") or ""
                if not url:
                    continue
                    
                # Match only valid product page URLs containing a numeric item ID
                match = re.search(r'/itm/(\d+)', url)
                if not match:
                    continue
                item_id = match.group(1)
                if item_id == "123456":
                    continue
                    
                clean_url = f"https://www.ebay.com/itm/{item_id}"
                
                if clean_url in all_candidate_urls:
                    continue
                    
                # Extract price relative to the link using XPath ancestor traversal
                price_val = 0.0
                price_text = ""
                for depth in range(1, 9):
                    ancestor_loc = link_loc.locator(f"xpath=./ancestor::*[{depth}]")
                    if ancestor_loc.count() > 0:
                        text = ancestor_loc.first.inner_text() or ""
                        # Find all prices (e.g. $220.00, ILS 220, etc.)
                        matches = re.findall(r'(?:ILS|\$|₪|£)\s*\d+(?:[.,]\d+)?', text, re.IGNORECASE)
                        if matches:
                            price_text = matches[0]
                            price_val = parse_price(price_text)
                            break
                            
                # Extract title and verify image/picture presence
                title = link_loc.inner_text() or ""
                img_loc = link_loc.locator("xpath=.//img")
                
                if img_loc.count() > 0:
                    img_src = img_loc.first.get_attribute("src") or ""
                    # Skip if the image source is missing or is a transparent/placeholder 1x1 gif
                    if not img_src or "s.gif" in img_src:
                        continue
                else:
                    continue
                    
                if not title:
                    title = img_loc.first.get_attribute("alt") or img_loc.first.get_attribute("title") or ""
                
                title = re.sub(r'New Listing|Sponsored', '', title, flags=re.IGNORECASE).strip()
                
                # Verify that the price is within range
                if 0.0 < price_val <= max_price:
                    # Filter out accessory listings if searching for shoes
                    if is_shoe_query and title:
                        title_lower = title.lower()
                        normalized_title = re.sub(r'[^a-z0-9]', ' ', title_lower)
                        
                        has_shoe_kw = any(re.search(r'\b' + re.escape(kw) + r'\b', normalized_title) for kw in SHOE_KEYWORDS)
                        has_accessory_kw = any(re.search(r'\b' + re.escape(kw) + r'\b', normalized_title) for kw in ACCESSORY_KEYWORDS)
                        
                        if not has_shoe_kw or has_accessory_kw:
                            continue
                            
                    all_candidate_urls.append(clean_url)
                    page_added += 1
                        
            self.logger.info(f"Collected {page_added} valid candidates on page {page_num}. Total in pool: {len(all_candidate_urls)}")
            
            # If we collected 15 or more valid candidates, we can stop fetching more pages
            if len(all_candidate_urls) >= 15:
                break
                
            # Try to click next page button
            next_btn = self.page.locator(self.next_page_btn)
            if next_btn.count() > 0 and next_btn.first.is_visible() and next_btn.first.get_attribute("aria-disabled") != "true":
                try:
                    self.logger.info("Clicking next page button...")
                    next_btn.first.click()
                    self.page.wait_for_load_state("load")
                    page_num += 1
                except Exception as e:
                    self.logger.warning(f"Could not click next page button: {e}")
                    break
            else:
                self.logger.info("No more pages available.")
                break
                
                # Perform random selection from candidate pool
        if len(all_candidate_urls) > limit:
            import random
            import time
            
            # Seed the random number generator using current time in milliseconds
            ms_seed = int(time.time() * 1000)
            random.seed(ms_seed)
            
            # Shuffle the candidate list first using the newly seeded randomizer
            shuffled_candidates = all_candidate_urls.copy()
            random.shuffle(shuffled_candidates)
            
            # Select the items
            selected_urls = random.sample(shuffled_candidates, limit)
            self.logger.info(f"Randomly selected {limit} items using millisecond seed {ms_seed}.")
        else:
            selected_urls = all_candidate_urls
            
        return selected_urls

    def assertSearchItemsFound(self, query: str, max_price: float, limit: int = 5) -> list:
        """
        Executes the search and asserts that at least one item was found under the price constraint.
        """
        self.logger.info(f"Executing search and asserting results found for query '{query}' under price {max_price}...")
        urls = self.searchItemsByNameUnderPrice(query, max_price, limit)
        assert len(urls) > 0, f"Search failed: No items found for '{query}' under budget of {max_price}."
        return urls
