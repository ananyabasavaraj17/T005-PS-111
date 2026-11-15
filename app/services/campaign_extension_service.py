
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.campaign import Campaign


def extend_campaign(
    db: Session,
    campaign_id: int,
    pledged_amount: Decimal,
    extension_days: int,
    current_time: datetime,
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Only live campaigns can be extended.")

    if campaign.extension_count >= 1:
        raise ValueError("Campaign can only be extended once.")

    if not 1 <= extension_days <= 15:
        raise ValueError("Extension cannot exceed 15 days.")

    if current_time >= campaign.deadline:
        raise ValueError("Campaign deadline has passed.")

    remaining_days = (
        campaign.deadline - current_time
    ).total_seconds() / 86400

    if remaining_days <= 7:
        raise ValueError("More than 7 days must remain.")

    pledged_amount = Decimal(str(pledged_amount))

    funding_percentage = (
        pledged_amount / campaign.goal_amount
    ) * 100

    if funding_percentage >= 50:
        raise ValueError("Campaign must be below 50% funded.")

    campaign.deadline += timedelta(days=extension_days)
    campaign.extension_count += 1
    campaign.extension_granted_at = current_time

    db.commit()
    db.refresh(campaign)

    return campaign
