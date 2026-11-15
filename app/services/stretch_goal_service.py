
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.stretch_goal import StretchGoal


def evaluate_stretch_goals(db: Session, campaign_id: int):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Stretch goals can only be updated while campaign is live.")

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

    # Evaluate thresholds from lowest to highest.
    goals = (
        db.query(StretchGoal)
        .filter(StretchGoal.campaign_id == campaign_id)
        .order_by(StretchGoal.target_amount.asc(), StretchGoal.id.asc())
        .all()
    )

    results = []

    for goal in goals:
        goal.is_unlocked = pledged_total >= goal.target_amount

        results.append({
            "goal_id": goal.id,
            "title": goal.title,
            "target_amount": goal.target_amount,
            "is_unlocked": goal.is_unlocked,
        })

    db.commit()

    return {
        "campaign_id": campaign_id,
        "pledged_total": pledged_total,
        "stretch_goals": results,
    }
