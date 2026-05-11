import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = Path(__file__).parent.parent / "data" / "output" / "asset_dashboard.db"

# ── Pipeline state ────────────────────────────────────────────────────────────

_state = {
    "is_running": False,
    "last_run_at": None,
    "last_run_status": None,  # "success" | "error"
    "last_run_error": None,
}


async def _run_pipeline(skip_ai: bool = False) -> None:
    if _state["is_running"]:
        return

    _state["is_running"] = True
    _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    _state["last_run_error"] = None

    try:
        from pipeline.run import run
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: run(skip_ai=skip_ai))
        _state["last_run_status"] = "success"
    except Exception as exc:
        _state["last_run_status"] = "error"
        _state["last_run_error"] = str(exc)
    finally:
        _state["is_running"] = False


# ── Scheduler (IST, Mon–Fri) ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    IST = "Asia/Kolkata"

    scheduler.add_job(_run_pipeline, CronTrigger(hour=9,  minute=18, day_of_week="mon-fri", timezone=IST))
    scheduler.add_job(_run_pipeline, CronTrigger(hour=12, minute=0,  day_of_week="mon-fri", timezone=IST))
    scheduler.add_job(_run_pipeline, CronTrigger(hour=15, minute=35, day_of_week="mon-fri", timezone=IST))

    scheduler.start()
    yield
    scheduler.shutdown()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "https://stan.alenkoikkara.com",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── DB helpers ────────────────────────────────────────────────────────────────

def read_holdings() -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM holdings", conn)
    conn.close()
    return df


def build_summary(holdings: pd.DataFrame) -> pd.DataFrame:
    summary = (
        holdings.groupby("symbol")
        .agg(
            asset_class=("asset_class", "first"),
            sector=("sector", "first"),
            total_invested=("invested_value", "sum"),
            total_current_value=("current_value", "sum"),
            total_unrealized_pnl=("unrealized_pnl", "sum"),
            brokers=("broker", lambda x: ",".join(sorted(x.unique()))),
        )
        .reset_index()
    )
    summary["total_unrealized_pnl_pct"] = (
        summary["total_unrealized_pnl"] / summary["total_invested"] * 100
    )
    return summary


# ── Pipeline endpoints ────────────────────────────────────────────────────────

@app.post("/api/pipeline/run")
async def trigger_pipeline(skip_ai: bool = Query(False)):
    if _state["is_running"]:
        return {"status": "already_running"}
    asyncio.create_task(_run_pipeline(skip_ai=skip_ai))
    return {"status": "triggered"}


@app.get("/api/pipeline/status")
def pipeline_status():
    return _state


# ── Portfolio endpoints ───────────────────────────────────────────────────────

@app.get("/api/portfolio")
def get_portfolio():
    holdings = read_holdings()
    summary = build_summary(holdings)

    total_invested = summary["total_invested"].sum()
    total_current = summary["total_current_value"].sum()
    total_pnl = summary["total_unrealized_pnl"].sum()
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

    holdings["day_change_abs"] = holdings["current_value"] * holdings["day_change_pct"].fillna(0) / 100
    day_change_abs = holdings["day_change_abs"].sum()
    day_change_pct = (day_change_abs / total_current * 100) if total_current else 0.0

    sec = summary.copy()
    sec["sector"] = sec["sector"].fillna("ETF / No Sector")
    sector_alloc = (
        sec.groupby("sector")["total_current_value"]
        .sum()
        .reset_index()
        .rename(columns={"total_current_value": "value"})
        .sort_values("value", ascending=False)
    )

    pnl_by_stock_df = summary[["symbol", "total_unrealized_pnl_pct"]].sort_values(
        "total_unrealized_pnl_pct"
    )

    holdings["_ts"] = pd.to_datetime(holdings["last_updated"], utc=True)
    last_updated = holdings["_ts"].max().strftime("%d %b %Y, %I:%M %p UTC")

    return {
        "kpis": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 4),
            "day_change_abs": round(day_change_abs, 2),
            "day_change_pct": round(day_change_pct, 4),
        },
        "last_updated": last_updated,
        "sector_allocation": json.loads(sector_alloc.to_json(orient="records")),
        "pnl_by_stock": json.loads(pnl_by_stock_df.to_json(orient="records")),
    }


@app.get("/api/holdings")
def get_holdings(
    sector: Optional[str] = Query(None),
    broker: Optional[str] = Query(None),
    sort: str = Query("pnl_pct"),
):
    holdings = read_holdings()
    summary = build_summary(holdings)

    if sector:
        if sector == "ETF / No Sector":
            summary = summary[summary["sector"].isna()]
        else:
            summary = summary[summary["sector"] == sector]

    if broker:
        allowed = holdings[holdings["broker"] == broker.lower()]["symbol"].unique()
        summary = summary[summary["symbol"].isin(allowed)]

    sort_map = {
        "pnl_pct": ("total_unrealized_pnl_pct", False),
        "current_value": ("total_current_value", False),
        "pnl_abs": ("total_unrealized_pnl", False),
        "symbol": ("symbol", True),
    }
    col, asc = sort_map.get(sort, ("total_unrealized_pnl_pct", False))
    summary = summary.sort_values(col, ascending=asc)

    return json.loads(summary.to_json(orient="records"))


@app.get("/api/holdings/{symbol}")
def get_holding_detail(symbol: str):
    holdings = read_holdings()
    rows = holdings[holdings["symbol"] == symbol.upper()].copy()

    if rows.empty:
        return {"brokers": []}

    return {"brokers": json.loads(rows.to_json(orient="records"))}
