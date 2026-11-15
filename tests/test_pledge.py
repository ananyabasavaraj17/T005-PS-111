
from app.models.reward_tier import RewardTier
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.services.pledge_service import create_pledge


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    session = TestingSession()
    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def live_campaign(db):
    now = datetime(2026, 1, 1, 12, 0, 0)

    campaign = Campaign(
        title="Pledge Test Campaign",
        description="Testing pledges",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=now - timedelta(days=5),
        deadline=now + timedelta(days=30),
        status="LIVE",
        creator_id="creator_1",
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


def test_create_pledge_without_reward(db, live_campaign):
    pledge = create_pledge(
        db=db,
        campaign_id=live_campaign.id,
        backer_id="backer_1",
        amount=Decimal("1000.00"),
    )

    assert pledge.id is not None
    assert pledge.campaign_id == live_campaign.id
    assert pledge.backer_id == "backer_1"
    assert pledge.amount == Decimal("1000.00")
    assert pledge.status == "PLEDGED"
    assert pledge.tier_id is None
    assert pledge.is_early_bird is False

    saved_pledge = db.get(Pledge, pledge.id)
    assert saved_pledge is not None

def test_zero_pledge_rejected(db, live_campaign):
    with pytest.raises(ValueError, match="Invalid pledge amount"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_2",
            amount=Decimal("0.00"),
        )


def test_negative_pledge_rejected(db, live_campaign):
    with pytest.raises(ValueError, match="Invalid pledge amount"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_2",
            amount=Decimal("-500.00"),
        )


def test_extra_contribution_must_be_multiple_of_100(db, live_campaign):
    with pytest.raises(ValueError, match="multiples of Rs. 100"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_2",
            amount=Decimal("1000.00"),
            extra_contribution=Decimal("50.00"),
        )


def test_no_reward_pledge_must_be_multiple_of_100(db, live_campaign):
    with pytest.raises(ValueError, match="multiples of Rs. 100"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_2",
            amount=Decimal("1050.00"),
        )


# Helper to create reward tiers for testing
def create_reward_tier(db, campaign, **overrides):
    tier_data = {
        "campaign_id": campaign.id,
        "name": "Standard Reward",
        "family": "STANDARD",
        "description": "A standard reward",
        "price": Decimal("1000.00"),
        "quantity_limit": 5,
        "quantity_sold": 0,
        "is_early_bird": False,
        "early_bird_discount": Decimal("15.00"),
        "early_bird_limit": 2,
        "early_bird_claimed": 0,
    }

    tier_data.update(overrides)

    tier = RewardTier(**tier_data)
    db.add(tier)
    db.commit()
    db.refresh(tier)

    return tier


# 1. Reject nonexistent campaign
def test_pledge_rejected_for_nonexistent_campaign(db):
    with pytest.raises(ValueError, match="Campaign not found"):
        create_pledge(
            db=db,
            campaign_id=999,
            backer_id="backer_1",
            amount=Decimal("1000.00"),
        )


# 2. Reject pledge when campaign is not LIVE
def test_pledge_rejected_for_non_live_campaign(db, live_campaign):
    live_campaign.status = "DRAFT"
    db.commit()

    with pytest.raises(ValueError, match="not live"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("1000.00"),
        )


# 3. Creator cannot pledge to own campaign
def test_creator_cannot_pledge(db, live_campaign):
    with pytest.raises(ValueError, match="Creator cannot pledge"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="creator_1",
            amount=Decimal("1000.00"),
        )


# 4. Reject nonexistent reward tier
def test_invalid_reward_tier_rejected(db, live_campaign):
    with pytest.raises(ValueError, match="Invalid reward tier"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("1000.00"),
            tier_id=999,
        )


# 5. Reject a reward tier belonging to another campaign
def test_reward_tier_from_another_campaign_rejected(db, live_campaign):
    another_campaign = Campaign(
        title="Another Campaign",
        description="Another test campaign",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=live_campaign.start_date,
        deadline=live_campaign.deadline,
        status="LIVE",
        creator_id="creator_2",
    )

    db.add(another_campaign)
    db.commit()
    db.refresh(another_campaign)

    tier = create_reward_tier(db, another_campaign)

    with pytest.raises(ValueError, match="Invalid reward tier"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("1000.00"),
            tier_id=tier.id,
        )


# 6. Reject sold-out reward tier
def test_sold_out_reward_tier_rejected(db, live_campaign):
    tier = create_reward_tier(
        db,
        live_campaign,
        quantity_limit=5,
        quantity_sold=5,
    )

    with pytest.raises(ValueError, match="sold out"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("1000.00"),
            tier_id=tier.id,
        )


# 7. Reject incorrect reward pledge amount
def test_incorrect_reward_amount_rejected(db, live_campaign):
    tier = create_reward_tier(db, live_campaign)

    with pytest.raises(ValueError, match="does not match reward price"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("1500.00"),
            tier_id=tier.id,
        )


# 8. Successful normal reward pledge updates inventory
def test_normal_reward_pledge_updates_inventory(db, live_campaign):
    tier = create_reward_tier(db, live_campaign)

    pledge = create_pledge(
        db=db,
        campaign_id=live_campaign.id,
        backer_id="backer_1",
        amount=Decimal("1000.00"),
        tier_id=tier.id,
    )

    assert pledge.status == "PLEDGED"
    assert pledge.is_early_bird is False
    assert tier.quantity_sold == 1


# 9. Early-bird discount is applied correctly
def test_early_bird_discount_applied(db, live_campaign):
    tier = create_reward_tier(
        db,
        live_campaign,
        is_early_bird=True,
        early_bird_limit=2,
    )

    pledge = create_pledge(
        db=db,
        campaign_id=live_campaign.id,
        backer_id="backer_1",
        amount=Decimal("850.00"),
        tier_id=tier.id,
    )

    assert pledge.amount == Decimal("850.00")
    assert pledge.is_early_bird is True
    assert tier.early_bird_claimed == 1
    assert tier.quantity_sold == 1


# 10. Full early-bird slots mean regular price applies
def test_early_bird_exhausted_uses_regular_price(db, live_campaign):
    tier = create_reward_tier(
        db,
        live_campaign,
        is_early_bird=True,
        early_bird_limit=2,
        early_bird_claimed=2,
    )

    pledge = create_pledge(
        db=db,
        campaign_id=live_campaign.id,
        backer_id="backer_1",
        amount=Decimal("1000.00"),
        tier_id=tier.id,
    )

    assert pledge.amount == Decimal("1000.00")
    assert pledge.is_early_bird is False
    assert tier.early_bird_claimed == 2


# 11. Backer cannot exceed contribution cap
def test_backer_contribution_cap_enforced(db, live_campaign):
    existing_pledge = Pledge(
        campaign_id=live_campaign.id,
        backer_id="backer_1",
        tier_id=None,
        amount=Decimal("4000.00"),
        status="PLEDGED",
        is_early_bird=False,
        extra_contribution=Decimal("0.00"),
    )

    db.add(existing_pledge)
    db.commit()

    with pytest.raises(ValueError, match="contribution limit exceeded"):
        create_pledge(
            db=db,
            campaign_id=live_campaign.id,
            backer_id="backer_1",
            amount=Decimal("2000.00"),
        )


