
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.payment import Payment
from app.models.settlement import Settlement


PLATFORM_FEES = {
    "ALL_OR_NOTHING": Decimal("0.05"),
    "FLEXIBLE": Decimal("0.08"),
}

PROCESSING_RATE = Decimal("0.025")
PROCESSING_FIXED_FEE = Decimal("3.00")
GST_RATE = Decimal("0.18")
RESERVE_RATE = Decimal("0.10")

PAYOUT_DELAY_DAYS = 14
RESERVE_PERIOD_DAYS = 90


def money(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def calculate_settlement(
    db: Session,
    campaign_id: int,
    current_time,
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "FUNDED":
        raise ValueError("Only funded campaigns can be settled.")

    existing = (
        db.query(Settlement)
        .filter(Settlement.campaign_id == campaign_id)
        .first()
    )

    if existing is not None:
        raise ValueError("Settlement already exists for this campaign.")

    funding_model = campaign.funding_model.upper()

    if funding_model not in PLATFORM_FEES:
        raise ValueError("Invalid funding model.")

    pledges = (
        db.query(Pledge)
        .filter(Pledge.campaign_id == campaign_id)
        .all()
    )

    pledged_amount = sum(
        (
            Decimal(str(pledge.amount))
            for pledge in pledges
            if pledge.status in ("PLEDGED", "COLLECTED")
        ),
        Decimal("0.00"),
    )

    successful_payments = (
        db.query(Payment)
        .join(Pledge, Payment.pledge_id == Pledge.id)
        .filter(
            Pledge.campaign_id == campaign_id,
            Payment.status == "SUCCESS",
        )
        .all()
    )

    collected_amount = sum(
        (
            Decimal(str(payment.amount))
            for payment in successful_payments
        ),
        Decimal("0.00"),
    )

    successful_charge_count = len(successful_payments)

    platform_fee = money(
        collected_amount * PLATFORM_FEES[funding_model]
    )

    processing_fee = money(
        collected_amount * PROCESSING_RATE
        + PROCESSING_FIXED_FEE * successful_charge_count
    )

    gst_amount = money(
        (platform_fee + processing_fee) * GST_RATE
    )

    total_fees = money(
        platform_fee + processing_fee + gst_amount
    )

    net_amount = money(
        collected_amount - total_fees
    )

    reserve_amount = money(
        net_amount * RESERVE_RATE
    )

    payout_amount = money(
        net_amount - reserve_amount
    )

    settlement = Settlement(
        campaign_id=campaign_id,
        pledged_amount=pledged_amount,
        collected_amount=collected_amount,
        successful_charge_count=successful_charge_count,
        platform_fee=platform_fee,
        processing_fee=processing_fee,
        gst_amount=gst_amount,
        total_fees=total_fees,
        net_amount=net_amount,
        reserve_amount=reserve_amount,
        reserve_remaining=reserve_amount,
        payout_amount=payout_amount,
        refund_total=Decimal("0.00"),
        chargeback_total=Decimal("0.00"),
        chargeback_count=0,
        reserve_frozen=False,
        status="PENDING_PAYOUT",
        payout_due_at=campaign.deadline + timedelta(
            days=PAYOUT_DELAY_DAYS
        ),
        reserve_release_at=campaign.deadline + timedelta(
            days=RESERVE_PERIOD_DAYS
        ),
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    return settlement


def execute_creator_payout(
    db: Session,
    campaign_id: int,
    current_time,
):
    settlement = (
        db.query(Settlement)
        .filter(Settlement.campaign_id == campaign_id)
        .first()
    )

    if settlement is None:
        raise ValueError("Settlement not found.")

    if settlement.status != "PENDING_PAYOUT":
        raise ValueError("Payout has already been processed or is not pending.")

    if current_time < settlement.payout_due_at:
        raise ValueError("Creator payout is not due yet.")

    # Record that the initial creator payout has been processed.
    settlement.status = "PAYOUT_COMPLETED"
    settlement.settled_at = current_time

    db.commit()
    db.refresh(settlement)

    return settlement


def release_creator_reserve(
    db: Session,
    campaign_id: int,
    current_time,
):
    settlement = (
        db.query(Settlement)
        .filter(Settlement.campaign_id == campaign_id)
        .first()
    )

    if settlement is None:
        raise ValueError("Settlement not found.")

    if settlement.status != "PAYOUT_COMPLETED":
        raise ValueError("Initial creator payout must be completed first.")

    if settlement.reserve_frozen:
        raise ValueError("Reserve is frozen due to chargebacks.")

    if current_time < settlement.reserve_release_at:
        raise ValueError("Reserve release is not due yet.")

    released_amount = settlement.reserve_remaining

    settlement.reserve_remaining = Decimal("0.00")
    settlement.status = "COMPLETED"

    db.commit()
    db.refresh(settlement)

    return released_amount
