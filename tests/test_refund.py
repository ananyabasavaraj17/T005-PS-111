
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
from app.models.refund import Refund
from app.services.settlement_service import calculate_settlement
from app.services.refund_service import process_refund


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
        title="Refund Test Campaign",
        description="Testing refunds",
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


def create_settlement_with_collected_pledge(db, campaign, amount):
    pledge = Pledge(
        campaign_id=campaign.id,
        backer_id="backer_1",
        tier_id=None,
        amount=Decimal(str(amount)),
        status="COLLECTED",
        is_early_bird=False,
        extra_contribution=Decimal("0.00"),
    )

    db.add(pledge)
    db.commit()
    db.refresh(pledge)

    payment = Payment(
        pledge_id=pledge.id,
        amount=Decimal(str(amount)),
        status="SUCCESS",
        attempt_number=1,
        attempted_at=campaign.deadline,
    )

    db.add(payment)
    db.commit()

    settlement = calculate_settlement(
        db,
        campaign.id,
        campaign.deadline,
    )

    return pledge, settlement


def test_refund_uses_reserve_first(db, funded_campaign):
    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    refund = process_refund(
        db,
        pledge.id,
        Decimal("500.00"),
        "CUSTOMER_REQUEST",
        funded_campaign.deadline + timedelta(days=5),
    )

    assert refund.status == "PROCESSED"
    assert refund.reserve_amount_used == Decimal("500.00")
    assert refund.creator_receivable_used == Decimal("0.00")
    assert settlement.reserve_remaining == (
        settlement.reserve_amount - Decimal("500.00")
    )


def test_refund_uses_creator_receivable_for_shortfall(db, funded_campaign):
    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    settlement.reserve_remaining = Decimal("100.00")
    db.commit()

    refund = process_refund(
        db,
        pledge.id,
        Decimal("500.00"),
        "CUSTOMER_REQUEST",
        funded_campaign.deadline + timedelta(days=5),
    )

    assert refund.reserve_amount_used == Decimal("100.00")
    assert refund.creator_receivable_used == Decimal("400.00")
    assert settlement.reserve_remaining == Decimal("0.00")


def test_failed_delivery_refund_allowed_for_all_funding_models(
    db, funded_campaign
):
    funded_campaign.funding_model = "ALL_OR_NOTHING"
    db.commit()

    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    refund = process_refund(
        db,
        pledge.id,
        Decimal("200.00"),
        "FAILED_DELIVERY",
        funded_campaign.deadline + timedelta(days=5),
    )

    assert refund.status == "PROCESSED"
    assert refund.amount == Decimal("200.00")


def test_normal_refund_rejected_for_all_or_nothing(
    db, funded_campaign
):
    funded_campaign.funding_model = "ALL_OR_NOTHING"
    db.commit()

    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    with pytest.raises(ValueError, match="FLEXIBLE"):
        process_refund(
            db,
            pledge.id,
            Decimal("200.00"),
            "CUSTOMER_REQUEST",
            funded_campaign.deadline + timedelta(days=5),
        )


def test_refund_rejected_after_14_days(db, funded_campaign):
    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    with pytest.raises(ValueError, match="14-day"):
        process_refund(
            db,
            pledge.id,
            Decimal("200.00"),
            "CUSTOMER_REQUEST",
            funded_campaign.deadline + timedelta(days=15),
        )


def test_refund_cannot_exceed_pledge_amount(db, funded_campaign):
    pledge, settlement = create_settlement_with_collected_pledge(
        db, funded_campaign, "10000.00"
    )

    with pytest.raises(ValueError, match="exceed"):
        process_refund(
            db,
            pledge.id,
            Decimal("11000.00"),
            "CUSTOMER_REQUEST",
            funded_campaign.deadline + timedelta(days=5),
        )
