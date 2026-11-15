
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.settlement import Settlement
from app.models.refund import Refund


REFUND_WINDOW_DAYS = 14


def money(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def process_refund(
    db: Session,
    pledge_id: int,
    amount: Decimal,
    reason: str,
    current_time,
):
    pledge = db.get(Pledge, pledge_id)

    if pledge is None:
        raise ValueError("Pledge not found.")

    if pledge.status != "COLLECTED":
        raise ValueError("Only successfully collected pledges can be refunded.")

    campaign = db.get(Campaign, pledge.campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    settlement = (
        db.query(Settlement)
        .filter(Settlement.campaign_id == campaign.id)
        .first()
    )

    if settlement is None:
        raise ValueError("Campaign settlement not found.")

    if settlement.status not in ("PENDING_PAYOUT", "PAYOUT_COMPLETED"):
        raise ValueError("Refund cannot be processed after settlement completion.")

    refund_amount = money(Decimal(str(amount)))

    if refund_amount <= Decimal("0.00"):
        raise ValueError("Refund amount must be positive.")

    if refund_amount > Decimal(str(pledge.amount)):
        raise ValueError("Refund cannot exceed the original pledge amount.")

    refund_reason = reason.strip().upper()

    if refund_reason != "FAILED_DELIVERY":
        if campaign.funding_model.upper() != "FLEXIBLE":
            raise ValueError(
                "Normal refunds are only allowed for FLEXIBLE campaigns."
            )

    refund_deadline = campaign.deadline + timedelta(
        days=REFUND_WINDOW_DAYS
    )

    if current_time < campaign.deadline or current_time > refund_deadline:
        raise ValueError("Refund request is outside the 14-day refund window.")

    existing_refunds = (
        db.query(Refund)
        .filter(
            Refund.pledge_id == pledge_id,
            Refund.status == "PROCESSED",
        )
        .all()
    )

    already_refunded = sum(
        (Decimal(str(item.amount)) for item in existing_refunds),
        Decimal("0.00"),
    )

    if already_refunded + refund_amount > Decimal(str(pledge.amount)):
        raise ValueError("Total refunds cannot exceed the pledge amount.")

    reserve_available = Decimal(
        str(settlement.reserve_remaining)
    )

    reserve_used = min(reserve_available, refund_amount)

    creator_receivable = refund_amount - reserve_used

    settlement.reserve_remaining = money(
        reserve_available - reserve_used
    )

    settlement.refund_total = money(
        Decimal(str(settlement.refund_total)) + refund_amount
    )

    refund = Refund(
        pledge_id=pledge_id,
        amount=refund_amount,
        reason=refund_reason,
        status="PROCESSED",
        reserve_amount_used=reserve_used,
        creator_receivable_used=creator_receivable,
        requested_at=current_time,
        processed_at=current_time,
        notes="Refund processed. Platform and processing fees are not refunded.",
    )

    db.add(refund)
    db.commit()
    db.refresh(refund)

    return refund
