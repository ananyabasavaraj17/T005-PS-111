
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.campaign import Campaign


MINIMUM_GOAL = Decimal("50000.00")
MINIMUM_DURATION = 15
MAXIMUM_DURATION = 60


def create_campaign(
    db: Session,
    title: str,
    description: str,
    goal_amount: Decimal,
    funding_model: str,
    start_date: datetime,
    deadline: datetime,
    creator_id: str = None,
):
    # Validate funding goal
    goal_amount = Decimal(str(goal_amount))

    if goal_amount < MINIMUM_GOAL:
        raise ValueError("Minimum campaign goal is Rs. 50,000.")

    # Validate funding model
    funding_model = funding_model.upper()

    if funding_model not in ("ALL_OR_NOTHING", "FLEXIBLE"):
        raise ValueError("Invalid funding model.")

    # Validate campaign duration
    duration = (deadline - start_date).total_seconds() / 86400

    if deadline <= start_date:
        raise ValueError("Deadline must be after the start date.")

    if not MINIMUM_DURATION <= duration <= MAXIMUM_DURATION:
        raise ValueError("Campaign duration must be 15 to 60 days.")

    # Validate creator
    if not creator_id:
        raise ValueError("Creator ID is required.")

    # Create campaign
    campaign = Campaign(
        title=title,
        description=description,
        goal_amount=goal_amount,
        funding_model=funding_model,
        start_date=start_date,
        deadline=deadline,
        status="DRAFT",
        creator_id=creator_id,
    )

    # Save campaign
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


def launch_campaign(
    db: Session,
    campaign_id: str | int,
    launch_time: datetime | None = None,
) -> Campaign:
    """Activate a campaign from DRAFT to LIVE (BR-04)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "DRAFT":
        raise ValueError(
            f"Campaign cannot be launched from status '{campaign.status}'. Only DRAFT campaigns can be launched."
        )

    campaign.status = "LIVE"
    if launch_time is not None:
        campaign.start_date = launch_time

    db.commit()
    db.refresh(campaign)
    return campaign


def record_failed_delivery(
    db: Session,
    campaign_id: str | int,
    current_time: datetime | None = None,
) -> Campaign:
    """Record a failed delivery event for a campaign (BR-33)."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found.")

    campaign.has_failed_delivery = True
    db.commit()
    db.refresh(campaign)
    return campaign

