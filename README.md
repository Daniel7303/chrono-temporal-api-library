# ⏳ Chrono Temporal

[![PyPI version](https://badge.fury.io/py/chrono-temporal.svg)](https://pypi.org/project/chrono-temporal/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

**A Python library that adds time-travel queries to your PostgreSQL database.**

Query what your data looked like at any point in history, track full change histories, and diff any two points in time — with a simple, clean API that drops into any existing project.

```bash
pip install chrono-temporal
```

---

## 🚀 The Problem

Most databases only store the **current state** of data. When something changes, the old version is gone forever:

- *"What was this user's subscription plan when they filed a dispute?"* — you can't know
- Audit trails and compliance become a nightmare
- Debugging issues that depended on state that no longer exists

Developers hack around this with `created_at`/`updated_at` columns and manual audit tables — all bespoke, inconsistent, and painful to query.

---

## ✅ The Solution

Drop `chrono-temporal` into your existing PostgreSQL project and get time-travel queries instantly — no architectural changes required.

```python
from chrono_temporal import TemporalService

svc = TemporalService(session)

# What was this user's plan in March 2024?
records = await svc.get_at_point_in_time("user", "user_001", datetime(2024, 3, 1))

# What changed between January 2024 and July 2025?
diff = await svc.get_diff("user", "user_001", datetime(2024, 1, 1), datetime(2025, 7, 1))
print(diff["changed"])  # {"plan": {"from": "free", "to": "pro"}}
```

---

## ✨ Features

- 🕐 **Time-travel queries** — state of any entity at any point in history
- 📜 **Full history** — complete timeline of changes for any entity
- 🔍 **Diff engine** — exactly what changed between two points in time
- 📦 **Generic** — works with any entity (users, orders, products, contracts)
- ⚡ **Async-first** — built on async SQLAlchemy for high performance
- 🐘 **PostgreSQL** — leverages native JSON and timezone support
- 🔐 **REST API included** — full FastAPI server with API key auth and Swagger docs
- 🐳 **Docker ready** — run everything with one command

---

## 📦 Quick Start

### Install

```bash
pip install chrono-temporal
```

### Setup

```python
from chrono_temporal import get_engine, get_session, create_tables

engine = get_engine("postgresql+asyncpg://user:pass@localhost/mydb")
session_factory = get_session(engine)
await create_tables(engine)  # creates the temporal_records table
```

### Store a record

```python
from chrono_temporal import TemporalService, TemporalRecordCreate
from datetime import datetime, timezone

async with session_factory() as session:
    svc = TemporalService(session)

    await svc.create(TemporalRecordCreate(
        entity_type="user",
        entity_id="user_001",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        data={"name": "Daniel", "plan": "free", "email": "daniel@example.com"}
    ))
```

### Time-travel query

```python
# What was the state on March 1st 2024?
records = await svc.get_at_point_in_time(
    "user", "user_001",
    datetime(2024, 3, 1, tzinfo=timezone.utc)
)
print(records[0].data)  # {"name": "Daniel", "plan": "free"}
```

### Diff two points in time

```python
diff = await svc.get_diff(
    "user", "user_001",
    datetime(2024, 1, 1, tzinfo=timezone.utc),
    datetime(2025, 7, 1, tzinfo=timezone.utc),
)
print(diff["changed"])    # {"plan": {"from": "free", "to": "pro"}}
print(diff["unchanged"])  # ["name", "email"]
```

### Full history

```python
history = await svc.get_history("user", "user_001")
for record in history:
    print(f"{record.valid_from} → {record.valid_to}: {record.data}")
# 2024-01-01 → 2025-06-01: {"plan": "free"}
# 2025-06-01 → None:       {"plan": "pro"}
```

---

## 🛠 Tech Stack

- **Python 3.11+**
- **PostgreSQL 15+**
- **SQLAlchemy 2.0** — async ORM
- **asyncpg** — async PostgreSQL driver
- **Pydantic 2.0** — data validation
- **FastAPI** — REST API layer (optional)

---

## 🐳 Run the REST API with Docker

Want a ready-made REST API on top of the library? Clone this repo and run:

```bash
git clone https://github.com/Daniel7303/chrono-temporal-api-framework.git
cd chrono-temporal-api-framework
```

Create a `.env.docker` file:
```env
DATABASE_URL=postgresql+asyncpg://temporal_user:temporal_pass@db:5432/temporal_api
DATABASE_URL_SYNC=postgresql+psycopg2://temporal_user:temporal_pass@db:5432/temporal_api
APP_NAME=Chrono Temporal
APP_VERSION=0.1.0
DEBUG=True
```

Start everything:
```bash
docker-compose up --build
```

Visit `http://127.0.0.1:8000/docs` — interactive Swagger UI with all endpoints. ✅

---

## 🔌 REST API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/temporal/` | Create a temporal record |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/current` | Get current state |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/history` | Get full history |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/as-of` | Time-travel query |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/diff` | Diff two points in time |
| `PATCH` | `/api/v1/temporal/{id}/close` | Close a record |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/keys/` | Generate a new API key |
| `GET` | `/auth/keys/` | List all keys |
| `DELETE` | `/auth/keys/{id}` | Revoke a key |

### Demo — Subscription Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/demo/subscriptions/customers` | Create a customer |
| `PATCH` | `/demo/subscriptions/customers/{id}/plan` | Upgrade/downgrade plan |
| `GET` | `/demo/subscriptions/customers/{id}/as-of` | Plan at a point in time |
| `GET` | `/demo/subscriptions/customers/{id}/diff` | What changed between dates |

---

## 🗺 Roadmap

- [x] Core time-travel query library
- [x] Diff engine
- [x] Full history tracking
- [x] REST API with FastAPI
- [x] API key authentication
- [x] Subscription management demo
- [x] Docker support
- [x] PyPI package
- [ ] Django ORM support
- [ ] Timeline summary endpoint
- [ ] Hosted cloud version

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

---

## 📄 License

MIT — free to use, modify, and distribute.
