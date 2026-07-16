# Architecture Overview

## Sprint 1 — Infrastructure

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                           │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  PostgreSQL  │    │    Redis     │    │  FastAPI Backend  │  │
│  │   :5432      │◄───│   :6379      │◄───│     :8000        │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                                                  │              │
└──────────────────────────────────────────────────┼─────────────┘
                                                   │
                                              HTTP :8000
                                                   │
                                              Client / API
```

## Component Responsibilities

| Component  | Role                                              |
|------------|---------------------------------------------------|
| FastAPI    | REST API, lifespan management, health checks      |
| PostgreSQL | Persistent storage for market data and state      |
| Redis      | Cache, pub/sub bus for real-time data events      |
| Collectors | (Sprint 2) Ingest raw data from external sources  |

## Sprint Roadmap

| Sprint | Focus                                    |
|--------|------------------------------------------|
| 1      | Infrastructure, health API, connections  |
| 2      | Data collectors (Binance, Polymarket, Chainlink) |
| 3      | Models, normalisation, persistence layer |
| 4      | Analysis services                        |
