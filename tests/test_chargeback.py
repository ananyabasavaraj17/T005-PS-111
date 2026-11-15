
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.payment import Payment
from app.models.settlement import Settlement
from app.services.settlement_service import calculate_settlement
from app.services.chargeback_service import process_chargeback


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
def funded_campaign(db):
    now = datetime(2026, 1, 1, 12, 0, 0)

    campaign = Campaign(
        title="Chargeback Test Campaign",
        description="Testing chargebacks",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=now - timedelta(days=30),
        deadline=now,
        status="FUNDED",
        creator_id="creator_1",
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


def create_settlement_with_pledges(db, campaign, count=3):
    pledges = []

    for number in range(count):
        pledge = Pledge(
            campaign_id=campaign.id,
            backer_id=f"backer_{number}",
            tier_id=None,
            amount=Decimal("10000.00"),
            status="COLLECTED",
            is_early_bird=False,
            extra_contribution=Decimal("0.00"),
        )

        db.add(pledge)
        db.commit()
        db.refresh(pledge)

        payment = Payment(
            pledge_id=pledge.id,
            amount=Decimal("10000.00"),
            status="SUCCESS",
            attempt_number=1,
            attempted_at=campaign.deadline,
        )

        db.add(payment)
        db.commit()

        pledges.append(pledge)

    settlement = calculate_settlement(
        db,
        campaign.id,
        campaign.deadline,
    )

    return pledges, settlement


def test_chargeback_records_500_fee(db, funded_campaign):
    pledges, settlement = create_settlement_with_pledges(
        db, funded_campaign, count=1
    )

    chargeback = process_chargeback(
        db,
        pledges[0].id,
        Decimal("500.00"),
        "UNAUTHORIZED_TRANSACTION",
        funded_campaign.deadline + timedelta(days=10),
    )

    assert chargeback.amount == Decimal("500.00")
    assert chargeback.chargeback_fee == Decimal("500.00")
    assert chargeback.status == "OPEN"


def test_chargeback_deducts_from_reserve(db, funded_campaign):
    pledges, settlement = create_settlement_with_pledges(
        db, funded_campaign, count=1
    )

    original_reserve = settlement.reserve_remaining

    chargeback = process_chargeback(
        db,
        pledges[0].id,
        Decimal("500.00"),
        "UNAUTHORIZED_TRANSACTION",
        funded_campaign.deadline + timedelta(days=10),
    )

    assert chargeback.reserve_amount_used == Decimal("500.00")
    assert settlement.reserve_remaining == original_reserve - Decimal("500.00")


def test_chargeback_rejected_after_90_days(db, funded_campaign):
    pledges, settlement = create_settlement_with_pledges(
        db, funded_campaign, count=1
    )

    with pytest.raises(ValueError, match="90-day"):
        process_chargeback(
            db,
            pledges[0].id,
            Decimal("500.00"),
            "UNAUTHORIZED_TRANSACTION",
            funded_campaign.deadline + timedelta(days=91),
        )


def test_reserve_freezes_after_three_chargebacks(db, funded_campaign):
    pledges, settlement = create_settlement_with_pledges(
        db, funded_campaign, count=3
    )

    for pledge in pledges:
        process_chargeback(
            db,
            pledge.id,
            Decimal("500.00"),
            "UNAUTHORIZED_TRANSACTION",
            funded_campaign.deadline + timedelta(days=10),
        )

    assert settlement.chargeback_count == 3
    assert settlement.reserve_frozen is True
