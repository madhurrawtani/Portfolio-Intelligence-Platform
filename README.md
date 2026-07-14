# AI Portfolio Analyzer MVP

An AI-powered portfolio analysis system built using **Streamlit** and the **Gemini Vision API**. It processes portfolio screenshots, extracts stock positions (names, quantities, and average prices), applies a stock name/ticker normalization layer, and displays the consolidated portfolio in a premium interactive dashboard.

## Features

- **Screenshot Upload**: Upload one or more portfolio screenshots (PNG, JPG, JPEG).
- **AI Extraction**: Uses Gemini Vision (e.g., `gemini-2.5-flash`) via structured outputs to extract stock positions.
- **Normalization Layer**: Standardizes extracted stock names (e.g., "HDFC BANK", "HDFCBANK", "HDFC Bank Ltd." map to `HDFCBANK`).
- **Data Consolidation**: Automatically aggregates quantities and calculates weighted average buy prices for duplicate positions across multiple screenshots.
- **JSON Save & Export**: Saves all extraction runs in the `outputs/` folder as structured JSON logs for future research API integration.
- **Run Reloading**: View and reload previous runs directly from the sidebar.

## Folder Architecture

```text
portfolio-analyzer/
├── app.py              # Streamlit frontend & UI dashboard
├── analyzer.py         # Backend Gemini API integration & Stock normalization
├── requirements.txt    # Python dependencies
├── README.md           # Setup and running instructions
└── outputs/            # Extracted JSON logs directory (auto-created)
```

## Setup Instructions

### 1. Prerequisites
Ensure you have Python 3.9 or higher installed on your system.

### 2. Create a Virtual Environment
Navigate to the project root directory and create a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
Install all required libraries using pip:
```bash
pip install -r requirements.txt
```

### 4. Set your Gemini API Key
Obtain an API key from Google AI Studio.

**On Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

**On macOS/Linux:**
```bash
export GEMINI_API_KEY="your_api_key_here"
```

*Alternatively, you can create a `.env` file in the project root directory:*
```env
GEMINI_API_KEY=your_api_key_here
```
*Or simply enter the key in the Streamlit application's sidebar at runtime.*

### 5. Running the Application
Launch the Streamlit server:
```bash
streamlit run app.py
```
This will start a local server and open the app in your default web browser (typically at `http://localhost:8501`).
