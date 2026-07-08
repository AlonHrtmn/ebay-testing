# eBay E2E Test Automation Framework

A premium, high-performance, and maintainable end-to-end (E2E) test automation suite for eBay. Built using **Python**, **Playwright**, and **pytest**, this framework follows the Page Object Model (POM), Object-Oriented Programming (OOP), Single Responsibility Principle (SRP), and Data-Driven testing design guidelines.

## 📊 Project Execution Flow
The sequence diagram below visualizes the execution flow of `main.py` calling the page objects:

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'fontSize': '16px', 'fontFamily': 'Outfit, sans-serif'}}}%%
sequenceDiagram
    autonumber
    actor User as Alon / Reviewer
    participant Main as main.py (Runner)
    participant Data as test_data.json
    participant Search as SearchPage
    participant Prod as ProductPage
    participant Cart as CartPage

    User->>Main: python main.py
    Main->>Data: Load parameters
    Data-->>Main: Return (query, max_price, limit)
    
    Main->>Search: searchItemsByNameUnderPrice()
    Search->>Search: Apply price filter on site
    Search->>Search: Collect item URLs (auto-paginate)
    Search-->>Main: Return URLs list (up to 5)
    
    Main->>Prod: addItemsToCart(urls)
    loop For each item URL
        Prod->>Prod: Select random variants
        Prod->>Prod: Click "Add to Cart"
        Prod->>Prod: Save screenshot (item_X_added.png)
    end
    Prod-->>Main: Return count of successfully added items
    
    Main->>Cart: assertCartTotalNotExceeds()
    Cart->>Cart: Retrieve subtotal (JS parser)
    Cart->>Cart: Assert subtotal <= max allowed budget
    Cart->>Cart: Save validation screenshot
    Cart-->>Main: Done (Success)
```

---

## 📐 Object-Oriented Architecture (UML Class Diagram)

The class diagram below visualizes the inheritance structure and class relationships of the Page Object Model (POM) implementation:

```mermaid
classDiagram
    class BasePage {
        +Page page
        +Logger logger
        +navigate(url, wait_until)
        +wait_for_page_ready(timeout)
        +pause(milliseconds)
        +take_screenshot(name)
        +locator(selector)
        +visible_locator(selector, timeout)
        +has_visible_element(selector, timeout)
        +click_element(selector, timeout)
        +fill_input(selector, value, timeout)
        +dismiss_blocking_overlays(context)
    }

    class LoginPage {
        +open_login_page()
        +start_guest_session()
        +login_stub(username, password)
    }

    class SearchPage {
        +open()
        +execute_search(query)
        +apply_buy_it_now_filter()
        +apply_max_price_filter(max_price)
        +search_items_by_name_under_price(query, max_price, limit)
        +collect_candidates(query, max_price, target_count)
        +go_to_next_results_page()
        +select_candidate_urls(candidates, limit)
        +assert_search_items_found(query, max_price, limit)
    }

    class ProductPage {
        +select_random_variants()
        +get_product_price()
        +product_has_real_image()
        +add_to_cart(max_price, screenshot_name)
        +addItemsToCart(urls, max_price, desired_count)
        +assertItemsAddedToCart(urls, max_price, desired_count)
    }

    class CartPage {
        +open()
        +is_cart_page()
        +is_verification_page()
        +raise_if_verification_required()
        +clear_cart()
        +get_subtotal()
        +wait_for_cart_item_images(expected_count)
        +assert_cart_total_not_exceeds(budget_per_item, items_count)
    }

    class MainScript {
        +main()
    }

    class TestSuite {
        +test_ebay_shopping_flow(page)
    }

    %% Inheritance Relationships
    BasePage <|-- LoginPage : inherits
    BasePage <|-- SearchPage : inherits
    BasePage <|-- ProductPage : inherits
    BasePage <|-- CartPage : inherits

    %% Usage/Dependency Relationships
    MainScript ..> LoginPage : instantiates & uses
    MainScript ..> SearchPage : instantiates & uses
    MainScript ..> ProductPage : instantiates & uses
    MainScript ..> CartPage : instantiates & uses

    TestSuite ..> LoginPage : instantiates & uses
    TestSuite ..> SearchPage : instantiates & uses
    TestSuite ..> ProductPage : instantiates & uses
    TestSuite ..> CartPage : instantiates & uses
