
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.creator import Creator
from app.models.pledge import Pledge
from app.models.reward_tier import RewardTier
from app.services.stretch_goal_service import evaluate_stretch_goals


MAX_BACKER_CAP = Decimal("200000.00")
EARLY_BIRD_DISCOUNT = Decimal("15.00")


def create_pledge(
    db: Session,
    campaign_id: int,
    backer_id: str,
    amount: Decimal,
    tier_id: int | None = None,
    extra_contribution: Decimal = Decimal("0.00"),
):
    amount = Decimal(str(amount))
    extra_contribution = Decimal(str(extra_contribution))

    # 1. Check campaign
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Campaign is not live.")

    # 2. Prevent creator and team members from pledging (BR-39)
    if backer_id == campaign.creator_id:
        raise ValueError("Creator cannot pledge to their own campaign.")

    creator = db.get(Creator, campaign.creator_id)
    if creator and creator.team_member_backer_ids:
        team_members = [
            tid.strip()
            for tid in creator.team_member_backer_ids.split(";")
            if tid.strip()
        ]
        if backer_id in team_members:
            raise ValueError(
                "Creator team members cannot pledge to their own campaign."
            )

    # 3. Validate contribution
    if amount <= 0 or extra_contribution < 0:
        raise ValueError("Invalid pledge amount.")

    if extra_contribution % Decimal("100") != 0:
        raise ValueError(
            "Extra contribution must be in multiples of Rs. 100."
        )

    # 4. Check reward tier availability
    tier = None
    received_early_bird = False

    if tier_id is not None:
        tier = db.get(RewardTier, tier_id)

        if tier is None or tier.campaign_id != campaign_id:
            raise ValueError("Invalid reward tier.")

        if (
            tier.quantity_limit is not None
            and tier.quantity_sold >= tier.quantity_limit
        ):
            raise ValueError("Reward tier is sold out.")

        expected_amount = tier.price + extra_contribution

        # Apply early-bird discount when slots remain
        if (
            tier.is_early_bird
            and tier.early_bird_claimed < tier.early_bird_limit
        ):
            received_early_bird = True

            expected_amount = (
                tier.price
                * (Decimal("100") - EARLY_BIRD_DISCOUNT)
                / Decimal("100")
            ) + extra_contribution

        if amount != expected_amount:
            raise ValueError("Pledge amount does not match reward price.")

    else:
        if amount % Decimal("100") != 0:
            raise ValueError(
                "No-reward contributions must be multiples of Rs. 100."
            )

    # 5. Calculate backer's existing pledges
    existing_pledges = (
        db.query(Pledge)
        .filter(
            Pledge.campaign_id == campaign_id,
            Pledge.backer_id == backer_id,
            Pledge.status == "PLEDGED",
        )
        .all()
    )

    existing_total = sum(
        (pledge.amount for pledge in existing_pledges),
        Decimal("0.00"),
    )

    backer_cap = min(
        campaign.goal_amount * Decimal("0.10"),
        MAX_BACKER_CAP,
    )

    if existing_total + amount > backer_cap:
        raise ValueError("Backer contribution limit exceeded.")

    # 6. Create pledge
    pledge = Pledge(
        campaign_id=campaign_id,
        backer_id=backer_id,
        tier_id=tier_id,
        amount=amount,
        extra_contribution=extra_contribution,
        status="PLEDGED",
        is_early_bird=received_early_bird,
    )

    db.add(pledge)

    # 7. Update reward inventory
    if tier is not None:
        tier.quantity_sold += 1

        if received_early_bird:
            tier.early_bird_claimed += 1

    # 8. Save pledge and evaluate stretch goals
    db.commit()

    evaluate_stretch_goals(db, campaign_id)

    db.refresh(pledge)

    return pledge
