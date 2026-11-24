from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.models.campaign import Campaign


def _parse_decimal(value: str) -> Decimal:
    return Decimal(value.strip().replace('₹', '').replace('$', ''))


def ingest_campaigns_from_csv(
    db: Session,
    csv_path: str | Path,
    *,
    batch_size: int = 100,
) -> List[Campaign]:
    """Ingest campaign definitions from a CSV file.

    Expected columns (header required):
        title, description, goal_amount, funding_model, start_date, deadline, creator_id, status
    Dates should be ISO format (e.g. ``2026-01-01T12:00:00``).
    ``status`` defaults to ``DRAFT`` if omitted.
    Returns the list of created ``Campaign`` objects.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    created: List[Campaign] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"title", "description", "goal_amount", "funding_model", "start_date", "deadline", "creator_id"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = ", ".join(sorted(required - set(reader.fieldnames or [])))
            raise ValueError(f"CSV missing required columns: {missing}")
        batch: List[Campaign] = []
        for row in reader:
            campaign = Campaign(
                title=row["title"].strip(),
                description=row["description"].strip(),
                goal_amount=_parse_decimal(row["goal_amount"]),
                funding_model=row["funding_model"].strip().upper(),
                start_date=datetime.fromisoformat(row["start_date"].strip()),
                deadline=datetime.fromisoformat(row["deadline"].strip()),
                status=row.get("status", "DRAFT").strip().upper(),
                creator_id=row["creator_id"].strip(),
            )
            batch.append(campaign)
            if len(batch) >= batch_size:
                db.add_all(batch)
                db.commit()
                created.extend(batch)
                batch.clear()
        if batch:
            db.add_all(batch)
            db.commit()
            created.extend(batch)
    return created
