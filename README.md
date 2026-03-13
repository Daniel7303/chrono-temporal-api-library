# ⏳ Chrono Temporal API Framework

A powerful backend framework that gives any data entity **time-travel superpowers**. Query what your data looked like at any point in history, track full change histories, and diff any two points in time — all through a clean REST API.

---

## 🚀 The Problem

Most databases only store the **current state** of data. When something changes, the old version is gone forever. This causes real pain:

- *"What was this user's subscription plan when they made this purchase?"* — you can't know
- Audit trails and compliance become a nightmare
- Debugging production issues that depended on state that no longer exists

Developers hack around this with `created_at`/`updated_at` columns and manual audit tables — all bespoke, inconsistent, and painful to query.

---

## ✅ The Solution

Chrono gives every entity a **time dimension**. Store any entity with a validity period and query it across time with zero extra effort.

---

## ✨ Features

- 🕐 **Time-travel queries** — Get the exact state of any entity at any point in history
- 📜 **Full history** — See the complete timeline of changes for any entity
- 🔍 **Diff engine** — Compare any two points in time and see exactly what changed
- 📦 **Generic** — Works with any entity type (users, orders, products, contracts — anything)
- ⚡ **Async** — Built with FastAPI and async SQLAlchemy for high performance
- 📖 **Auto docs** — Interactive Swagger UI out of the box

---

## 🛠 Tech Stack

- **FastAPI** — Modern async Python web framework
- **PostgreSQL** — Battle-tested relational database
- **SQLAlchemy 2.0** — Async ORM
- **Alembic** — Database migrations
- **Pydantic** — Data validation
- **asyncpg** — Async PostgreSQL driver

---

## 📦 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 15+

### Installation

```bash
# Clone the repo
git clone https://github.com/Daniel7303/chrono-temporal-api-framework.git
cd chrono-temporal-api-framework

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configure environment

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/temporal_api
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:yourpassword@localhost:5432/temporal_api
APP_NAME=Chrono Temporal API Framework
APP_VERSION=0.1.0
DEBUG=True
```

### Run the server

```bash
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for the interactive API docs.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/temporal/` | Create a temporal record |
| `GET` | `/api/v1/temporal/{id}` | Get a record by ID |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/current` | Get current state |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/history` | Get full history |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/as-of` | Time-travel query |
| `GET` | `/api/v1/temporal/entity/{type}/{id}/diff` | Diff two points in time |
| `PATCH` | `/api/v1/temporal/{id}/close` | Close a record |

---

## 💡 Example Usage

### 1. Create a user record

```bash
POST /api/v1/temporal/
{
  "entity_type": "user",
  "entity_id": "user_001",
  "valid_from": "2024-01-01T00:00:00Z",
  "data": {
    "name": "Daniel",
    "plan": "free",
    "email": "daniel@example.com"
  }
}
```

### 2. Record an upgrade

```bash
POST /api/v1/temporal/
{
  "entity_type": "user",
  "entity_id": "user_001",
  "valid_from": "2025-06-01T00:00:00Z",
  "data": {
    "name": "Daniel",
    "plan": "pro",
    "email": "daniel@example.com"
  }
}
```

### 3. Time-travel — what plan was Daniel on in March 2024?

```bash
GET /api/v1/temporal/entity/user/user_001/as-of?as_of=2024-03-01T00:00:00Z

# Returns: { "plan": "free", ... }
```

### 4. Diff — what changed between 2024 and 2025?

```bash
GET /api/v1/temporal/entity/user/user_001/diff?from_dt=2024-03-01T00:00:00Z&to_dt=2025-07-01T00:00:00Z

# Returns:
{
  "changed": {
    "plan": { "from": "free", "to": "pro" }
  },
  "unchanged": ["name", "email"],
  "has_changes": true
}
```

---

## 🗺 Roadmap

- [ ] API key authentication
- [ ] Demo app (subscription management system)
- [ ] Timeline summary endpoint
- [ ] Docker support
- [ ] PyPI package

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

---

## 📄 License

MIT License — free to use, modify, and distribute.
