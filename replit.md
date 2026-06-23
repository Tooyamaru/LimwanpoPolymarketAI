# Polymarket Quant Bot

A production-grade quantitative trading infrastructure for Polymarket prediction markets. Integrates price feeds from Binance and Chainlink to analyze "Up-or-Down" markets for BTC, ETH, SOL, and XRP.

## Architecture

- **Backend**: FastAPI + Uvicorn (async Python 3.12)
- **Database**: PostgreSQL (Replit managed)
- **Cache**: Redis (in-process via redis-server)
- **Background tasks**: Collector, Scanner, Universe Sync, Price Refresh, Signal Engine, Opportunity Engine

## Running the App

The `Start application` workflow starts Redis and then launches the FastAPI backend on port 5000.

## User Preferences

- Use Python 3.12
- Structured JSON logging via structlog
- Async SQLAlchemy with asyncpg driver
- Keep Docker/docker-compose files but don't rely on them for running in Replit
