import json
from pathlib import Path
from typing import Callable, Dict, List

from sqlalchemy.orm import Session

# Import service functions that can be invoked via command file
from app.services.campaign_service import create_campaign
from app.services.pledge_service import create_pledge
from app.services.campaign_extension_service import extend_campaign
from app.services.campaign_closing_service import close_campaign
from app.services.payment_collection_service import (
    record_payment_attempt,
    collect_campaign_pledges,
    retry_failed_payments,
    process_due_retries,
)
from app.services.waitlist_service import join_waitlist, allocate_next_backer
from app.services.stretch_goal_service import evaluate_stretch_goals
from app.services.chargeback_service import process_chargeback
from app.services.csv_ingestion_service import ingest_reward_tiers_from_csv
from app.services.csv_ingestion_campaign_service import ingest_campaigns_from_csv
from app.services.csv_ingestion_stretch_goal_service import ingest_stretch_goals_from_csv

# Mapping from command name to callable
_COMMAND_MAP: Dict[str, Callable] = {
    "CREATE_CAMPAIGN": create_campaign,
    "CREATE_PLEDGE": create_pledge,
    "EXTEND_CAMPAIGN": extend_campaign,
    "CLOSE_CAMPAIGN": close_campaign,
    "RECORD_PAYMENT": record_payment_attempt,
    "COLLECT_PLEDGES": collect_campaign_pledges,
    "RETRY_PAYMENTS": retry_failed_payments,
    "PROCESS_RETRIES": process_due_retries,
    "JOIN_WAITLIST": join_waitlist,
    "ALLOCATE_NEXT_BACKER": allocate_next_backer,
    "EVALUATE_STRETCH_GOALS": evaluate_stretch_goals,
    "PROCESS_CHARGEBACK": process_chargeback,
    "INGEST_REWARD_TIERS": ingest_reward_tiers_from_csv,
    "INGEST_CAMPAIGNS": ingest_campaigns_from_csv,
    "INGEST_STRETCH_GOALS": ingest_stretch_goals_from_csv,
}


def _parse_line(line: str) -> tuple[str, dict]:
    """Parse a single line of the command file.

    Expected format::
        COMMAND_NAME {json_payload}
    The JSON payload may be omitted for commands that take no arguments.
    """
    parts = line.strip().split(maxsplit=1)
    if not parts:
        raise ValueError("Empty command line.")
    command = parts[0].upper()
    payload = {}
    if len(parts) == 2:
        try:
            payload = json.loads(parts[1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload for {command}: {exc}")
    return command, payload


def process_command_file(db: Session, file_path: str | Path) -> List[dict]:
    """Execute a series of commands defined in a plain‑text file.

    The file may contain comment lines starting with ``#`` and blank lines.
    Each non‑comment line is parsed as ``COMMAND_NAME <json>`` where the JSON
    argument dictionary is passed verbatim to the mapped service function.
    The function returns a list of result dictionaries (or ``None`` where the
    service does not return a value).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Command file not found: {path}")

    results: List[dict] = []
    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            command, payload = _parse_line(line)
            if command not in _COMMAND_MAP:
                raise ValueError(f"Unknown command '{command}' in file {path}")
            func = _COMMAND_MAP[command]
            # All service functions expect the DB session as the first argument
            try:
                result = func(db, **payload) if payload else func(db)
            except TypeError:
                # Some functions have a different signature (e.g., ingest functions)
                result = func(db, **payload)
            # Normalise result to a dict for easy downstream consumption
            if result is None:
                results.append({"command": command, "result": None})
            else:
                # If the result is a SQLAlchemy model instance, convert to dict
                if hasattr(result, "__dict__"):
                    result_dict = {
                        k: v for k, v in vars(result).items() if not k.startswith("_")
                    }
                else:
                    result_dict = result
                results.append({"command": command, "result": result_dict})
    return results
