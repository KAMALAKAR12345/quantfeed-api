from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import yfinance as yf
import pandas as pd

app = FastAPI(
    title="QuantFeed API",
    description="Algorithmic trading & financial data pipeline service",
    version="1.0.0"
)

# ----------------- Data Models -----------------
class TradeSignal(BaseModel):
    ticker: str
    action: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    quantity: int

# ----------------- Endpoints -----------------

@app.get("/")
def root():
    return {"message": "QuantFeed API is operational", "status": "online"}


@app.get("/api/v1/quote/{ticker}")
def get_live_quote(ticker: str):
    """
    Fetches latest price snapshot for an NSE stock.
    Example: RELIANCE.NS, INFY.NS, TATAMOTORS.NS
    """
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period="1d")
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found on exchange.")
            
        latest_close = float(hist["Close"].iloc[-1])
        day_open = float(hist["Open"].iloc[-1])
        day_high = float(hist["High"].iloc[-1])
        day_low = float(hist["Low"].iloc[-1])
        volume = int(hist["Volume"].iloc[-1])
        
        pct_change = round(((latest_close - day_open) / day_open) * 100, 2)

        return {
            "symbol": ticker.upper(),
            "latest_price": round(latest_close, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": volume,
            "change_percent": pct_change
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/indicators/{ticker}")
def get_technical_indicators(ticker: str, period: str = Query("3mo", description="Historical duration, e.g., 1mo, 3mo, 6mo, 1y")):
    """
    Computes 20-day Simple Moving Average (SMA) and 14-day Relative Strength Index (RSI).
    """
    try:
        stock = yf.Ticker(ticker.upper())
        df = stock.history(period=period)
        
        if len(df) < 20:
            raise HTTPException(status_code=400, detail="Insufficient price history for technical calculations.")

        # 20-period Simple Moving Average
        df["SMA_20"] = df["Close"].rolling(window=20).mean()

        # 14-period RSI calculation
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI_14"] = 100 - (100 / (1 + rs))

        latest_price = round(float(df["Close"].iloc[-1]), 2)
        latest_sma = round(float(df["SMA_20"].iloc[-1]), 2)
        latest_rsi = round(float(df["RSI_14"].iloc[-1]), 2)

        trend = "BULLISH" if latest_price > latest_sma else "BEARISH"

        return {
            "symbol": ticker.upper(),
            "latest_price": latest_price,
            "sma_20": latest_sma,
            "rsi_14": latest_rsi,
            "indicator_trend": trend
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/history/{ticker}")
def get_historical_timeseries(ticker: str, period: str = Query("3mo")):
    """
    Returns structured timeseries data optimized for Power BI ingestion.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        df = stock.history(period=period)
        
        if df.empty or len(df) < 20:
            raise HTTPException(status_code=400, detail="Insufficient history.")

        # 20-period Simple Moving Average
        df["SMA_20"] = df["Close"].rolling(window=20).mean()
        
        # 14-period RSI calculation
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI_14"] = 100 - (100 / (1 + rs))

        # Format dataframe for JSON export
        df = df.reset_index()
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        
        # Drop rows with NaN values (the first 19 days before SMA calculates) and convert to dict
        records = df[["Date", "Open", "High", "Low", "Close", "Volume", "SMA_20", "RSI_14"]].dropna().to_dict(orient="records")
        return records
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/webhook/signal")
def receive_trade_signal(signal: TradeSignal):
    """
    Ingests automated signals from TradingView or custom scrapers,
    validates risk, and prepares execution payload.
    """
    per_share_risk = abs(signal.entry_price - signal.stop_loss)
    total_capital_at_risk = round(per_share_risk * signal.quantity, 2)
    position_size = round(signal.entry_price * signal.quantity, 2)

    return {
        "status": "PROCESSED",
        "order": {
            "ticker": signal.ticker.upper(),
            "action": signal.action.upper(),
            "quantity": signal.quantity,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "total_order_value": position_size,
            "max_loss_potential": total_capital_at_risk
        }
    }