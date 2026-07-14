# Release Checklist - AI Portfolio Analyzer v1.0

Use this checklist to verify production readiness before pushing a new release of the AI Portfolio Analyzer application.

---

## 🛠️ Pre-Release Validation

- [ ] **Dependencies Sync**: Ensure that all required third-party libraries used in the code are listed with minimum versions in `requirements.txt`.
- [ ] **Environment Template**: Verify `.env.example` is complete and contains all required environment variables used by the application, with no real keys committed.
- [ ] **Unit and Integration Tests**:
  - Run `python test_health.py` and confirm all tests pass.
  - Run `python test_advisory.py` and confirm all tests pass.
  - Run `python test_market_data.py` and confirm all tests pass.
- [ ] **Local Verification**:
  - Run `streamlit run app.py` locally and verify the dashboard loads without syntax errors.
  - Upload sample screenshots and verify that positions normalize correctly.
  - Choose different risk profiles in the sidebar and verify that the rebalancing calculations refresh instantly.
- [ ] **PDF Report Rendering**:
  - Run `python C:\Users\HP1\.gemini\antigravity\scratch\test_pdf_gen.py` to ensure that PDF report compilation works.
  - Open the generated PDF report at `outputs/test_report.pdf` and check:
    - Cover page metadata matches expectations.
    - Currency formatting is correct (`Rs. XX,XX,XXX.XX`).
    - Page numbering displays correctly ("Page X of Y").
    - All charts (Matplotlib) render and fit within margins.
    - Table columns wrap cell values with no content clipped.

---

## 🐳 Dockerization Validation

- [ ] **Image Compilation**: Build the container image locally:
  ```bash
  docker build -t ai-portfolio-analyzer:v1.0 .
  ```
- [ ] **Local Run Check**: Launch the container:
  ```bash
  docker run -d -p 8501:8501 --env-file .env -v $(pwd)/outputs:/app/outputs ai-portfolio-analyzer:v1.0
  ```
- [ ] **Container Accessibility**: Navigate to `http://localhost:8501` and verify that the application loads and runs correctly in the container.
- [ ] **Volume Mount Persistence**: Run a test analysis inside the container and check if the output JSON and PDF files are successfully written to your local `./outputs` directory.

---

## 🚀 Deployment Platform Verification

### Render Deploy
- [ ] **Blueprint Configuration**: Review `render.yaml` and confirm the build/start commands and ports match.
- [ ] **Persistent Disk Setup**: Verify a persistent disk is configured and mounted to `/app/outputs` in the Render service settings (to prevent data loss on restarts).
- [ ] **Environment Secrets**: Ensure the required secret keys (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are inputted in the Render settings.

### Streamlit Community Cloud
- [ ] **GitHub Push**: Confirm `.env` and `outputs/` are ignored in `.gitignore`.
- [ ] **Secrets Input**: Paste secrets in TOML format into the App Advanced Settings and click Save before starting deployment.

---

## 📋 Post-Release Sanity Checks

- [ ] **Clean Console Logs**: Check Streamlit console output for any warning messages (e.g. missing Matplotlib font caches or deprecation notices).
- [ ] **Multi-Format Downloads**: In the dashboard Report Center:
  - Download PDF report and verify it matches the latest state.
  - Download Consolidated holdings CSV and inspect it in Excel/Sheets.
  - Download Rebalancing CSV and inspect for proper allocation change values.
  - Download JSON payload and check for backward compatibility.
