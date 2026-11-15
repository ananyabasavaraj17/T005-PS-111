
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.stretch_goal import StretchGoal


FLEXIBLE_SUCCESS_THRESHOLD = Decimal("0.20")


def close_campaign(
    db: Session,
    campaign_id: int,
    current_time: datetime,
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Only live campaigns can be closed.")

    if current_time < campaign.deadline:
        raise ValueError("Campaign deadline has not been reached.")

    # Count only active pledges.
    pledged_total = (
        db.query(func.coalesce(func.sum(Pledge.amount), 0))
        .filter(
            Pledge.campaign_id == campaign_id,
            Pledge.status == "PLEDGED",
        )
        .scalar()
    )

    pledged_total = Decimal(str(pledged_total))
    goal = Decimal(str(campaign.goal_amount))

    funding_model = campaign.funding_model.upper()

    if funding_model == "ALL_OR_NOTHING":
        successful = pledged_total >= goal

    elif funding_model == "FLEXIBLE":
        successful = (
            pledged_total >= goal * FLEXIBLE_SUCCESS_THRESHOLD
        )

    else:
        raise ValueError("Invalid campaign funding model.")

    # Freeze final stretch-goal states at closing.
    goals = (
        db.query(StretchGoal)
        .filter(StretchGoal.campaign_id == campaign_id)
        .order_by(
            StretchGoal.target_amount.asc(),
            StretchGoal.id.asc(),
        )
        .all()
    )

    for stretch_goal in goals:
        stretch_goal.is_unlocked = (
            pledged_total >= stretch_goal.target_amount
        )

    campaign.status = "FUNDED" if successful else "FAILED"

    db.commit()
    db.refresh(campaign)

    return {
        "campaign_id": campaign.id,
        "funding_model": funding_model,
        "goal_amount": goal,
        "pledged_total": pledged_total,
        "status": campaign.status,
        "stretch_goals": [
            {
                "id": goal.id,
                "title": goal.title,
                "unlocked": goal.is_unlocked,
            }
            for goal in goals
        ],
    }
