# How to Run This Project from Scratch

If an interviewer hands you a fresh laptop and says, *"Pull down your project from GitHub and run it,"* do not panic. This is a very common test to see if you understand environment setup.

Follow these exact steps in order. (Note: These instructions assume Python and Git are already installed on the computer).

### Step 1: Open Terminal and Clone the Code
Open PowerShell (if on Windows) or Terminal (if on Mac) and run:
```bash
git clone https://github.com/AlonHrtmn/ebay-testing.git
cd ebay-testing
```

### Step 2: Create a Virtual Environment (Crucial Step!)
Interviewers **love** seeing candidates use Virtual Environments. It proves you don't pollute the computer's global Python installation.
```bash
python -m venv venv
```

### Step 3: Activate the Virtual Environment
You must activate the isolated environment before installing packages.
* **If you are on Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\activate
  ```
* **If you are on Mac/Linux:**
  ```bash
  source venv/bin/activate
  ```
*(You will know it worked because `(venv)` will appear at the start of your terminal prompt).*

### Step 4: Install Dependencies
Now install the required packages (Pytest, Playwright, Pytest-HTML) exactly as they are defined in your project:
```bash
pip install -r requirements.txt
```

### Step 5: Install Playwright Browsers
Playwright requires its own specific browser engines to run. You only need Chromium for this test:
```bash
playwright install chromium
```

### Step 6: Run the Tests
Now you have two ways to prove it works:

**Option A: Run the visual script (Shows the browser UI)**
```bash
python main.py
```

**Option B: Run the Pytest suite (Generates the HTML report)**
```bash
pytest --headed --html=reports/report.html
```

---

> [!TIP]
> **Pro Interview Move:** If you get to Step 4 and it fails because `requirements.txt` is missing or corrupted, immediately say: *"Ah, let me just install the packages directly."* and run: `pip install pytest pytest-playwright pytest-html`. Being able to recover gracefully is exactly what they want to see!
