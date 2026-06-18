"""
Data collector package.

Collectors are responsible for ingesting raw market data from external sources
and persisting it to PostgreSQL while publishing normalised events to Redis.

Available collectors (Sprint 2+):
- BinanceSpotCollector    — Binance Spot WebSocket streams
- BinanceFuturesCollector — Binance USD-M Futures streams
- PolymarketCollector     — Polymarket CLOB WebSocket API
- ChainlinkCollector      — Chainlink on-chain price feeds
"""
