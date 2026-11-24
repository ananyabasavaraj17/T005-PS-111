from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.models.stretch_goal import StretchGoal


def _parse_decimal(value: str) -> Decimal:
    return Decimal(value.strip().replace('₹', '').replace('$', ''))


def ingest_stretch_goals_from_csv(
    db: Session,
    campaign_id: int,
    csv_path: str | Path,
    *,
    batch_size: int = 100,
) -> List[StretchGoal]:
    """Ingest stretch‑goal definitions for a specific campaign from CSV.

    Expected columns (header required):
        title, description, target_amount
    ``target_amount`` is parsed as ``Decimal``.
    Returns the list of created ``StretchGoal`` objects.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    created: List[StretchGoal] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"title", "description", "target_amount"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = ", ".join(sorted(required - set(reader.fieldnames or [])))
            raise ValueError(f"CSV missing required columns: {missing}")
        batch: List[StretchGoal] = []
        for row in reader:
            goal = StretchGoal(
                campaign_id=campaign_id,
                title=row["title"].strip(),
                description=row["description"].strip(),
                target_amount=_parse_decimal(row["target_amount"]),
                is_unlocked=False,
            )
            batch.append(goal)
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
