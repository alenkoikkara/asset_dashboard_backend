# Asset Dashboard Backend

This repository contains the backend for a comprehensive Asset Dashboard. It aggregates investment portfolio data from various brokers, enriches the data, and serves it via a REST API.

## Architecture

The backend consists of two main components:

1. **ETL Pipeline (`pipeline/`)**:
   - **Extractors**: Fetch holdings from brokers (e.g., Zerodha Kite, Groww).
   - **Enrichers**: Add context to the data, such as real-time market prices, calendar events, and AI-driven sentiment analysis (via Anthropic Claude).
   - **Loaders**: Export the processed data to an SQLite database and CSV files.
   - It can be run manually or automatically via an APScheduler integrated into the FastAPI application.

2. **FastAPI Application (`api/`)**:
   - Serves the aggregated portfolio data stored in SQLite.
   - Provides endpoints for frontend visualization (overall metrics, sector allocations, individual holdings, index benchmarks).
   - Manages and monitors background pipeline runs.

## Setup

1. **Clone the repository and set up a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Copy `.env.example` to `.env` and fill in your API keys:
   - **Kite Connect**: `KITE_API_KEY`, `KITE_ACCESS_TOKEN` (needs daily refresh).
   - **Groww Trade API**: `GROWW_API_KEY`, `GROWW_API_SECRET`, `GROWW_ACCESS_TOKEN`.
   - **Anthropic**: `ANTHROPIC_API_KEY` (for AI commentary).

3. **Generating Tokens**:
   Some tokens expire daily. Use the scripts in the `scripts/` directory to generate/refresh them:
   ```bash
   python scripts/generate_kite_token.py
   python scripts/generate_groww_token.py
   ```

## Running the Application

### Running the ETL Pipeline Manually

You can run the pipeline directly from the command line:

```bash
# Full pipeline run
python -m pipeline.run

# Skip Claude commentary (saves API cost)
python -m pipeline.run --skip-ai

# Print summary without saving to DB/CSV
python -m pipeline.run --dry-run
```

### Running the API Server

```bash
uvicorn api.main:app --reload --port 8002
```

The API will be available at `http://localhost:8002`.

### Docker

You can run the entire backend using Docker Compose:

```bash
docker-compose up -d
```

This will build the image, start the FastAPI server, and mount the `data/` directory.

## Data Storage

Data is persisted in the `data/` directory (mounted as a volume in Docker):
- **Database**: `data/output/asset_dashboard.db` (SQLite).
- **Exports**: `data/output/` (CSV exports).
