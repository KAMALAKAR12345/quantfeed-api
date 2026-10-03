import logging
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Header, Depends, status
from pydantic import BaseModel, Field
import yfinance as yf
import pandas as pd
import numpy as np

# Configure internal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quantfeed")

app = FastAPI(
    title="QuantFeed API",
    description="Algorithmic trading & financial data pipeline service",
    version="1.0.0"
)

# ----------------- Security & Auth -----------------
# In production, pull this from os.environ or a .env file
WEBHOOK_SECRET = "quantfeed_secure_secret_token_123"

def verify_webhook_token(x_webhook_secret: str = Header(...)):
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret"
        )
    return True

# ----------------- Data Models -----------------
class TradeSignal(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=12, examples=["RELIANCE.NS"])
    action: Literal["BUY", "SELL"]
    entry_price: float = Field(..., gt=0, description="Price must be strictly positive")
    stop_loss: float = Field(..., gt=0, description="Stop loss must be strictly positive")
    quantity: int = Field(..., gt=0, description="Quantity must be at least 1")

AllowedPeriods = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]

# ----------------- Endpoints -----------------

@app.get("/")
def root():
    return {"message": "QuantFeed API is operational", "status": "online"}


@app.get("/api/v1/quote/{ticker}")
def get_live_quote(ticker: str):
    try:
        clean_ticker = ticker.strip().upper()
        stock = yf.Ticker(clean_ticker)
        hist = stock.history(period="1d")

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Ticker '{clean_ticker}' not found.")

        latest_close = float(hist["Close"].iloc[-1])
        day_open = float(hist["Open"].iloc[-1])
        day_high = float(hist["High"].iloc[-1])
        day_low = float(hist["Low"].iloc[-1])
        volume = int(hist["Volume"].iloc[-1])

        # Prevent division by zero
        pct_change = round(((latest_close - day_open) / day_open) * 100, 2) if day_open > 0 else 0.0

        return {
            "symbol": clean_ticker,
            "latest_price": round(latest_close, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": volume,
            "change_percent": pct_change
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing market quote.")


@app.get("/api/v1/indicators/{ticker}")
def get_technical_indicators(
    ticker: str,
    period: AllowedPeriods = Query("3mo", description="Allowed: 1mo, 3mo, 6mo, 1y, 2y, 5y, max")
):
    try:
        clean_ticker = ticker.strip().upper()
        stock = yf.Ticker(clean_ticker)
        df = stock.history(period=period)

        if len(df) < 20:
            raise HTTPException(status_code=400, detail="Insufficient price history for technical calculations.")

        df["SMA_20"] = df["Close"].rolling(window=20).mean()

        # Safe RSI Calculation
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        rs = gain / loss.replace(0, np.nan)
        df["RSI_14"] = 100 - (100 / (1 + rs))
        df["RSI_14"] = df["RSI_14"].fillna(100)  # If loss was 0, RSI is 100

        latest_price = round(float(df["Close"].iloc[-1]), 2)
        latest_sma = round(float(df["SMA_20"].iloc[-1]), 2)
        latest_rsi = round(float(df["RSI_14"].iloc[-1]), 2)

        return {
            "symbol": clean_ticker,
            "latest_price": latest_price,
            "sma_20": latest_sma,
            "rsi_14": latest_rsi,
            "indicator_trend": "BULLISH" if latest_price > latest_sma else "BEARISH"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating indicators for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing technical indicators.")


@app.get("/api/v1/history/{ticker}")
def get_historical_timeseries(
    ticker: str,
    period: AllowedPeriods = Query("3mo", description="Historical duration")
):
    try:
        clean_ticker = ticker.strip().upper()
        stock = yf.Ticker(clean_ticker)
        df = stock.history(period=period)

        if df.empty or len(df) < 20:
            raise HTTPException(status_code=400, detail="Insufficient historical data.")

        df["SMA_20"] = df["Close"].rolling(window=20).mean()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["RSI_14"] = (100 - (100 / (1 + rs))).fillna(100)

        df = df.reset_index()
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        records = df[["Date", "Open", "High", "Low", "Close", "Volume", "SMA_20", "RSI_14"]].dropna().to_dict(orient="records")
        return records
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeseries for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error generating historical timeseries.")


@app.post("/api/v1/webhook/signal", dependencies=[Depends(verify_webhook_token)])
def receive_trade_signal(signal: TradeSignal):
    per_share_risk = abs(signal.entry_price - signal.stop_loss)
    total_capital_at_risk = round(per_share_risk * signal.quantity, 2)
    position_size = round(signal.entry_price * signal.quantity, 2)

    return {
        "status": "PROCESSED",
        "order": {
            "ticker": signal.ticker.upper(),
            "action": signal.action,
            "quantity": signal.quantity,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "total_order_value": position_size,
            "max_loss_potential": total_capital_at_risk
        }
    }