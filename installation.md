# Installation Guide - AI Portfolio Analyzer v1.0

This guide explains how to set up and run the AI Portfolio Analyzer from scratch in a local environment.

## Prerequisites

1. **Python 3.9 to 3.11** installed on your system.
2. **API Keys** (At least one is required for full functionality):
   - **Gemini API Key**: Required for OCR screenshot reading. Get one from [Google AI Studio](https://aistudio.google.com/).
   - **OpenRouter API Key**: Required if using Llama models for equity research summary grounding (default). Get one from [OpenRouter](https://openrouter.ai/).

---

## Step-by-Step Local Setup

### 1. Clone the Codebase
Navigate to the directory where you want to run the project.

```bash
git clone <repository-url>
cd portfolio-analyzer
```

### 2. Set Up a Virtual Environment (Recommended)
Creating an isolated environment ensures dependencies don't conflict with other Python projects.

* **On Windows (Command Prompt/PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **On macOS/Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Dependencies
Install all required modules from `requirements.txt`:

```bash
pip install -r requirements.txt
```

This will install the core Streamlit application framework, PDF layout compiler (`reportlab`), mathematical plotting tool (`matplotlib`), and AI integration libraries.

### 4. Configure Environment Variables
Copy the template `.env.example` file to create your active configuration:

* **On Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
* **On macOS/Linux/Git Bash:**
  ```bash
  cp .env.example .env
  ```

Open the newly created `.env` file in your preferred text editor and replace the placeholder text with your actual keys:
```env
GEMINI_API_KEY=AIzaSy...
RESEARCH_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=meta-llama/llama-3-8b-instruct:free
```

---

## Verification & Execution

### 1. Run Verification Tests
Verify that the calculation engines and sector resolution mechanisms work correctly:

```bash
python test_health.py
python test_advisory.py
```
Both test suites should return `ALL TESTS PASSED SUCCESSFULLY!` with no errors.

### 2. Run the Application
Launch the Streamlit dashboard server:

```bash
streamlit run app.py
```

The server will initialize and automatically open the dashboard in your web browser (usually at `http://localhost:8501`).

---

## Troubleshooting

- **Matplotlib Font Warnings**: On first startup, Matplotlib might rebuild its font cache. This is normal and takes only a few seconds.
- **Port Conflict**: If port `8501` is already in use, Streamlit will automatically try `8502`, `8503`, etc. You can explicitly set a port with `streamlit run app.py --server.port=8080`.
- **API Key Failures**: Double check that your `.env` contains valid keys and that your internet connection allows outgoing connections to Google's GenAI endpoint and OpenRouter.
