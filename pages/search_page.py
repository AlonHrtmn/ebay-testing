import random
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote_plus

from playwright.sync_api import Locator

from pages.base_page import BasePage
from utils.helpers import parse_price


@dataclass(frozen=True)
class SearchCandidate:
    item_id: str
    title: str
    price: float

    @property
    def url(self) -> str:
        return f"https://www.ebay.com/itm/{self.item_id}"


class SearchPage(BasePage):
    EBAY_HOME_URL = "https://www.ebay.com"
    SEARCH_INPUT = "#gh-ac"
    SEARCH_BUTTON_NAME = "Search"
    PRICE_MAX_INPUT_NAME = "_udhi"
    ITEM_LINK_SELECTOR = "xpath=//a[contains(@href, '/itm/')]"
    PRICE_PATTERN = re.compile(r"(?:ILS|\$|\u20aa|\u00a3|GBP|EUR)\s*\d+(?:[.,]\d+)?", re.IGNORECASE)
    ITEM_ID_PATTERN = re.compile(r"/itm/(\d+)")
    PLACEHOLDER_IMAGE_TERMS = (
        "s.gif",
        "spacer",
        "placeholder",
        "noimage",
        "no-image",
        "no_image",
        "blank",
        "transparent",
        "loading",
        "lazy-load",
        "pixel.",
    )

    NEXT_PAGE_SELECTOR = (
        "a.pagination__next, "
        "a[aria-label='Go to next search page'], "
        "a[aria-label='Next page'], "
        "a.pagination__next-icon"
    )

    SHOE_KEYWORDS = {
        "shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "sandal",
        "sandals", "slipper", "slippers", "clog", "clogs", "footwear",
        "loafer", "loafers", "flats", "flat", "oxford", "oxfords", "mule",
        "mules", "slide", "slides", "runner", "runners", "trainer",
        "trainers", "slip", "slip-on", "slip-ons", "bootie", "booties",
        "cleats", "brogue", "brogues", "pump", "pumps", "heels",
    }

    ACCESSORY_KEYWORDS = {
        "sock", "socks", "laces", "horn", "horns", "polish", "cleaner",
        "cleaners", "brush", "brushes", "spray", "shield", "shields",
        "protector", "tree", "trees", "rack", "racks", "organizer",
        "organizers", "box", "boxes", "bag", "bags", "insole", "insoles",
        "insert", "inserts", "cushion", "cushions", "keychain", "keyring",
        "charm", "charms", "sticker", "stickers", "display", "hanger",
        "deodorizer", "remover", "storage", "stand", "cabinet", "shirt",
        "shirts", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees",
        "hoodie", "hoodies", "sweatshirt", "sweatshirts", "jacket",
        "jackets", "pants", "shorts", "cap", "caps", "hat", "hats",
        "beanie", "beanies", "clothing", "apparel", "costume", "costumes",
        "dress", "dresses", "skirt", "skirts", "jeans", "towel", "towels",
        "lace", "laces", "shoelace", "shoelaces", "shoestring",
        "shoestrings", "schnursenkel", "schnuersenkel", "senkel", "schuhband",
        "schuhbaender",
        "polish", "paints", "dyes", "conditioner", "conditioners", "cream",
        "creams", "repair", "repairs", "glue", "adhesive", "adhesives",
        "angelus",
    }

    QUERY_SHOE_KEYWORDS = {
        "shoe", "sneaker", "boot", "sandal", "slipper", "clog",
        "footwear", "loafer", "flat", "oxford", "mule", "slide",
    }
    ACCESSORY_PATTERNS = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bshoe\s*laces?\b",
            r"\bshoe\s*strings?\b",
            r"\bshoelaces?\b",
            r"\bshoestrings?\b",
            r"\blaces?\s+for\s+(?:shoes|sneakers|boots)\b",
            r"\b(?:round|flat)\s+laces?\b",
            r"\breplacement\s+laces?\b",
            r"\bschnursenkel\b",
            r"\bschnuersenkel\b",
            r"\bsenkel\b",
            r"\bschuhbaender\b",
            r"\bschuhband\b",
            r"\bshoe\s+(?:care|repair|polish|paint|dye|glue)\b",
            r"\bleather\s+(?:paint|dye|cream|conditioner|repair|care)\b",
            r"\b(?:paint|dye|polish|cleaner|conditioner|cream|repair|glue|adhesive)s?\s+(?:for\s+)?(?:shoes|sneakers|boots|leather)\b",
            r"\b(?:shoes|sneakers|boots|leather)\s+(?:paint|dye|polish|cleaner|conditioner|cream|repair|glue|adhesive)s?\b",
            r"\bangelus\b",
        )
    )
    SEARCH_READY_SELECTORS = (
        "ul.srp-results li.s-item, "
        "div.srp-river-results li.s-item, "
        "a[href*='/itm/']"
    )
    SAMPLE_POOL_MULTIPLIER = 3

    def open(self) -> None:
        if not re.search(r"https://(www|www\.sandbox)\.ebay\.com(?:/|$)", self.page.url):
            self.navigate(self.EBAY_HOME_URL)

    def execute_search(self, query: str) -> None:
        self.logger.info("Searching eBay for: %s", query)
        self.open()
        if self.has_visible_element(self.SEARCH_INPUT, timeout=self.SHORT_TIMEOUT_MS):
            self.fill_input(self.SEARCH_INPUT, query)
            if not self.submit_search_with_button():
                self.logger.info("Search button was unavailable; submitting search with Enter.")
                self.page.press(self.SEARCH_INPUT, "Enter")
        else:
            self.logger.warning(
                "Search input was unavailable; opening search results URL directly."
            )
            self.navigate(self.search_url(query), wait_until="domcontentloaded")
        self.wait_for_page_ready()
        self.wait_for_search_results_shell()
        self.apply_buy_it_now_filter()

    @classmethod
    def search_url(cls, query: str) -> str:
        return f"{cls.EBAY_HOME_URL}/sch/i.html?_nkw={quote_plus(query)}"

    def submit_search_with_button(self) -> bool:
        search_button = self.page.get_by_role("button", name=self.SEARCH_BUTTON_NAME, exact=True)
        try:
            search_button.wait_for(state="visible", timeout=self.SHORT_TIMEOUT_MS)
            search_button.click()
            return True
        except Exception as exc:
            self.logger.warning("Could not submit search with button: %s", exc)
            return False

    def wait_for_search_results_shell(self) -> None:
        try:
            self.page.wait_for_selector(
                self.SEARCH_READY_SELECTORS,
                state="attached",
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
        except Exception as exc:
            self.logger.warning("Search results shell was not detected after submit: %s", exc)

    def apply_buy_it_now_filter(self) -> bool:
        buy_it_now = self.page.locator("a:has-text('Buy It Now'), a[aria-label='Buy It Now']")
        success = False
        try:
            if buy_it_now.count() > 0 and buy_it_now.first.is_visible():
               self.logger.info("Applying Buy It Now filter.")
               buy_it_now.first.click()
               self.wait_for_page_ready()
               self.pause(2000)
               success = True 

        except Exception as exc:
            self.logger.warning("Could not apply Buy It Now filter: %s", exc)
            
        return success

    def apply_max_price_filter(self, max_price: float) -> bool:
        self.logger.info("Applying max price filter: %s", max_price)
        selector = f"input[name='{self.PRICE_MAX_INPUT_NAME}']"

        if not self.has_visible_element(selector, timeout=3000, warn_on_timeout=False):
            self.logger.info("Price filter input was not available; filtering client-side.")
            return False

        try:
            self.fill_input(selector, str(int(max_price)))
            self.page.press(selector, "Enter")
            self.wait_for_page_ready()
            self.logger.info("Applied max price filter through eBay UI.")
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply max price filter through UI: %s", exc)
            return False

    def search_items_by_name_under_price(
        self,
        query: str,
        max_price: float,
        limit: int = 5,
    ) -> list[str]:
        self.logger.info(
            "Searching items by name under price: query=%s, max_price=%s, limit=%s",
            query,
            max_price,
            limit,
        )
        self.execute_search(query)
        self.apply_max_price_filter(max_price)

        fallback_pool_size = max(limit * self.SAMPLE_POOL_MULTIPLIER, limit + 5)
        candidates = self.collect_candidates(
            query=query,
            max_price=max_price,
            target_count=fallback_pool_size,
        )
        selected = self.select_candidate_urls(candidates, fallback_pool_size)
        self.logger.info(
            "Selected %s candidate item URL(s) for a target of %s cart item(s).",
            len(selected),
            limit,
        )
        return selected

    def collect_candidates(self, query: str, max_price: float, target_count: int) -> list[SearchCandidate]:
        is_shoe_query = self.is_shoe_query(query)
        candidates: list[SearchCandidate] = []
        seen_urls: set[str] = set()
        page_number = 1

        while len(candidates) < target_count:
            self.logger.info("Scanning search results page %s.", page_number)

            if not self.wait_for_results(page_number):
                break

            added = self.collect_candidates_from_current_page(
                max_price=max_price,
                is_shoe_query=is_shoe_query,
                seen_urls=seen_urls,
                candidates=candidates,
            )
            self.logger.info(
                "Collected %s valid candidate(s) on page %s; pool size=%s.",
                added,
                page_number,
                len(candidates),
            )

            if len(candidates) >= target_count or not self.go_to_next_results_page():
                break

            page_number += 1

        return candidates

    def wait_for_results(self, page_number: int) -> bool:
        try:
            self.page.wait_for_selector(
                self.ITEM_LINK_SELECTOR,
                state="attached",
                timeout=self.DEFAULT_TIMEOUT_MS,
            )
            return True
        except Exception as exc:
            self.logger.warning("Timed out waiting for item links on page %s: %s", page_number, exc)
            self.take_screenshot(f"search_timeout_page_{page_number}.png")
            return False

    def collect_candidates_from_current_page(
        self,
        max_price: float,
        is_shoe_query: bool,
        seen_urls: set[str],
        candidates: list[SearchCandidate],
    ) -> int:
        added = 0
        links = self.page.locator(self.ITEM_LINK_SELECTOR).all()
        self.logger.info("Found %s raw item link(s).", len(links))

        for link in links:
            candidate = self.build_candidate(link, max_price, is_shoe_query)
            if candidate is None or candidate.url in seen_urls:
                continue

            seen_urls.add(candidate.url)
            candidates.append(candidate)
            added += 1

        return added

    def build_candidate(
        self,
        link: Locator,
        max_price: float,
        is_shoe_query: bool,
    ) -> SearchCandidate | None:
        item_id = self.extract_item_id(link)
        if item_id is None:
            return None

        price = self.extract_price_near_link(link)
        if not (0.0 < price <= max_price):
            return None

        title = self.extract_title(link)
        if not title or not self.link_has_real_image(link):
            return None

        if is_shoe_query and not self.title_matches_shoe_intent(title):
            return None

        return SearchCandidate(item_id=item_id, title=title, price=price)

    def extract_item_id(self, link: Locator) -> str | None:
        url = link.get_attribute("href") or ""
        match = self.ITEM_ID_PATTERN.search(url)
        if not match:
            return None

        item_id = match.group(1)
        if item_id == "123456":
            return None
        return item_id

    def extract_price_near_link(self, link: Locator) -> float:
        for depth in range(1, 9):
            ancestor = link.locator(f"xpath=./ancestor::*[{depth}]")
            if ancestor.count() == 0:
                continue

            text = ancestor.first.inner_text() or ""
            price_match = self.PRICE_PATTERN.search(text)
            if price_match:
                return parse_price(price_match.group(0))

        return 0.0

    def extract_title(self, link: Locator) -> str:
        title = link.inner_text() or ""
        image = link.locator("xpath=.//img")

        if not title and image.count() > 0:
            title = image.first.get_attribute("alt") or image.first.get_attribute("title") or ""

        return re.sub(r"New Listing|Sponsored", "", title, flags=re.IGNORECASE).strip()

    def link_has_real_image(self, link: Locator) -> bool:
        image = link.locator("xpath=.//img")
        if image.count() == 0:
            return False

        image_url = self.first_image_url(image.first)
        return self.is_real_image_url(image_url)

    @classmethod
    def first_image_url(cls, image: Locator) -> str:
        for attribute in ("src", "data-src", "data-original", "data-lazy-src", "srcset"):
            value = image.get_attribute(attribute) or ""
            if value:
                return value.split(",")[0].strip().split(" ")[0]
        return ""

    @classmethod
    def is_real_image_url(cls, image_url: str) -> bool:
        normalized_url = image_url.strip().lower()
        if not normalized_url:
            return False

        return not any(term in normalized_url for term in cls.PLACEHOLDER_IMAGE_TERMS)

    @classmethod
    def title_matches_shoe_intent(cls, title: str) -> bool:
        normalized = cls.normalize_words(title)
        if cls.is_accessory_text(normalized):
            return False

        has_shoe_keyword = cls.contains_any_keyword(normalized, cls.SHOE_KEYWORDS)
        return has_shoe_keyword

    def go_to_next_results_page(self) -> bool:
        next_button = self.page.locator(self.NEXT_PAGE_SELECTOR)
        if (
            next_button.count() == 0
            or not next_button.first.is_visible()
            or next_button.first.get_attribute("aria-disabled") == "true"
        ):
            self.logger.info("No additional results page is available.")
            return False

        try:
            self.logger.info("Opening next results page.")
            next_button.first.click()
            self.wait_for_page_ready()
            return True
        except Exception as exc:
            self.logger.warning("Could not open next results page: %s", exc)
            return False

    def select_candidate_urls(self, candidates: list[SearchCandidate], limit: int) -> list[str]:
        urls = [candidate.url for candidate in candidates]
        if not urls:
            return []

        rng = random.SystemRandom()
        rng.shuffle(urls)
        selected = urls[:limit]
        self.logger.info("Randomly selected up to %s item(s).", limit)
        return selected

    @staticmethod
    def normalize_words(text: str) -> str:
        ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]", " ", ascii_text.lower())

    @classmethod
    def is_accessory_text(cls, text: str) -> bool:
        normalized = cls.normalize_words(text)
        if cls.contains_any_keyword(normalized, cls.ACCESSORY_KEYWORDS):
            return True

        compact = normalized.replace(" ", "")
        return any(pattern.search(normalized) or pattern.search(compact) for pattern in cls.ACCESSORY_PATTERNS)

    @classmethod
    def is_shoe_query(cls, query: str) -> bool:
        lowered_query = query.lower()
        return any(keyword in lowered_query for keyword in cls.QUERY_SHOE_KEYWORDS)

    @classmethod
    def contains_any_keyword(cls, text: str, keywords: Iterable[str]) -> bool:
        normalized = cls.normalize_words(text)
        return any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords)

    def assert_search_items_found(self, query: str, max_price: float, limit: int = 5) -> list[str]:
        urls = self.search_items_by_name_under_price(query, max_price, limit)
        assert urls, f"Search failed: no items found for '{query}' under budget of {max_price}."
        return urls

    # Backward-compatible API expected by the current tests.
    def searchItemsByNameUnderPrice(self, query: str, max_price: float, limit: int = 5) -> list[str]:
        return self.search_items_by_name_under_price(query, max_price, limit)

    def assertSearchItemsFound(self, query: str, max_price: float, limit: int = 5) -> list[str]:
        return self.assert_search_items_found(query, max_price, limit)
