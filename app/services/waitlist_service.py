
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.reward_tier import RewardTier
from app.models.waitlist import Waitlist


def join_waitlist(
    db: Session,
    campaign_id: int,
    tier_id: int,
    backer_id: str,
    amount: Decimal,
):
    amount = Decimal(str(amount))

    # 1. Check campaign
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "LIVE":
        raise ValueError("Campaign is not live.")

    # 2. Prevent creator from joining
    if backer_id == campaign.creator_id:
        raise ValueError("Creator cannot join their own campaign waitlist.")

    # 3. Check reward tier
    tier = db.get(RewardTier, tier_id)

    if tier is None or tier.campaign_id != campaign_id:
        raise ValueError("Invalid reward tier.")

    if tier.quantity_limit is None:
        raise ValueError("This reward tier has no quantity limit.")

    if tier.quantity_sold < tier.quantity_limit:
        raise ValueError("This reward tier is not sold out.")

    # 4. Validate amount
    if amount <= 0:
        raise ValueError("Waitlist amount must be positive.")

    # 5. Prevent duplicate active waitlist entries
    existing = (
        db.query(Waitlist)
        .filter(
            Waitlist.campaign_id == campaign_id,
            Waitlist.tier_id == tier_id,
            Waitlist.backer_id == backer_id,
            Waitlist.status == "WAITING",
        )
        .first()
    )

    if existing:
        raise ValueError("Backer is already on this waitlist.")

    # 6. Add backer to waitlist
    entry = Waitlist(
        campaign_id=campaign_id,
        tier_id=tier_id,
        backer_id=backer_id,
        amount=amount,
        status="WAITING",
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


from sqlalchemy import select

from app.models.pledge import Pledge


def allocate_next_backer(db: Session, campaign_id: int, tier_id: int):
    # Find campaign and reward tier
    campaign = db.get(Campaign, campaign_id)
    tier = db.get(RewardTier, tier_id)

    if campaign is None or tier is None:
        raise ValueError("Campaign or reward tier not found.")

    if campaign.status != "LIVE":
        return None

    # Find the earliest waiting backer (FIFO)
    next_backer = db.scalars(
        select(Waitlist)
        .where(
            Waitlist.campaign_id == campaign_id,
            Waitlist.tier_id == tier_id,
            Waitlist.status == "WAITING",
        )
        .order_by(Waitlist.created_at, Waitlist.id)
        .limit(1)
    ).first()

    if next_backer is None:
        return None

    # Check the backer's contribution cap
    existing = (
        db.query(Pledge)
        .filter(
            Pledge.campaign_id == campaign_id,
            Pledge.backer_id == next_backer.backer_id,
            Pledge.status == "PLEDGED",
        )
        .all()
    )

    existing_total = sum(
        (p.amount for p in existing),
        Decimal("0.00"),
    )

    cap = min(
        campaign.goal_amount * Decimal("0.10"),
        Decimal("200000.00"),
    )

    if existing_total + next_backer.amount > cap:
        next_backer.status = "SKIPPED"
        db.commit()
        return allocate_next_backer(db, campaign_id, tier_id)

    # Create the automatic pledge
    pledge = Pledge(
        campaign_id=campaign_id,
        backer_id=next_backer.backer_id,
        tier_id=tier_id,
        amount=next_backer.amount,
        status="PLEDGED",
    )

    db.add(pledge)

    tier.quantity_sold += 1
    next_backer.status = "ALLOCATED"

    db.commit()
    db.refresh(pledge)

    return pledge
