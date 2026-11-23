from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.stretch_goal import StretchGoal
from app.services.campaign_service import create_campaign
from app.services.campaign_closing_service import close_campaign
from app.services.campaign_extension_service import extend_campaign


@pytest.fixture
def db():
    # Safety: tests use a separate in-memory database, never crowdfunding.db.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def live_campaign(db):
    now = datetime(2026, 1, 1, 12, 0, 0)
    campaign = Campaign(
        title="Campaign service test",
        description="Testing campaign services",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=now - timedelta(days=20),
        deadline=now + timedelta(days=20),
        status="LIVE",
        creator_id="creator_1",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def add_pledge(db, campaign, amount, status="PLEDGED"):
    pledge = Pledge(
        campaign_id=campaign.id,
        backer_id="backer_test",
        amount=Decimal(str(amount)),
        status=status,
    )
    db.add(pledge)
    db.commit()
    db.refresh(pledge)
    return pledge


def add_stretch_goal(db, campaign, target, unlocked=False):
    goal = StretchGoal(
        campaign_id=campaign.id,
        title="Test stretch goal",
        description="Goal for campaign closing tests",
        target_amount=Decimal(str(target)),
        is_unlocked=unlocked,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


# Campaign creation

def test_create_campaign_valid_input_creates_draft(db):
    start = datetime(2026, 1, 1, 12)
    campaign = create_campaign(
        db=db,
        title="New campaign",
        description="Valid campaign description",
        goal_amount=Decimal("50000.00"),
        funding_model="flexible",
        start_date=start,
        deadline=start + timedelta(days=15),
        creator_id="creator_1",
    )
    assert campaign.id
    assert campaign.status == "DRAFT"
    assert campaign.funding_model == "FLEXIBLE"
    assert campaign.goal_amount == Decimal("50000.00")


@pytest.mark.parametrize("goal", ["49999.99", "0", "-1"])
def test_create_campaign_rejects_goal_below_minimum(db, goal):
    start = datetime(2026, 1, 1, 12)
    with pytest.raises(ValueError, match="Minimum campaign goal"):
        create_campaign(
            db, "Campaign", "Description", Decimal(goal), "FLEXIBLE",
            start, start + timedelta(days=20),
        )


def test_create_campaign_rejects_invalid_funding_model(db):
    start = datetime(2026, 1, 1, 12)
    with pytest.raises(ValueError, match="Invalid funding model"):
        create_campaign(
            db, "Campaign", "Description", Decimal("50000"),
            "INVALID", start, start + timedelta(days=20),
        )


@pytest.mark.parametrize("days", [14, 61])
def test_create_campaign_rejects_duration_outside_range(db, days):
    start = datetime(2026, 1, 1, 12)
    with pytest.raises(ValueError, match="Campaign duration"):
        create_campaign(
            db, "Campaign", "Description", Decimal("50000"),
            "FLEXIBLE", start, start + timedelta(days=days),
        )


def test_create_campaign_rejects_deadline_before_start(db):
    start = datetime(2026, 1, 1, 12)
    with pytest.raises(ValueError):
        create_campaign(
            db, "Campaign", "Description", Decimal("50000"),
            "FLEXIBLE", start, start - timedelta(days=1),
        )


# Campaign closing

def test_close_all_or_nothing_campaign_when_goal_is_met(db, live_campaign):
    live_campaign.funding_model = "ALL_OR_NOTHING"
    live_campaign.goal_amount = Decimal("50000.00")
    add_pledge(db, live_campaign, "50000.00")
    now = live_campaign.deadline + timedelta(seconds=1)

    result = close_campaign(db, live_campaign.id, now)

    assert result["status"] == "FUNDED"
    assert live_campaign.status == "FUNDED"


def test_close_all_or_nothing_campaign_as_failed_below_goal(db, live_campaign):
    live_campaign.funding_model = "ALL_OR_NOTHING"
    add_pledge(db, live_campaign, "49999.99")
    now = live_campaign.deadline + timedelta(seconds=1)

    result = close_campaign(db, live_campaign.id, now)

    assert result["status"] == "FAILED"
    assert live_campaign.status == "FAILED"


def test_close_flexible_campaign_at_twenty_percent_threshold(db, live_campaign):
    add_pledge(db, live_campaign, "10000.00")
    now = live_campaign.deadline + timedelta(seconds=1)

    result = close_campaign(db, live_campaign.id, now)

    assert result["status"] == "FUNDED"


def test_close_flexible_campaign_below_twenty_percent(db, live_campaign):
    add_pledge(db, live_campaign, "9999.99")
    now = live_campaign.deadline + timedelta(seconds=1)

    result = close_campaign(db, live_campaign.id, now)

    assert result["status"] == "FAILED"


def test_campaign_closing_ignores_non_pledged_status(db, live_campaign):
    add_pledge(db, live_campaign, "50000.00", status="CANCELLED")
    now = live_campaign.deadline + timedelta(seconds=1)

    result = close_campaign(db, live_campaign.id, now)

    assert result["pledged_total"] == Decimal("0.00")
    assert result["status"] == "FAILED"


def test_campaign_closing_updates_stretch_goal_unlock_state(db, live_campaign):
    add_pledge(db, live_campaign, "20000.00")
    reached = add_stretch_goal(db, live_campaign, "15000.00")
    not_reached = add_stretch_goal(db, live_campaign, "25000.00")
    now = live_campaign.deadline + timedelta(seconds=1)

    close_campaign(db, live_campaign.id, now)

    assert reached.is_unlocked is True
    assert not_reached.is_unlocked is False

def test_campaign_closing_rejects_before_deadline(db, live_campaign):
    before_deadline = live_campaign.deadline - timedelta(seconds=1)

    with pytest.raises(ValueError):
        close_campaign(
            db,
            live_campaign.id,
            before_deadline,
        )

def test_campaign_closing_rejects_non_live_campaign(db, live_campaign):
    live_campaign.status = "FAILED"
    db.commit()

    with pytest.raises(ValueError):
        close_campaign(
            db,
            live_campaign.id,
            live_campaign.deadline + timedelta(seconds=1),
        )


# Campaign extension

def test_extend_campaign_updates_deadline_and_count(db, live_campaign):
    original_deadline = live_campaign.deadline
    now = datetime(2026, 1, 1, 12, 0, 0)

    extended = extend_campaign(
        db, live_campaign.id, Decimal("10000.00"), 5, now
    )

    assert extended.deadline == original_deadline + timedelta(days=5)
    assert extended.extension_count == 1
    assert extended.extension_granted_at == now


def test_extension_rejects_second_extension(db, live_campaign):
    live_campaign.extension_count = 1
    db.commit()
    with pytest.raises(ValueError):
        extend_campaign(
            db, live_campaign.id, Decimal("10000"), 5,
            datetime(2026, 1, 1, 12),
        )


@pytest.mark.parametrize("days", [0, 16])
def test_extension_rejects_invalid_extension_days(db, live_campaign, days):
    with pytest.raises(ValueError):
        extend_campaign(
            db, live_campaign.id, Decimal("10000"), days,
            datetime(2026, 1, 1, 12),
        )


def test_extension_rejects_campaign_with_seven_or_fewer_days_remaining(
    db, live_campaign
):
    now = live_campaign.deadline - timedelta(days=7)
    with pytest.raises(ValueError, match="More than 7 days"):
        extend_campaign(db, live_campaign.id, Decimal("10000"), 5, now)


def test_extension_rejects_campaign_at_or_above_fifty_percent(db, live_campaign):
    with pytest.raises(ValueError, match="below 50%"):
        extend_campaign(
            db, live_campaign.id, Decimal("25000"), 5,
            datetime(2026, 1, 1, 12),
        )


def test_extension_rejects_campaign_that_is_not_live(db, live_campaign):
    live_campaign.status = "FAILED"
    db.commit()
    with pytest.raises(ValueError):
        extend_campaign(
            db, live_campaign.id, Decimal("10000"), 5,
            datetime(2026, 1, 1, 12),
        )
