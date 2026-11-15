
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
from app.services.stretch_goal_service import evaluate_stretch_goals


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def live_campaign(db):
    campaign = Campaign(
        title="Test Campaign",
        description="Testing stretch goals",
        goal_amount=Decimal("50000"),
        funding_model="FLEXIBLE",
        start_date=datetime.utcnow(),
        deadline=datetime.utcnow() + timedelta(days=30),
        status="LIVE",
        creator_id=1,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def add_goal(db, campaign, title, target):
    goal = StretchGoal(
        campaign_id=campaign.id,
        title=title,
        description="Test stretch goal",
        target_amount=Decimal(str(target)),
        is_unlocked=False,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def add_pledge(db, campaign, amount, status="PLEDGED"):
    pledge = Pledge(
        campaign_id=campaign.id,
        backer_id=2,
        amount=Decimal(str(amount)),
        status=status,
    )
    db.add(pledge)
    db.commit()
    return pledge


def test_stretch_goal_unlocks_when_target_reached(db, live_campaign):
    goal = add_goal(db, live_campaign, "First Goal", 10000)
    add_pledge(db, live_campaign, 10000)

    result = evaluate_stretch_goals(db, live_campaign.id)

    assert result["pledged_total"] == Decimal("10000")
    assert goal.is_unlocked is True


def test_stretch_goal_remains_locked_below_target(db, live_campaign):
    goal = add_goal(db, live_campaign, "First Goal", 10000)
    add_pledge(db, live_campaign, 5000)

    evaluate_stretch_goals(db, live_campaign.id)

    assert goal.is_unlocked is False


def test_only_active_pledges_are_counted(db, live_campaign):
    goal = add_goal(db, live_campaign, "First Goal", 10000)
    add_pledge(db, live_campaign, 5000, "PLEDGED")
    add_pledge(db, live_campaign, 10000, "CANCELLED")

    result = evaluate_stretch_goals(db, live_campaign.id)

    assert result["pledged_total"] == Decimal("5000")
    assert goal.is_unlocked is False


def test_multiple_stretch_goals_unlock_correctly(db, live_campaign):
    goal1 = add_goal(db, live_campaign, "First Goal", 5000)
    goal2 = add_goal(db, live_campaign, "Second Goal", 10000)
    goal3 = add_goal(db, live_campaign, "Third Goal", 20000)

    add_pledge(db, live_campaign, 12000)

    evaluate_stretch_goals(db, live_campaign.id)

    assert goal1.is_unlocked is True
    assert goal2.is_unlocked is True
    assert goal3.is_unlocked is False


def test_non_live_campaign_rejected(db, live_campaign):
    live_campaign.status = "CLOSED"
    db.commit()

    with pytest.raises(ValueError):
        evaluate_stretch_goals(db, live_campaign.id)


def test_nonexistent_campaign_rejected(db):
    with pytest.raises(ValueError):
        evaluate_stretch_goals(db, 999)
