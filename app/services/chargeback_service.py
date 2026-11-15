
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.settlement import Settlement
from app.models.chargeback import Chargeback


CHARGEBACK_WINDOW_DAYS = 90
CHARGEBACK_FEE = Decimal("500.00")
CHARGEBACK_FREEZE_THRESHOLD = 3


def money(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def process_chargeback(
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
        raise ValueError("Only collected pledges can have chargebacks.")

    campaign = db.get(Campaign, pledge.campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    chargeback_deadline = campaign.deadline + timedelta(
        days=CHARGEBACK_WINDOW_DAYS
    )

    if (
        current_time < campaign.deadline
        or current_time > chargeback_deadline
    ):
        raise ValueError("Chargeback is outside the 90-day window.")

    settlement = (
        db.query(Settlement)
        .filter(Settlement.campaign_id == campaign.id)
        .first()
    )

    if settlement is None:
        raise ValueError("Campaign settlement not found.")

    chargeback_amount = money(Decimal(str(amount)))

    if chargeback_amount <= Decimal("0.00"):
        raise ValueError("Chargeback amount must be positive.")

    if chargeback_amount > Decimal(str(pledge.amount)):
        raise ValueError("Chargeback cannot exceed the original pledge amount.")

    existing_chargebacks = (
        db.query(Chargeback)
        .filter(
            Chargeback.pledge_id == pledge_id,
            Chargeback.status == "OPEN",
        )
        .all()
    )

    already_disputed = sum(
        (Decimal(str(item.amount)) for item in existing_chargebacks),
        Decimal("0.00"),
    )

    if already_disputed + chargeback_amount > Decimal(str(pledge.amount)):
        raise ValueError(
            "Total chargebacks cannot exceed the original pledge amount."
        )

    reserve_available = Decimal(
        str(settlement.reserve_remaining)
    )

    reserve_used = min(reserve_available, chargeback_amount)

    settlement.reserve_remaining = money(
        reserve_available - reserve_used
    )

    settlement.chargeback_total = money(
        Decimal(str(settlement.chargeback_total))
        + chargeback_amount
    )

    settlement.chargeback_count += 1

    if settlement.chargeback_count >= CHARGEBACK_FREEZE_THRESHOLD:
        settlement.reserve_frozen = True

    chargeback = Chargeback(
        pledge_id=pledge_id,
        amount=chargeback_amount,
        chargeback_fee=CHARGEBACK_FEE,
        reason=reason.strip(),
        status="OPEN",
        reserve_amount_used=reserve_used,
        created_at=current_time,
        notes=(
            "₹500 chargeback fee is a separate creator liability. "
            "Any disputed amount not covered by the reserve remains "
            "a creator liability. Manual review required if reserve is frozen."
        ),
    )

    db.add(chargeback)
    db.commit()
    db.refresh(chargeback)

    return chargeback
