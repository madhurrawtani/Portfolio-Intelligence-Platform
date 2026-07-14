# Project State - AI Portfolio Analyzer v1.0

This document provides a technical overview of the system architecture, directory layouts, data flows, and development roadmap for Version 1.0.

---

## 🏗️ System Architecture

The AI Portfolio Analyzer is built as a highly modular, decoupled application separating visual rendering, OCR extraction, web research grounding, quantitative diagnostics, target-weight optimization, and PDF report compilation.

```mermaid
graph TD
    A[app.py - Streamlit UI] --> B[analyzer.py - OCR & Normalization]
    A --> C[research.py - Search & Grounding]
    A --> D[health.py - Portfolio Diagnostics]
    A --> E[advisory.py - Weight Optimizer]
    A --> F[report_generator.py - Report & Chart Engine]
    
    C -->|API/Scraping| G[AI & Web Grounding APIs]
    D -->|Sector Metadata| H[Yahoo Finance Search API]
    F -->|Draw flowables| I[ReportLab / Matplotlib]
```

---

## 📁 Folder Structure

```
portfolio-analyzer/
├── outputs/                  # Persistent data directory
│   ├── research_cache.json   # Persistent 24h research cache
│   └── portfolio_report_*.pdf# Pre-generated client PDF reports
├── advisory.py               # Optimized target allocation & rebalancing
├── analyzer.py               # Gemini Vision OCR & ticker name standardizer
├── app.py                    # Streamlit Dashboard UI & state control
├── health.py                 # Risk-profile-aware health scoring
├── report_generator.py       # Matplotlib visualizer & ReportLab PDF compiler
├── research.py               # DuckDuckGo scraper, consensus, & confidence
├── Dockerfile                # Docker container configuration
├── docker-compose.yml        # Docker compose configuration
├── render.yaml               # Render Blueprint deploy configuration
├── requirements.txt          # Python dependencies
├── installation.md           # Local installation guide
├── deployment.md             # Cloud deployment instructions
├── PROJECT_STATE.md          # Current project state (this file)
├── test_health.py            # Test suite for health scoring & sector lookups
├── test_advisory.py          # Test suite for rebalancing & exclusions
└── test_live_openrouter.py   # Test suite for OpenRouter API grounded research
```

---

## ⚙️ Implemented Modules

1. **Portfolio OCR & Normalization (`analyzer.py`)**: Uses the Gemini 2.5 Flash model with Structured JSON Outputs to read screenshot images. Converts raw portfolio rows into standardized tickers, quantities, average costs, and current values.
2. **Web Grounded Research (`research.py`)**: Runs DuckDuckGo web searches for Nirmal Bang, Motilal Oswal, and Web fallbacks. Grounded reports are analyzed by an LLM to generate consensus ratings, targets, and dates. Python parses the categorical parameters into a final **Confidence Score (0-100%)**.
3. **Health Engine (`health.py`)**: Computes the **Portfolio Health Score (0-100)**. Sizing concentration limits and sector exposure limits are checked relative to the selected Risk Profile. Tickers are resolved to industry sectors using a static mapping table, dynamic Yahoo Finance lookups, or LLM fallbacks.
4. **Advisory & Rebalancing (`advisory.py`)**: Excludes Sell-rated assets, maps target weights based on broker ratings, applies risk-profile sector biases, runs iterative stock capping (15%/25%/35%), redistributes excess weights, and flags required transaction actions (`Increase`, `Reduce`, or `Maintain` exposure).
5. **PDF Report Engine (`report_generator.py`)**: Implements double-pass `NumberedCanvas` to draw dynamic "Page X of Y" headers/footers, formats currencies to Indian Rupees (`Rs. XX,XX,XXX.XX`), generates matplotlib plots (Allocation, Sector, Recommendations), and compiles sections into a client-facing PDF.

---

## 🌐 External APIs Used

| API Service | Module | Purpose | Authentication |
| :--- | :--- | :--- | :--- |
| **Google GenAI (Gemini)** | `analyzer.py`, `research.py` | Image OCR & optional research summarization | API Key |
| **OpenRouter (Llama 3)** | `research.py` | Grounded research consensus summaries | API Key |
| **Yahoo Finance Search** | `health.py` | Sector metadata resolution lookup | Public (None) |
| **DuckDuckGo HTML Search**| `research.py` | Scraping broker report citations | Public (None) |

---

## 🔄 Data Flow

```
[Upload Screenshots] 
        │
        ▼
[Gemini OCR Image Parsing] ──► Standardizes Stock Names (e.g., RELIANCE)
        │
        ▼
[Sector Lookup Hierarchy] ──► Checks Static Map ──► Yahoo Finance ──► LLM
        │
        ▼
[Research Grounding] ──► Checks Cache ──► Scraping nb/mo reports ──► LLM Consensus
        │
        ▼
[Python Score Calculations] ──► Confidence % Formula & Report Date Safety
        │
        ▼
[Advisory Engine] ──► Excludes Sells ──► Sizing Caps & Redistribution ──► Actions
        │
        ▼
[Matplotlib Plots] ──► Compiles Allocation, Sector, & Ratings distribution
        │
        ▼
[PDF Canvas Compilation] ──► Generates NumberedCanvas ──► Outputs client PDF report
        │
        ▼
[Dashboard UI Update] ──► Renders metrics, plots, and enables file exports (PDF/CSV/JSON)
```

---

## 🛣️ Roadmap for Version 2.0 (Future Milestones)

- **Real-Time Prices**: Integrate a streaming stock market API (e.g. Zerodha Kite Connect, Alpaca, or Yahoo Finance Real-time) to fetch spot market values instead of relying solely on screenshot OCR estimates.
- **Multi-Currency Support**: Support international equities portfolios, allowing seamless toggle between Indian Rupees (INR), US Dollars (USD), and Euros (EUR) across reports.
- **Client Management & DB Persistence**: Add multi-user login authentication and replace local JSON/PDF files with a PostgreSQL database to track historical client portfolio runs over time.
- **Broker Direct Integration**: Allow direct connection to broker accounts (e.g. Zerodha, Upstox, Interactive Brokers) via OAuth to pull holdings automatically without requiring screenshot uploads.
- **One-Click Rebalancing Execution**: Generate trade basket links (e.g., Zerodha Smallcase baskets) to allow clients to execute the recommended rebalancing trades in one click.
