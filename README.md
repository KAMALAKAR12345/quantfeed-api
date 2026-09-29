# QuantFeed: Algorithmic Trading API & BI Dashboard

## 📌 Project Overview
QuantFeed is a full-stack financial data pipeline designed for algorithmic trading analysis. It features a custom Python/FastAPI backend that fetches live and historical market data, computes technical indicators (SMA, RSI) on the fly, and streams structured JSON to a Power BI frontend. The dashboard utilizes custom DAX models to generate automated BUY/SELL/HOLD signals based on momentum and trend-following strategies.

## 🛠️ Tech Stack
* **Backend:** Python, FastAPI, Uvicorn
* **Data Processing:** Pandas, yfinance
* **Frontend/BI:** Power BI, Power Query, DAX
* **Architecture:** RESTful API, JSON Webhooks

## 📊 Dashboard & Quantitative Logic
The Power BI interface ingests historical timeseries data directly from the local API endpoint. It features:
1. **Trend Analysis:** Dual-line chart mapping daily closing prices against a 20-day Simple Moving Average (SMA).
2. **Momentum Oscillator:** 14-period Relative Strength Index (RSI) with static overbought (70) and oversold (30) reference bands.
3. **Automated Trading Engine:** Custom DAX measures that evaluate conditions across multiple columns to flag high-probability setups:
   * **STRONG BUY:** Price > 20 SMA & RSI < 30
   * **STRONG SELL:** Price < 20 SMA & RSI > 70

## 🚀 API Endpoints
The FastAPI application serves the following routes:

* `GET /api/v1/quote/{ticker}`
  Fetches the latest price snapshot, day highs/lows, volume, and percentage change.
* `GET /api/v1/indicators/{ticker}`
  Computes and returns the latest 20-SMA, 14-RSI, and current trend status (BULLISH/BEARISH).
* `GET /api/v1/history/{ticker}`
  Returns a structured JSON array of historical prices and computed indicators, optimized for direct Power BI ingestion.
* `POST /api/v1/webhook/signal`
  Ingests automated signals from external platforms (e.g., TradingView), validates risk limits, and prepares execution payloads.

## 💻 Local Setup & Execution
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/quantfeed-api.git](https://github.com/yourusername/quantfeed-api.git)
   cd quantfeed-api