from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.campaign import Campaign
from app.models.creator import Creator
from app.models.backer import Backer
from app.models.reward_tier import RewardTier
from app.models.stretch_goal import StretchGoal
from app.models.pledge import Pledge
from app.models.payment import Payment
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.settlement import Settlement
from app.models.waitlist import Waitlist
from app.models.id_generator import generate_id, get_id_generator, VALID_PREFIXES


@pytest.fixture
def db():
    # Strict safety rule: isolated in-memory database only
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_id_generator_prefixes_and_callable_uniqueness():
    # Verify all expected prefixes
    expected_prefixes = {"CMP", "CRT", "TIR", "SG", "BKR", "PLG", "PAY", "REF", "CHB", "STL"}
    for p in expected_prefixes:
        assert p in VALID_PREFIXES
        gen_fn = get_id_generator(p)
        id1 = gen_fn()
        id2 = gen_fn()
        assert id1 != id2
        assert id1.startswith(f"{p}_")
        assert id2.startswith(f"{p}_")


def test_alphanumeric_identifiers_and_relationships(db):
    # 1. Create creator and backer
    creator = Creator(
        creator_id="CRT-01",
        creator_name="Studio Kaveri",
        team_member_backer_ids="BKR-001;BKR-002",
    )
    backer = Backer(
        backer_id="BKR-010",
        backer_name="Anand Rao",
        city="Bengaluru",
        device_id="DEV-0010",
    )
    db.add_all([creator, backer])
    db.commit()

    # 2. Create campaign with string ID
    now = datetime(2026, 9, 1, 10, 0, 0)
    campaign = Campaign(
        id="CMP-01",
        title="Kannada Folk Tales",
        description="Illustrated book",
        goal_amount=Decimal("100000.00"),
        funding_model="ALL_OR_NOTHING",
        start_date=now,
        deadline=now + timedelta(days=44),
        status="LIVE",
        creator_id=creator.creator_id,
        has_failed_delivery=False,
    )
    db.add(campaign)
    db.commit()

    # 3. Create tier and stretch goal
    tier = RewardTier(
        id="TIR-03",
        campaign_id=campaign.id,
        name="Collector box",
        family="BOOK",
        description="Collector box edition",
        price=Decimal("8000.00"),
        quantity_limit=15,
        early_bird_limit=0,
    )
    goal = StretchGoal(
        id="SG-01",
        campaign_id=campaign.id,
        title="Audio narration",
        description="Audio narration unlock",
        target_amount=Decimal("120000.00"),
    )
    db.add_all([tier, goal])
    db.commit()

    # 4. Create pledge with string ID
    pledge = Pledge(
        id="PLG-0001",
        campaign_id=campaign.id,
        backer_id=backer.backer_id,
        tier_id=tier.id,
        amount=Decimal("10000.00"),
        extra_contribution=Decimal("2000.00"),
        status="PLEDGED",
    )
    db.add(pledge)
    db.commit()

    # 5. Create payment, refund, chargeback, settlement, waitlist
    payment = Payment(
        id="PAY-0001",
        pledge_id=pledge.id,
        amount=pledge.amount,
        status="SUCCESS",
        attempt_number=1,
    )
    refund = Refund(
        id="REF-0001",
        pledge_id=pledge.id,
        amount=Decimal("1000.00"),
        reason="REQUESTED",
        status="PROCESSED",
    )
    chargeback = Chargeback(
        id="CHB-0001",
        pledge_id=pledge.id,
        amount=Decimal("5000.00"),
        reason="FRAUD",
        status="OPEN",
    )
    settlement = Settlement(
        id="STL-0001",
        campaign_id=campaign.id,
        collected_amount=pledge.amount,
    )
    waitlist = Waitlist(
        id="WTL-0001",
        campaign_id=campaign.id,
        tier_id=tier.id,
        backer_id=backer.backer_id,
        amount=tier.price,
    )
    db.add_all([payment, refund, chargeback, settlement, waitlist])
    db.commit()

    # Verify retrieval
    assert db.get(Creator, "CRT-01") is not None
    assert db.get(Backer, "BKR-010") is not None
    assert db.get(Campaign, "CMP-01").has_failed_delivery is False
    assert db.get(RewardTier, "TIR-03").campaign_id == "CMP-01"
    assert db.get(StretchGoal, "SG-01").campaign_id == "CMP-01"
    assert db.get(Pledge, "PLG-0001").tier_id == "TIR-03"
    assert db.get(Payment, "PAY-0001").pledge_id == "PLG-0001"
    assert db.get(Refund, "REF-0001").pledge_id == "PLG-0001"
    assert db.get(Chargeback, "CHB-0001").pledge_id == "PLG-0001"
    assert db.get(Settlement, "STL-0001").campaign_id == "CMP-01"
    assert db.get(Waitlist, "WTL-0001").campaign_id == "CMP-01"


def test_has_failed_delivery_flag(db):
    now = datetime(2026, 9, 1, 10, 0, 0)
    campaign = Campaign(
        id="CMP-04",
        title="Single-estate Coffee",
        description="Coffee subscription",
        goal_amount=Decimal("300000.00"),
        funding_model="ALL_OR_NOTHING",
        start_date=now,
        deadline=now + timedelta(days=45),
        status="FUNDED",
        creator_id="CRT-04",
        has_failed_delivery=False,
    )
    db.add(campaign)
    db.commit()

    campaign.has_failed_delivery = True
    db.commit()
    db.refresh(campaign)

    assert campaign.has_failed_delivery is True


def test_automatic_callable_defaults_on_instantiation(db):
    now = datetime(2026, 9, 1, 10, 0, 0)
    # Instantiate without explicit IDs
    c1 = Campaign(
        title="Auto Campaign 1",
        description="Desc 1",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=now,
        deadline=now + timedelta(days=30),
        status="LIVE",
        creator_id="CRT-01",
    )
    c2 = Campaign(
        title="Auto Campaign 2",
        description="Desc 2",
        goal_amount=Decimal("50000.00"),
        funding_model="FLEXIBLE",
        start_date=now,
        deadline=now + timedelta(days=30),
        status="LIVE",
        creator_id="CRT-01",
    )
    db.add_all([c1, c2])
    db.commit()

    assert c1.id is not None
    assert c2.id is not None
    assert c1.id != c2.id
    assert c1.id.startswith("CMP_")
    assert c2.id.startswith("CMP_")
