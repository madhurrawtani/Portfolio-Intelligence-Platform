# Release Notes - AI Portfolio Analyzer v1.0 (Production Release)

We are pleased to announce the official release of **Version 1.0** of the AI Portfolio Analyzer. This release marks the completion of the core development lifecycle, transforming the screenshot-based OCR parser into a premium client-facing advisory platform.

---

## 🌟 Key Features Released

### 1. Multi-Screenshot OCR Portfolio Extraction
* **Gemini Vision Parser**: Extract stock assets, quantities, and buy prices directly from one or multiple screenshots.
* **Consolidation**: Holdings are automatically normalized (standardizing tickers and corporate names) and merged into a single consolidated position statement.

### 2. Prioritized Grounded Broker Research Consensus
* **Broker Search Grounding**: Scrapes DuckDuckGo search context for **Nirmal Bang** and **Motilal Oswal** equity reports.
* **Consensus Rating**: Synthesizes a consensus rating when both are available, falls back to single-source if only one has coverage, and uses general web research as a safe fallback.
* **Python Scoring Engine**: Determines rating confidence (0-100%) and factor breakdowns programmatically in Python (avoiding LLM score hallucinations).
* **Date Safety Handler**: Publication dates are parsed strictly from research results. If unavailable, it substitutes with retrieval timestamps to avoid AI-generated dates.

### 3. Yahoo Finance Market Data Integration
* **Provider Layer**: Queries public Yahoo Finance endpoints without SSL package issues, validates datasets, sorts dates chronologically, and repairs duplicate or missing records.
* **Market Intelligence Engine**: Calculates technical trend, momentum, volatility, and volume breakout metrics dynamically from historical Yahoo Finance data.

### 4. Dynamic Portfolio Health Diagnostics
* **Health Score (0-100)**: Evaluates rating quality, sector exposure, stock concentration, and rating confidence.
* **Sector Resolution Hierarchy**: Dynamically classifies sectors using a local mapping table, live Yahoo Finance API search, or LLM context lookups.
* **Risk Profile Limits**: Sizing limits adapt dynamically to the selected profile:
  - *Conservative*: Stock Cap = 15.0% | Sector Cap = 30.0%
  - *Balanced*: Stock Cap = 25.0% | Sector Cap = 45.0%
  - *Aggressive*: Stock Cap = 35.0% | Sector Cap = 60.0%

### 5. Advisory Weight Optimizer & Rebalancing
* **Asset Exclusions**: Filters out all assets with `Sell` or `Reduce` ratings.
* **Iterative Sizing Cap**: Limits overweight holdings and proportionally redistributes excess weight to uncapped active assets.
* **Action Steps**: Maps required rebalancing transaction rules: `Increase Exposure` (change > 2%), `Reduce Exposure` (change < -2%), or `Maintain Exposure`.

### 6. Premium Client Dashboard & Visual PDF Reports
* **Executive Summary**: Premium overview card displaying Portfolio Health, Market Intelligence, Research Consensus, top opportunities, and largest risks at first glance.
* **Redesigned Grid Layout**: Streamlined holdings, rebalancing actions, and independent factor breakdown columns utilizing colored badges (🟢, 🟡, 🔴) for client views.
* **ReportLab Compiler**: ReportLab-based advisory layout featuring cover sheet, executive summary, tables, disclosures, and disclaimer matching the website.
* **Decorators Canvas**: Custom `NumberedCanvas` prints header borders and dynamic page numbering ("Page X of Y").
* **INR Formatting**: Currencies formatted to Indian Rupees (`Rs. XX,XX,XXX.XX`).
* **Visual Diagrams**: Matplotlib rendering for current vs. recommended allocations, sector allocations, and rating distributions.

---

## 🔧 Infrastructure & Deployment

* **EPHEMERAL SAFE STORAGE**: Configured `.dockerignore` and Docker volumes to persist user uploads and outputs.
* **DOCKERIZATION**: Created `Dockerfile` and `docker-compose.yml` for local container runtimes.
* **BLUEPRINT DEPLOY**: Created `render.yaml` for instant deployment on Render.
* **STREAMLIT CLOUD**: Compatible with Streamlit Community Cloud secret keys structure.
* **PERSISTENT CACHING**: Persistent caching layer saves web research for 24 hours in `outputs/research_cache.json` to optimize API usage.
* **ROBUSTNESS**: Handled missing sectors, quantities, or prices gracefully using `safe_float` type conversion checks.
