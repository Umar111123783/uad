# UiPath to Power Automate Desktop (Robin) Migration Tool
### Featuring PwC GenAI Gateway Integration

A dedicated tool to inspect UiPath RPA NuGet packages (`.nupkg` and `.zip`), extract workflows (`Main.xaml`), and convert them into **100% paste-validated** Microsoft Power Automate Desktop (PAD Robin) scripts.

---

## 🚀 Quick Start

1. Double-click **`run_converter.bat`** to start the main application.
2. Open your browser at **http://localhost:8502**.
3. Select or upload any `.nupkg` or `.zip` file from the sidebar.
4. Navigate to the **"🧠 Pure LLM Converter (app_llm)"** tab.
5. Paste your **PwC Gateway API-Key** and click **"Convert to PAD Robin with PwC GenAI"**.
6. Copy the plain-text output (`Ctrl + C`), open Power Automate Desktop Designer, and paste (`Ctrl + V`) directly onto the canvas.

---

## 📁 Project Structure

```text
UiPath-to-PAD-Converter/
├── nupkg_browser.py          # Main Streamlit app (NUPKG explorer + PwC LLM + Offline converter)
├── app_llm.py                # Standalone Pure LLM Streamlit app
├── llm.py                    # PwC GenAI Gateway client & Robin formatting rules
├── parser.py                 # UiPath package extractor and XAML optimizer
├── robin_converter.py        # Offline XAML-to-Robin translator and PAD syntax validator
├── run_converter.bat         # 1-click launcher for the main app (port 8502)
├── run_pure_llm.bat          # 1-click launcher for the pure LLM app (port 8503)
├── requirements.txt          # Python dependencies (streamlit, requests)
├── converter/                # Modular conversion pipeline
├── data/                     # Sample UiPath .nupkg bots (AgeChecker, CrudOperation, etc.)
└── pad-robin-action-kb-main/ # Official PAD 2.74 Robin Action Knowledge Base (1,135 actions)
```

---

## 🏢 PwC GenAI Gateway Setup

* **Endpoint**: `https://genai-sharedservice-apac.pwcinternal.com/chat/completions` (Pre-configured)
* **Default Model**: `openai.global.gpt-4.1` (or `openai.global.gpt-4o`, `openai.global.gpt-4o-mini`, `azure.gpt-4o`)
* **Header**: Sent automatically via `API-Key: <your_key>`.

---

## ✅ Paste Validation Guarantee

Generated scripts are verified against **PAD 2.74 syntax rules**:
* Strings are escaped (`$'''...'''` with `\'` for apostrophes).
* Expressions and variables are bare without illegal outer `%` signs.
* Full PAD action selectors and enums are used (e.g. `Display.ShowMessageDialog.ShowMessage`).
* Pastes cleanly into Power Automate Desktop with **0 silent drops or syntax errors**.
