# Deployment Guide - AI Portfolio Analyzer v1.0

This guide explains how to package and deploy the AI Portfolio Analyzer application into production environments.

---

## 🐳 Docker Deployment

The application includes a `Dockerfile` and `docker-compose.yml` to facilitate containerized environments.

### Local Docker Execution

1. Build and start the container using Docker Compose:
   ```bash
   docker-compose up --build -d
   ```
2. The dashboard will be accessible locally at `http://localhost:8501`.
3. Consolidated JSON outputs and PDF reports will be written to the local `./outputs` directory which is mounted as a volume.

### Manual Docker Build

If you are deploying to a container orchestration platform (e.g. AWS ECS, Google Cloud Run, Kubernetes):

1. Build the Docker image:
   ```bash
   docker build -t ai-portfolio-analyzer:v1.0 .
   ```
2. Run the Docker container:
   ```bash
   docker run -p 8080:8501 --env-file .env -v $(pwd)/outputs:/app/outputs ai-portfolio-analyzer:v1.0
   ```
3. Expose port `8080` (or whichever port your environment requires).

---

## 🚀 Render Deployment

Render is a cloud hosting provider suited for deploying Streamlit applications.

### Option A: Deploy using `render.yaml` (Recommended)

1. Commit and push the code to your GitHub/GitLab repository.
2. In the Render Dashboard, click **New > Blueprint**.
3. Select your repository. Render will automatically parse the `render.yaml` file.
4. Set your environment keys (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`) when prompted.
5. Click **Approve**. Render will build and deploy the app.

### Option B: Manual Web Service Setup

1. In Render, select **New > Web Service**.
2. Connect your Git repository.
3. Configure the following service settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Under **Advanced**, add the environment variables listed in `.env.example`.

> [!WARNING]
> **Persistent Disk Mounting (Render)**:
> Since containers are ephemeral, any saved analysis runs and generated PDFs stored in the `outputs/` folder will be lost when the web service restarts.
> To prevent data loss, go to **Disks** in your Render dashboard, click **Add Disk**, mount it to `/app/outputs`, and assign it a size (e.g., 1 GB).

---

## ☁️ Streamlit Community Cloud

Streamlit Community Cloud is a free hosting service directly connected to your GitHub repository.

1. Push your project to a **public or private GitHub repository**.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
3. Click **New App**, then select your repository, branch (usually `main`), and set the main file path to `app.py`.
4. Click **Advanced settings** before deploying.
5. In the **Secrets** text box, paste the variables from your `.env` file using TOML format:
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   RESEARCH_PROVIDER = "openrouter"
   OPENROUTER_API_KEY = "sk-or-v1-..."
   OPENROUTER_MODEL = "meta-llama/llama-3-8b-instruct:free"
   ```
6. Click **Save** and click **Deploy!**

---

## 🔒 Production Best Practices

1. **Security**: Never commit the active `.env` file to version control. It is already added to `.gitignore`.
2. **Resource Allocation**: The app uses Matplotlib for chart rendering and report compilation. Assign at least 512MB of RAM to the container to prevent Out-Of-Memory (OOM) crashes during chart generation.
3. **Session Cache Limit**: Streamlit cache data is stored in memory. For heavy multi-user production, restart the server weekly or adjust Streamlit cache TTL rules to prevent memory leaks.
