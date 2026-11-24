# Crowdfunding Engine (T005 – PS-111)

## Project Overview

A backend‑only crowdfunding platform that supports:
- Campaign lifecycle management (draft, live, funded, failed, closed)
- Pledge handling with early‑bird discounts and quantity limits
- Reward tiers and stretch goals with automatic unlocking
- Refunds, chargebacks and settlement processing
- CSV ingestion for bulk creation of rewards and stretch goals
- Command‑file processor for declarative batch operations

The implementation uses **Python 3.10+**, **SQLite**, **SQLAlchemy**, **Decimal** for monetary values, and **pytest** for the test suite.

## Prerequisites

- Python 3.10 or newer
- `virtualenv` (optional but recommended)

## Setup

```bash
# Clone the repository (if not already extracted)
# cd into the extracted folder
cd C:\Users\User\Documents\crowdfunding-engine

# Create a virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Initialise the Database

```bash
python - <<PY
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
PY
```

This creates a `crowdfunding.db` SQLite file in the project root.

## Usage

The entry point is the CLI located at `app/cli.py`.

```bash
python -m app.cli <command_file_path>
```

The command file contains one operation per line, e.g.:
```
launch_campaign 1
add_pledge 1 user123 50.00 reward_tier_2
process_refund 42
```

See the `data/` folder for sample CSV files used by the ingestion services.

## Running the Test Suite

```bash
pytest -q
```
All 72 tests should pass.

## Documentation

- Design document: `docs/design_document.md`
- Decision log: `docs/decision_log.md`

## License

MIT License (see LICENSE file if present).