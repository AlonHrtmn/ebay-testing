# Playwright Object Hierarchy in Your Framework

When the interviewer asks, *"How does Playwright actually work under the hood, and what objects are you interacting with?"*, you can use this diagram to explain the core Playwright hierarchy and how you inject it into your Page Object Model (POM).

```mermaid
graph TD
    %% Styling
    classDef pw fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px;
    classDef pom fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;
    classDef dom fill:#fff3e0,stroke:#ff9800,stroke-width:2px;

    subgraph "The Playwright Engine (Injected via Pytest)"
        PW[Playwright Instance]:::pw --> B[Browser <br/>e.g., Chromium]:::pw
        B --> C[BrowserContext <br/>Isolated Incognito Session]:::pw
        C --> P[Page <br/>The specific browser tab]:::pw
    end

    subgraph "Your Automation Code (POM)"
        P -.->|Passed into| BP[BasePage class]:::pom
        BP --> SP[SearchPage]:::pom
        BP --> PP[ProductPage]:::pom
        BP --> CP[CartPage]:::pom
    end

    subgraph "The Website (DOM Interaction)"
        SP --> L[Locator <br/>e.g., page.locator]:::dom
        PP --> L
        CP --> L
        L -->|Action| E[Actual HTML Element <br/>button, input, etc.]:::dom
    end
```

### Key Talking Points for the Interview:
1. **The BrowserContext:** Playwright is powerful because it uses `BrowserContexts`. You can explain: *"Instead of launching a heavy, full browser for every test like Selenium does, Playwright launches one Browser and creates isolated, incognito `BrowserContexts` for each test. This makes tests run incredibly fast and ensures cookies/cache don't leak between tests."*
2. **The `Page` Object:** Your Pytest fixture automatically hands you the `Page` object (representing the active tab). You immediately pass this `Page` into your `BasePage`, which shares it with all your Page Objects (`SearchPage`, `CartPage`).
3. **The `Locator` Object:** Playwright doesn't find elements immediately. It creates a `Locator`—a strict recipe for finding an element. You can explain: *"Playwright Locators are evaluated strictly at the moment of action (like `.click()`). This enables Auto-waiting, because the Locator will constantly poll the DOM until the element is visible and actionable, preventing Stale Element Exceptions."*
