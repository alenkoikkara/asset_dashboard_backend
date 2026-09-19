# Agent Context: Asset Dashboard Backend

**Read this document before making architectural changes, adding new features, or modifying the core pipeline.**

This document provides AI agents with context on how to interact with, update, and extend the Asset Dashboard backend codebase.

## 1. System Overview

The application is split into two loosely coupled parts:
- **`pipeline/` (ETL):** Responsible for fetching data, modifying it, and persisting it to `data/output/asset_dashboard.db`.
- **`api/main.py` (API):** Reads from the SQLite DB using `pandas` and serves REST endpoints. It also contains an `AsyncIOScheduler` that runs the pipeline on a schedule (IST market hours).

## 2. Adding or Modifying Brokers (Extractors)

To add support for a new broker (e.g., Upstox, AngelOne, or a Crypto exchange):

1. **Create the Extractor:** Add a new file in `pipeline/extractors/` (e.g., `upstox.py`).
2. **Implement Logic:** Your extractor must return a list of `Holding` objects (defined in `pipeline/models/holding.py`). Ensure proper error handling and logging.
3. **Register the Extractor:** Open `pipeline/run.py` and add your new extractor to the `build_extractors()` function.
   ```python
   def build_extractors():
       return [
           ZerodhaExtractor(),
           GrowwExtractor(),
           NewBrokerExtractor(), # <-- Add here
       ]
   ```
4. **Configuration:** Add any new API keys or credentials to `pipeline/config.py` and `.env.example`.

## 3. Adding Data Enrichments

Enrichers process the merged list of holdings to add metadata (e.g., market data, calendar events, AI analysis).

1. **Create the Enricher:** Add a file in `pipeline/enrichers/`.
2. **Implement Logic:** The enricher should implement an `enrich(holdings: list[Holding]) -> list[Holding]` method.
3. **Register the Enricher:** Add it to the `build_enrichers()` list in `pipeline/run.py`. Be mindful of the order if your enricher depends on data added by another enricher.

## 4. Modifying API Endpoints

All API logic currently resides in `api/main.py`.

- **Data Fetching:** Do not query external APIs directly in `api/main.py` if it can be avoided. Instead, endpoints should use `read_holdings()` to query the local SQLite DB or use `yfinance` for light real-time data like indices.
- **Transformations:** Endpoints frequently use `pandas` for grouping and summarizing data before returning it as JSON.
- **Pipeline Control:** The API has endpoints to trigger the pipeline manually (`/api/pipeline/run`) and check its status.

## 5. Token Management & Scripts

Tokens for Indian brokers (Zerodha, Groww) typically expire daily.
- Scripts to refresh these tokens are located in the `scripts/` directory.
- Avoid hardcoding token logic into the main pipeline; the pipeline should rely on the `.env` variables being up-to-date.

## 6. Testing Changes

When modifying the pipeline, use the `run.py` CLI flags to test without mutating the database or incurring API costs:

```bash
# Test extraction and enrichment, print results, don't write to DB
python -m pipeline.run --dry-run

# Skip AI commentary to save Claude API costs during rapid development
python -m pipeline.run --skip-ai --dry-run
```

## 7. Style & Conventions

- Use standard Python typing (`list[Holding]`, `Optional[str]`).
- Use `logging` instead of `print()` for the pipeline (configured via `pipeline.utils.logging.get_logger`).
- Prefer standard library or minimal dependencies where possible. Keep the `Dockerfile` lean.
