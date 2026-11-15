
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
from app.services.payment_collection_service import (
    record_payment_attempt,
    collect_campaign_pledges,
    retry_failed_payments,
    process_due_retries,
)


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
        description="Payment testing campaign",
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


def create_test_pledge(db, campaign_id):
    pledge = Pledge(
        campaign_id=campaign_id,
        backer_id="backer_1",
        amount=Decimal("1000.00"),
        status="PLEDGED",
        extra_contribution=Decimal("0.00"),
    )

    db.add(pledge)
    db.commit()
    db.refresh(pledge)

    return pledge


def test_successful_payment(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    result = record_payment_attempt(
        db,
        pledge.id,
        True,
        funded_campaign.deadline,
    )

    assert result["payment_status"] == "SUCCESS"
    assert pledge.status == "COLLECTED"


def test_failed_payment(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    result = record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
        failure_reason="Card declined",
    )

    assert result["payment_status"] == "FAILED"
    assert pledge.status == "PLEDGED"


def test_retry_not_due(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
    )

    result = retry_failed_payments(
        db,
        funded_campaign.deadline + timedelta(hours=12),
    )

    assert result == []


def test_retry_due(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
    )

    result = retry_failed_payments(
        db,
        funded_campaign.deadline + timedelta(hours=24),
    )

    assert len(result) == 1
    assert result[0]["status"] == "RETRY_DUE"


def test_successful_retry(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
    )

    result = process_due_retries(
        db,
        funded_campaign.deadline + timedelta(hours=24),
        {pledge.id: True},
    )

    assert result[0]["payment_status"] == "SUCCESS"
    assert pledge.status == "COLLECTED"


def test_retry_uses_latest_failed_attempt(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
    )

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline + timedelta(hours=24),
    )

    result = retry_failed_payments(
        db,
        funded_campaign.deadline + timedelta(hours=36),
    )

    assert result == []


def test_failed_pledge_dropped_after_seven_days(db, funded_campaign):
    pledge = create_test_pledge(db, funded_campaign.id)

    record_payment_attempt(
        db,
        pledge.id,
        False,
        funded_campaign.deadline,
    )

    result = retry_failed_payments(
        db,
        funded_campaign.deadline + timedelta(days=7, seconds=1),
    )

    assert result[0]["status"] == "DROPPED"
    assert pledge.status == "PAYMENT_FAILED"

