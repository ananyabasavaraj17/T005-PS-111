
import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

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

from app.services.waitlist_service import (
    join_waitlist,
    allocate_next_backer,
)

from app.services.stretch_goal_service import evaluate_stretch_goals
from app.services.chargeback_service import process_chargeback

from app.services.csv_ingestion_service import ingest_reward_tiers_from_csv
from app.services.csv_ingestion_campaign_service import ingest_campaigns_from_csv
from app.services.csv_ingestion_stretch_goal_service import (
    ingest_stretch_goals_from_csv,
)


# Commands supported by the command-file processor
_COMMAND_MAP: dict[str, Callable[..., Any]] = {
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


def _parse_line(line: str) -> tuple[str, dict[str, Any]]:
    """Parse one command line into a command name and JSON payload.

    Format:
        COMMAND_NAME {"key": "value"}

    Commands without arguments may omit the JSON payload.
    """
    parts = line.strip().split(maxsplit=1)

    if not parts:
        raise ValueError("Empty command line.")

    command = parts[0].upper()
    payload: dict[str, Any] = {}

    if len(parts) == 2:
        try:
            payload = json.loads(parts[1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON payload for command '{command}': {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"JSON payload for command '{command}' must be an object."
            )

    return command, payload


def _serialize_result(result: Any) -> Any:
    """Convert service results into values suitable for command output."""

    if result is None:
        return None

    # SQLAlchemy model instance
    if hasattr(result, "__table__"):
        return {
            column.name: getattr(result, column.name)
            for column in result.__table__.columns
        }

    # List or tuple of results
    if isinstance(result, (list, tuple)):
        return [_serialize_result(item) for item in result]

    # Dictionary result
    if isinstance(result, dict):
        return {
            key: _serialize_result(value)
            for key, value in result.items()
        }

    # Other result types
    return result


def process_command_file(
    db: Session,
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Execute commands from a text file.

    Blank lines and lines beginning with '#' are ignored.

    Each command is written as:
        COMMAND_NAME {"argument": "value"}

    The JSON object is passed as keyword arguments to the mapped
    service function. The database session is passed as the first
    positional argument.

    Returns a list containing the command name and its result.
    """
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Command file not found: {path}")

    results: list[dict[str, Any]] = []

    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                command, payload = _parse_line(line)

                if command not in _COMMAND_MAP:
                    raise ValueError(f"Unknown command '{command}'.")

                service_function = _COMMAND_MAP[command]

                # Execute the service exactly once.
                result = (
                    service_function(db, **payload)
                    if payload
                    else service_function(db)
                )

                results.append(
                    {
                        "command": command,
                        "result": _serialize_result(result),
                    }
                )

            except Exception as exc:
                raise RuntimeError(
                    f"Error processing command at line {line_number} "
                    f"in '{path}': {exc}"
                ) from exc

    return results
