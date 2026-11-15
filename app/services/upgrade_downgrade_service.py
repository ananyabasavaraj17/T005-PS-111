
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.reward_tier import RewardTier


MAX_BACKER_CAP = Decimal("200000.00")
EARLY_BIRD_DISCOUNT = Decimal("15.00")


def change_pledge(
    db: Session,
    pledge_id: int,
    new_tier_id: int | None,
    current_time,
    extra_contribution: Decimal | None = None,
):
    pledge = db.get(Pledge, pledge_id)

    if pledge is None or pledge.status != "PLEDGED":
        raise ValueError("Active pledge not found.")

    campaign = db.get(Campaign, pledge.campaign_id)

    if campaign is None or campaign.status != "LIVE":
        raise ValueError("Campaign is not live.")

    old_tier = (
        db.get(RewardTier, pledge.tier_id)
        if pledge.tier_id is not None else None
    )

    new_tier = (
        db.get(RewardTier, new_tier_id)
        if new_tier_id is not None else None
    )

    if new_tier_id is not None:
        if new_tier is None or new_tier.campaign_id != campaign.id:
            raise ValueError("Invalid reward tier.")

    # Keep the existing extra contribution unless explicitly changed.
    if extra_contribution is None:
        extra = pledge.extra_contribution
    else:
        extra = Decimal(str(extra_contribution))

    if extra < 0 or extra % Decimal("100") != 0:
        raise ValueError("Extra contribution must be in multiples of Rs. 100.")

    # Calculate the new reward price.
    new_reward_price = Decimal("0.00")
    new_early_bird = False

    if new_tier is not None:
        if (
            new_tier.quantity_limit is not None
            and new_tier.quantity_sold >= new_tier.quantity_limit
            and new_tier.id != pledge.tier_id
        ):
            raise ValueError("New reward tier is sold out.")

        new_early_bird = (
            pledge.is_early_bird
            and old_tier is not None
            and old_tier.family == new_tier.family
            and new_tier.is_early_bird
        )

        new_reward_price = new_tier.price

        if new_early_bird:
            new_reward_price = (
                new_tier.price
                * (Decimal("100") - EARLY_BIRD_DISCOUNT)
                / Decimal("100")
            )

    elif extra == 0:
        raise ValueError("No-reward contribution cannot be zero.")

    new_amount = new_reward_price + extra

    # A downgrade is any decrease in total pledge amount.
    if new_amount < pledge.amount:
        cutoff = campaign.deadline - timedelta(hours=48)

        if current_time >= cutoff:
            raise ValueError(
                "Downgrades are not allowed within 48 hours of the deadline."
            )

    # Check the backer's cap, excluding this pledge.
    other_pledges = (
        db.query(Pledge)
        .filter(
            Pledge.campaign_id == campaign.id,
            Pledge.backer_id == pledge.backer_id,
            Pledge.status == "PLEDGED",
            Pledge.id != pledge.id,
        )
        .all()
    )

    other_total = sum(
        (item.amount for item in other_pledges),
        Decimal("0.00"),
    )

    backer_cap = min(
        campaign.goal_amount * Decimal("0.10"),
        MAX_BACKER_CAP,
    )

    if other_total + new_amount > backer_cap:
        raise ValueError("Backer contribution limit exceeded.")

    # Update inventory only when changing tiers.
    if old_tier is not None and (
        new_tier is None or old_tier.id != new_tier.id
    ):
        old_tier.quantity_sold = max(0, old_tier.quantity_sold - 1)

    if new_tier is not None and (
        old_tier is None or old_tier.id != new_tier.id
    ):
        new_tier.quantity_sold += 1

    pledge.tier_id = new_tier_id
    pledge.amount = new_amount
    pledge.extra_contribution = extra
    pledge.is_early_bird = new_early_bird

    db.commit()
    db.refresh(pledge)

    return pledge
