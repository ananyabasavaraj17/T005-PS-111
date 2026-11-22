from app.services.stretch_goal_service import evaluate_stretch_goals
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.reward_tier import RewardTier
from app.services.waitlist_service import allocate_next_backer


def cancel_pledge(db: Session, pledge_id: str | int):
    # Find pledge
    pledge = db.get(Pledge, pledge_id)

    if pledge is None:
        raise ValueError("Pledge not found.")

    if pledge.status != "PLEDGED":
        raise ValueError("Only active pledges can be cancelled.")

    # Find campaign
    campaign = db.get(Campaign, pledge.campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Pledges can only be cancelled while campaign is live.")

    # Cancel pledge
    pledge.status = "CANCELLED"

    # Free the reward quantity
    if pledge.tier_id is not None:
        tier = db.get(RewardTier, pledge.tier_id)

        if tier is not None:
            tier.quantity_sold = max(0, tier.quantity_sold - 1)

    db.commit()

    # Allocate the freed reward to the next eligible backer
    allocated = None
    if pledge.tier_id is not None:
        allocated = allocate_next_backer(
            db,
            pledge.campaign_id,
            pledge.tier_id,
        )

    evaluate_stretch_goals(db, pledge.campaign_id)

    return allocated
