
from app.services.settlement_service import release_creator_reserve
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
        title="Test Campaign",
        description="Settlement test",
        goal_amount=Decimal("50000.00"),
        funding_model="ALL_OR_NOTHING",
        start_date=now - timedelta(days=30),
        deadline=now,
        status="FUNDED",
        creator_id="creator_1",
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


def add_collected_pledge(db, campaign, amount):
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

    return pledge


def test_all_or_nothing_settlement_calculations(db, funded_campaign):
    add_collected_pledge(db, funded_campaign, "10000.00")
    add_collected_pledge(db, funded_campaign, "10000.00")

    settlement = calculate_settlement(
        db,
        funded_campaign.id,
        datetime(2026, 1, 1, 12, 0, 0),
    )

    assert settlement.pledged_amount == Decimal("20000.00")
    assert settlement.collected_amount == Decimal("20000.00")
    assert settlement.successful_charge_count == 2

    # Platform fee: 5%
    assert settlement.platform_fee == Decimal("1000.00")

    # Processing: 2.5% + Rs. 3 per successful charge
    assert settlement.processing_fee == Decimal("506.00")

    # GST: 18% of platform + processing fees
    assert settlement.gst_amount == Decimal("271.08")

    assert settlement.total_fees == Decimal("1777.08")
    assert settlement.net_amount == Decimal("18222.92")

    # 10% reserve
    assert settlement.reserve_amount == Decimal("1822.29")
    assert settlement.reserve_remaining == Decimal("1822.29")

    # Remaining 90% paid to creator
    assert settlement.payout_amount == Decimal("16400.63")


def test_flexible_settlement_uses_eight_percent_platform_fee(db, funded_campaign):
    funded_campaign.funding_model = "FLEXIBLE"
    db.commit()

    add_collected_pledge(db, funded_campaign, "10000.00")

    settlement = calculate_settlement(
        db,
        funded_campaign.id,
        datetime(2026, 1, 1, 12, 0, 0),
    )

    assert settlement.platform_fee == Decimal("800.00")
    assert settlement.processing_fee == Decimal("253.00")
    assert settlement.gst_amount == Decimal("189.54")
    assert settlement.total_fees == Decimal("1242.54")
    assert settlement.net_amount == Decimal("8757.46")


def test_settlement_payout_and_reserve_dates(db, funded_campaign):
    add_collected_pledge(db, funded_campaign, "10000.00")

    settlement = calculate_settlement(
        db,
        funded_campaign.id,
        datetime(2026, 1, 1, 12, 0, 0),
    )

    assert settlement.payout_due_at == (
        funded_campaign.deadline + timedelta(days=14)
    )

    assert settlement.reserve_release_at == (
        funded_campaign.deadline + timedelta(days=90)
    )

    assert settlement.status == "PENDING_PAYOUT"
    assert settlement.reserve_frozen is False


def test_duplicate_settlement_is_rejected(db, funded_campaign):
    add_collected_pledge(db, funded_campaign, "10000.00")

    calculate_settlement(
        db,
        funded_campaign.id,
        datetime(2026, 1, 1, 12, 0, 0),
    )

    with pytest.raises(ValueError, match="Settlement already exists"):
        calculate_settlement(
            db,
            funded_campaign.id,
            datetime(2026, 1, 1, 12, 0, 0),
        )


from app.services.settlement_service import execute_creator_payout


def test_creator_payout_after_14_days(db, funded_campaign):
    add_collected_pledge(db, funded_campaign, "10000.00")

    settlement = calculate_settlement(
        db,
        funded_campaign.id,
        funded_campaign.deadline,
    )

    payout_time = funded_campaign.deadline + timedelta(days=14)

    result = execute_creator_payout(
        db,
        funded_campaign.id,
        payout_time,
    )

    assert result.status == "PAYOUT_COMPLETED"
    assert result.settled_at == payout_time

def test_reserve_release_after_90_days(db, funded_campaign):
    add_collected_pledge(db, funded_campaign, "10000.00")

    settlement = calculate_settlement(
        db,
        funded_campaign.id,
        funded_campaign.deadline,
    )

    payout_time = funded_campaign.deadline + timedelta(days=14)

    execute_creator_payout(
        db,
        funded_campaign.id,
        payout_time,
    )

    release_time = funded_campaign.deadline + timedelta(days=90)

    released_amount = release_creator_reserve(
        db,
        funded_campaign.id,
        release_time,
    )

    assert released_amount == settlement.reserve_amount
    assert settlement.reserve_remaining == Decimal("0.00")
    assert settlement.status == "COMPLETED"