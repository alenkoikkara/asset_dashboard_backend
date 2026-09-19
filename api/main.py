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


def fmt_dt(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%d %b %y, %I:%M %p")

# ── Pipeline state ────────────────────────────────────────────────────────────

_state = {
    "is_running": False,
    "last_run_at": None,
    "last_run_status": None,  # "success" | "error"
    "last_run_error": None,
}

_scheduler: AsyncIOScheduler | None = None


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
    global _scheduler
    _scheduler = AsyncIOScheduler()
    IST = "Asia/Kolkata"

    _scheduler.add_job(_run_pipeline, CronTrigger(hour=9,  minute=18, day_of_week="mon-fri", timezone=IST))
    _scheduler.add_job(_run_pipeline, CronTrigger(hour=12, minute=0,  day_of_week="mon-fri", timezone=IST))
    _scheduler.add_job(_run_pipeline, CronTrigger(hour=15, minute=35, day_of_week="mon-fri", timezone=IST))

    _scheduler.start()
    yield
    _scheduler.shutdown()


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
    next_run_at = None
    if _scheduler:
        upcoming = [
            job.next_run_time for job in _scheduler.get_jobs()
            if job.next_run_time is not None
        ]
        if upcoming:
            next_run_at = fmt_dt(min(upcoming))
    return {
        **_state,
        "last_run_at": fmt_dt(_state["last_run_at"]),
        "next_run_at": next_run_at,
    }


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
    last_updated = holdings["_ts"].max().to_pydatetime().isoformat()

    broker_alloc = (
        holdings.groupby("broker")
        .agg(
            invested=("invested_value", "sum"),
            current_value=("current_value", "sum"),
            pnl=("unrealized_pnl", "sum"),
        )
        .reset_index()
    )
    broker_alloc["pnl_pct"] = (broker_alloc["pnl"] / broker_alloc["invested"] * 100).round(4)
    broker_alloc = broker_alloc.round(2)

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
        "broker_allocation": json.loads(broker_alloc.to_json(orient="records")),
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



@app.get("/api/indices")
def get_indices():
    import yfinance as yf

    INDICES = [
        {
            "key": "nifty50",
            "name": "Nifty 50",
            "ticker": "^NSEI",
            "hours": "9:15 AM – 3:30 PM IST",
            "extended": False,
            "note": None,
        },
        {
            "key": "banknifty",
            "name": "Bank Nifty",
            "ticker": "^NSEBANK",
            "hours": "9:15 AM – 3:30 PM IST",
            "extended": False,
            "note": None,
        },
        {
            "key": "giftnifty",
            "name": "Gift Nifty",
            "ticker": "^NSEI",
            "hours": "6:00 AM – 11:30 PM IST",
            "extended": True,
            # Gift Nifty (NSE IFSC futures) has no Yahoo Finance ticker;
            # Nifty 50 spot is shown as the nearest reference.
            "note": "NSE IFSC · Nifty spot proxy",
        },
    ]

    result = []
    for idx in INDICES:
        try:
            fi = yf.Ticker(idx["ticker"]).fast_info
            price = round(float(fi.last_price), 2)
            prev = round(float(fi.previous_close), 2)
            chg = round(price - prev, 2)
            chg_pct = round((chg / prev) * 100, 2) if prev else 0.0
        except Exception:
            price = prev = chg = chg_pct = None

        result.append(
            {
                "key": idx["key"],
                "name": idx["name"],
                "hours": idx["hours"],
                "extended": idx["extended"],
                "note": idx["note"],
                "price": price,
                "change": chg,
                "change_pct": chg_pct,
                "prev_close": prev,
            }
        )

    return result


@app.get("/api/benchmark")
def get_benchmark(period: str = Query("1y")):
    import yfinance as yf
    from datetime import timedelta

    end_dt = datetime.now()
    if period == "1m":
        start_dt = end_dt - timedelta(days=31)
    elif period == "1y":
        start_dt = end_dt - timedelta(days=366)
    else:  # all — 5 years
        start_dt = end_dt - timedelta(days=365 * 5)

    holdings = read_holdings()
    holding_info = (
        holdings.groupby("symbol")
        .agg(quantity=("quantity", "sum"))
        .reset_index()
    )

    yf_symbols = [f"{s}.NS" for s in holding_info["symbol"].tolist()]
    all_symbols = yf_symbols + ["^NSEI"]

    empty_result = {
        "series": [],
        "summary": {
            "portfolio_return": 0,
            "nifty50_return": 0,
            "start_date": None,
            "end_date": None,
        },
    }

    try:
        raw = yf.download(
            all_symbols,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        prices = raw["Close"] if "Close" in raw.columns else raw
    except Exception:
        return empty_result

    if prices.empty:
        return empty_result

    if isinstance(prices, pd.Series):
        prices = prices.to_frame()

    prices = prices.ffill()

    portfolio_value = pd.Series(0.0, index=prices.index)
    for _, row in holding_info.iterrows():
        yf_sym = f"{row['symbol']}.NS"
        if yf_sym in prices.columns:
            portfolio_value += prices[yf_sym] * row["quantity"]

    nifty = prices.get("^NSEI")
    if nifty is None:
        return empty_result

    # Keep only rows where portfolio has value
    mask = portfolio_value > 0
    portfolio_value = portfolio_value[mask]
    nifty = nifty[mask]

    if portfolio_value.empty:
        return empty_result

    portfolio_ret = ((portfolio_value / portfolio_value.iloc[0]) - 1) * 100
    nifty_ret = ((nifty / nifty.iloc[0]) - 1) * 100

    combined = pd.DataFrame(
        {"portfolio": portfolio_ret.round(2), "nifty50": nifty_ret.round(2)}
    ).dropna()

    # Resample to weekly for all-time to reduce payload size
    if period == "all" and len(combined) > 260:
        combined = combined.resample("W").last().dropna()

    combined.index = pd.DatetimeIndex(combined.index).strftime("%Y-%m-%d")

    series = [
        {
            "date": date,
            "portfolio": float(row["portfolio"]),
            "nifty50": float(row["nifty50"]),
        }
        for date, row in combined.iterrows()
    ]

    return {
        "series": series,
        "summary": {
            "portfolio_return": round(float(combined["portfolio"].iloc[-1]), 2) if series else 0,
            "nifty50_return": round(float(combined["nifty50"].iloc[-1]), 2) if series else 0,
            "start_date": series[0]["date"] if series else None,
            "end_date": series[-1]["date"] if series else None,
        },
    }
