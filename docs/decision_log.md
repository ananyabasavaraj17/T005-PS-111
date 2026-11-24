# Decision Log

| Decision | Rationale | Affected Files |
|----------|-----------|----------------|
| Use **SQLite** as the persistence layer | Simplicity for a self‑contained capstone; no external DB setup required. | `app/database.py`, `app/models/*` |
| Store monetary values as **Decimal** | Avoid floating‑point rounding errors in financial calculations. | All service files handling amounts (`pledge_service.py`, `settlement_service.py`, `refund_service.py`, etc.) |
| Keep **CSV ingestion** as separate services per entity (reward tier, stretch goal) | Improves single‑responsibility; easier to test and extend. | `app/services/csv_ingestion_service.py`, `csv_ingestion_campaign_service.py`, `csv_ingestion_stretch_goal_service.py` |
| Implement a **command‑file processor** rather than a full CLI parser | Provides a lightweight batch execution mechanism aligned with specification. | `app/services/command_file_processor.py`, `app/cli.py` |
| Enforce **required‑column validation** in CSV ingestion | Guarantees data integrity before creating DB records. | `app/services/csv_ingestion_service.py` (`validate_headers`) |
| Model **campaign status** as a string column with default `DRAFT` | Matches specification; simple enumeration without separate table. | `app/models/campaign.py` |
| Include **early‑bird** fields in `RewardTier` model | Supports discounted early pledges as required by business rules. | `app/models/reward_tier.py` |
| Use **service layer** for business logic, keeping models thin | Facilitates unit testing and isolates DB interactions. | All `app/services/*.py` |
| Keep **test suite** in `tests/` with pytest fixtures | Standard Python testing practice; ensures repeatable CI runs. | `tests/*.py` |

These decisions were made based on the existing codebase and the official project specification, without introducing new dependencies or altering the established architecture.
