from decimal import Decimal
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.stretch_goal import StretchGoal
from app.models.reward_tier import RewardTier


def generate_campaign_report(db: Session, campaign_id: int) -> Dict:
    """Return a concise financial report for a campaign.

    The report includes:
        - campaign basic info (title, status, goal, dates)
        - total pledged amount (only ``PLEDGED`` pledges)
        - breakdown of reward‑tier sales (sold/limit)
        - stretch‑goal unlock status
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found.")

    # Total pledged (only active pledges)
    pledged_total = (
        db.query(func.coalesce(func.sum(Pledge.amount), 0))
        .filter(Pledge.campaign_id == campaign_id, Pledge.status == "PLEDGED")
        .scalar()
    )
    pledged_total = Decimal(str(pledged_total))

    # Reward tier summary
    reward_summary: List[Dict] = []
    tiers = db.query(RewardTier).filter(RewardTier.campaign_id == campaign_id).all()
    for tier in tiers:
        reward_summary.append(
            {
                "tier_id": tier.id,
                "name": tier.name,
                "price": tier.price,
                "quantity_limit": tier.quantity_limit,
                "quantity_sold": tier.quantity_sold,
                "is_early_bird": tier.is_early_bird,
                "early_bird_limit": tier.early_bird_limit,
                "early_bird_claimed": tier.early_bird_claimed,
            }
        )

    # Stretch goals
    stretch_goals = db.query(StretchGoal).filter(StretchGoal.campaign_id == campaign_id).all()
    stretch_summary = [
        {
            "goal_id": g.id,
            "title": g.title,
            "target_amount": g.target_amount,
            "is_unlocked": g.is_unlocked,
        }
        for g in stretch_goals
    ]

    report = {
        "campaign_id": campaign.id,
        "title": campaign.title,
        "status": campaign.status,
        "goal_amount": campaign.goal_amount,
        "funding_model": campaign.funding_model,
        "start_date": campaign.start_date,
        "deadline": campaign.deadline,
        "created_at": campaign.created_at,
        "pledged_total": pledged_total,
        "reward_summary": reward_summary,
        "stretch_goals": stretch_summary,
    }
    return report
