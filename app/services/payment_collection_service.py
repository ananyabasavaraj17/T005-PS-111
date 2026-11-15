
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.pledge import Pledge
from app.models.payment import Payment


RETRY_WINDOW_DAYS = 7
RETRY_INTERVAL_HOURS = 24


def record_payment_attempt(
    db: Session,
    pledge_id: int,
    succeeded: bool,
    attempted_at: datetime,
    failure_reason: str | None = None,
    transaction_reference: str | None = None,
):
    pledge = db.get(Pledge, pledge_id)

    if pledge is None:
        raise ValueError("Pledge not found.")

    campaign = db.get(Campaign, pledge.campaign_id)

    if campaign is None or campaign.status != "FUNDED":
        raise ValueError("Only funded campaigns can collect payments.")

    if pledge.status != "PLEDGED":
        raise ValueError("Only active pledges can be collected.")

    retry_deadline = campaign.deadline + timedelta(
        days=RETRY_WINDOW_DAYS
    )

    if attempted_at < campaign.deadline:
        raise ValueError("Payment collection cannot start before campaign close.")

    if attempted_at > retry_deadline:
        pledge.status = "PAYMENT_FAILED"
        db.commit()
        return {
            "status": "DROPPED",
            "pledge_id": pledge.id,
        }

    previous_attempt = (
        db.query(Payment)
        .filter(Payment.pledge_id == pledge_id)
        .order_by(
            Payment.attempted_at.desc(),
            Payment.id.desc(),
        )
        .first()
    )

    if previous_attempt is not None:
        if previous_attempt.status == "SUCCESS":
            raise ValueError("This pledge has already been collected.")

        next_attempt_time = previous_attempt.attempted_at + timedelta(
            hours=RETRY_INTERVAL_HOURS
        )

        if attempted_at < next_attempt_time:
            raise ValueError("A payment retry is not due yet.")

    attempt_number = (
        db.query(Payment)
        .filter(Payment.pledge_id == pledge_id)
        .count()
        + 1
    )

    payment = Payment(
        pledge_id=pledge.id,
        amount=pledge.amount,
        status="SUCCESS" if succeeded else "FAILED",
        attempt_number=attempt_number,
        attempted_at=attempted_at,
        failure_reason=None if succeeded else failure_reason,
        transaction_reference=transaction_reference,
    )

    db.add(payment)

    if succeeded:
        pledge.status = "COLLECTED"
    elif attempted_at >= retry_deadline:
        pledge.status = "PAYMENT_FAILED"

    db.commit()
    db.refresh(payment)

    return {
        "payment_id": payment.id,
        "pledge_id": pledge.id,
        "attempt_number": payment.attempt_number,
        "payment_status": payment.status,
        "pledge_status": pledge.status,
    }


def collect_campaign_pledges(
    db: Session,
    campaign_id: int,
    current_time: datetime,
    payment_outcomes: dict[int, bool],
):
    campaign = db.get(Campaign, campaign_id)

    if campaign is None:
        raise ValueError("Campaign not found.")

    if campaign.status != "FUNDED":
        raise ValueError("Only funded campaigns can collect payments.")

    if current_time < campaign.deadline:
        raise ValueError("Campaign deadline has not been reached.")

    pledges = (
        db.query(Pledge)
        .filter(
            Pledge.campaign_id == campaign_id,
            Pledge.status == "PLEDGED",
        )
        .order_by(Pledge.id.asc())
        .all()
    )

    results = []

    for pledge in pledges:
        succeeded = payment_outcomes.get(pledge.id, False)

        result = record_payment_attempt(
            db=db,
            pledge_id=pledge.id,
            succeeded=succeeded,
            attempted_at=current_time,
            failure_reason=(
                None if succeeded else "Initial payment failed"
            ),
        )

        results.append(result)

    return results


def retry_failed_payments(
    db: Session,
    current_time: datetime,
):
    failed_payments = (
        db.query(Payment)
        .join(Pledge, Payment.pledge_id == Pledge.id)
        .filter(
            Payment.status == "FAILED",
            Pledge.status == "PLEDGED",
        )
        .order_by(
            Payment.pledge_id.asc(),
            Payment.attempted_at.desc(),
            Payment.id.desc(),
        )
        .all()
    )

    latest_failed = {}

    for payment in failed_payments:
        if payment.pledge_id not in latest_failed:
            latest_failed[payment.pledge_id] = payment

    failed_payments = list(latest_failed.values())

    results = []

    for payment in failed_payments:
        pledge = db.get(Pledge, payment.pledge_id)
        campaign = db.get(Campaign, pledge.campaign_id)

        if campaign is None or campaign.status != "FUNDED":
            continue

        retry_deadline = campaign.deadline + timedelta(
            days=RETRY_WINDOW_DAYS
        )

        if current_time > retry_deadline:
            pledge.status = "PAYMENT_FAILED"
            db.commit()

            results.append({
                "pledge_id": pledge.id,
                "status": "DROPPED",
            })
            continue

        next_retry = payment.attempted_at + timedelta(
            hours=RETRY_INTERVAL_HOURS
        )

        if current_time < next_retry:
            continue

        results.append({
            "pledge_id": pledge.id,
            "status": "RETRY_DUE",
        })

    return results


def process_due_retries(
    db: Session,
    current_time: datetime,
    payment_outcomes: dict[int, bool],
):
    due_items = retry_failed_payments(db, current_time)

    results = []

    for item in due_items:
        if item["status"] != "RETRY_DUE":
            results.append(item)
            continue

        pledge_id = item["pledge_id"]
        succeeded = payment_outcomes.get(pledge_id, False)

        result = record_payment_attempt(
            db=db,
            pledge_id=pledge_id,
            succeeded=succeeded,
            attempted_at=current_time,
            failure_reason=(
                None if succeeded else "Retry payment failed"
            ),
        )

        results.append(result)

    return results
