# Playwright + Angular + SAP Architecture

This diagram illustrates how your Python Playwright framework would integrate into an enterprise environment where the frontend is built with **Angular** and the backend is an **SAP** ERP system. 

It highlights how your **Page Object Model (POM)** interacts with the Angular UI, and how you can use Playwright's native API capabilities to interact directly with the SAP backend (OData/REST APIs) for faster test setup and teardown.

```mermaid
graph TD
    %% Styling
    classDef framework fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px;
    classDef system fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px;
    classDef data fill:#fff3e0,stroke:#ff9800,stroke-width:2px;

    subgraph "Automation Framework (Python + Playwright)"
        direction TB
        Config[test_data.json]:::data -.->|Data Driven| TestRunner
        
        TestRunner[Pytest / Playwright Test]:::framework
        
        subgraph "Page Object Model (POM)"
            TestRunner --> AngularAppPage[Angular Web Pages]
            TestRunner --> SAPFioriPage[SAP Fiori UI Pages]
        end
        
        TestRunner -.->|Fast Setup/Teardown via API| APIClient[Playwright APIRequestContext]:::framework
    end

    subgraph "System Under Test (Enterprise Environment)"
        direction TB
        AngularAppPage -->|Browser Automation| AngularUI((Angular Frontend)):::system
        SAPFioriPage -->|Browser Automation| SAPUI((SAP Web UI)):::system
        
        AngularUI <-->|REST API| SAPBackend[(SAP ERP Backend / HANA)]:::system
        SAPUI <-->|OData API| SAPBackend
        APIClient <-->|Direct OData / REST Calls| SAPBackend
    end
```

### Key Talking Points for this Diagram:
1. **Angular Frontend (SPAs):** Angular is a Single Page Application. Because elements render dynamically, Selenium often fails here. Playwright's **Auto-waiting** handles Angular's dynamic DOM flawlessly.
2. **SAP Backend (Heavy Systems):** SAP is a massive, slow ERP system. Notice the dotted line from the `TestRunner` to the `SAPBackend`. Instead of automating the SAP UI to create a user or seed test data, a senior engineer uses **Playwright's APIRequestContext** to inject data directly into SAP via API, bypassing the UI completely. This saves minutes of test execution time!
3. **Data-Driven (Config):** The test data flows seamlessly into the tests, just like in your eBay assignment.

*You can open this artifact to view the diagram visually.*