```

---

## 📋 Features & Architecture

*   **Page Object Model (POM)**: Separates page-specific selector elements and browser interaction methods from the test logic.
    *   `SearchPage`: Handles searches, sidebar price filters, page scraping, and page-by-page pagination.
    *   `ProductPage`: Identifies item options and dynamic dropdowns (size/color), selects random variants, and adds items to the cart.
    *   `CartPage`: Opens the shopping cart, extracts the total subtotal, and validates budget calculations.
*   **Data-Driven Configuration**: Read test parameters dynamically from the external configuration file `config/test_data.json` instead of hardcoding values.
*   **Robust Selectors & Auto-Waiting**: Playwright automatically handles element states (visibility, activity), replacing fragile static waits.
*   **Anti-Bot & Captcha Mitigation**: Utilizes specialized User-Agents, locale constraints, and viewport configurations to bypass anti-bot security systems.
*   **Screenshots & Reporting**: 
    *   Captures screenshots on every successful item addition and final cart verification.
    *   Automatically captures error screenshots on any test failure.
    *   Generates an interactive, self-contained HTML report detailing execution logs and embedding screenshots.
*   **CI/CD Integration**: Preconfigured with a **GitHub Actions** cloud workflow (`.github/workflows/run-tests.yml`) to automatically execute tests on code pushes and upload results as build artifacts.

---

## 🛠️ Prerequisites

*   **Python**: Python 3.11 or newer.
*   **pip**: Python package installer.

---

## 🚀 Setup & Installation

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd ebay-automation-tests
    ```

2.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright Web Driver**:
    ```bash
    python -m playwright install chromium
    ```

---

## 🏃 Running the Tests

You can run the assignment either as a standalone script or through the pytest framework:

### 1. Direct Script Execution (main.py - Recommended for Review)
Runs the three requested functions sequentially in a visible, headed browser window so you can watch the automated flow live:
```bash
python main.py
```

### 2. Pytest Execution (Generates HTML Report)
Runs tests in the background (headless) and generates an interactive, self-contained HTML report with embedded screenshots:
```bash
pytest --html=reports/report.html --self-contained-html
```
*The HTML report is saved under `reports/report.html` and can be opened in any browser.*

### 3. Pytest Headed Run (Watch execution via pytest)
```bash
pytest --headed --html=reports/report.html --self-contained-html
```

---

## 📂 Project Structure

```
ebay-automation-tests/
├── .github/
│   └── workflows/
│       └── run-tests.yml      # CI/CD GitHub Actions cloud workflow
├── config/
│   └── test_data.json         # Data-driven JSON inputs (search query, max price, limit)
├── pages/
│   ├── base_page.py           # Shared utilities (navigation, screenshots, auto-waits)
│   ├── search_page.py         # Search page, price filter, pagination
│   ├── product_page.py        # Product details, variant selection, add to cart
│   └── cart_page.py           # Cart page, subtotal reading and assertion
├── reports/                   # Holds generated HTML reports
├── screenshots/               # Holds step screenshots (item added, cart subtotal, failures)
├── tests/
│   ├── conftest.py            # Pytest browser configuration fixtures & hooks
│   └── test_ebay_flow.py      # E2E shopping flow test case
├── utils/
│   ├── helpers.py             # Price cleaner and parsing logic
│   └── logger.py              # Log setup
├── requirements.txt           # Python library dependencies
└── ReadMeAIBugs.md            # Static code analysis of the buggy AI script
```

---

## ⚙️ Data-Driven Inputs Configuration

To change the search items or target budget values, modify `config/test_data.json`:
```json
{
  "search_query": "shoes",
  "max_price": 220.0,
  "item_limit": 5
}
```

*   `search_query`: The item to search for on eBay.
*   `max_price`: The maximum allowed budget price per single item.
*   `item_limit`: The target number of items to collect and add to the cart.

---

## ⚠️ Assumptions & Limitations

1.  **Guest Flow**: Per instructions, the login stage is stubbed out. The test executes as a Guest Checkout (searching, picking variants, adding to cart, and checking out total price) to avoid captcha blocks on authentication forms.
2.  **Locale / Currency**: Prices are parsed using regex-based extraction. The system cleans currency symbols (`$`, `₪`, `£`, `ILS`, etc.) and supports both dot (`.`) and comma (`,`) decimal separators.
3.  **Variant Selection**: If a product has variant dropdowns (e.g. shoe size, color), the framework selects a random option among the available ones. If no option is selected or required, it skips directly to "Add to cart".
