from datetime import datetime, timedelta, UTC
from mongo import subscriptions_collection as subscriptions

# ---- DateTime helpers (single place to handle aware/naive & comparisons) ----

def ensure_aware_utc(dt: datetime | None) -> datetime | None:
    """Return the same moment as a timezone-aware UTC datetime.
    If dt is naive, assume it is UTC and attach tzinfo=UTC.
    If dt is aware but not UTC, convert to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def utc_now() -> datetime:
    """Single source of truth for 'now' in UTC (aware)."""
    return datetime.now(UTC)


def not_expired(end_dt: datetime | None) -> bool:
    """Generic check used across the codebase to compare end dates with now."""
    end_dt = ensure_aware_utc(end_dt)
    return end_dt is not None and utc_now() <= end_dt


async def add_subscription(user_id: int, days: int = 30):
    """Extend subscription if already active, otherwise start new."""
    now = utc_now()
    record = await subscriptions.find_one({"user_id": user_id})

    current_end = ensure_aware_utc(record.get("end_date")) if record else None
    if record and record.get("subscribed") and current_end and current_end > now:
        # Extend from the current end_date if active
        end_date = current_end + timedelta(days=days)
        start_date = ensure_aware_utc(record.get("start_date")) or now
    else:
        # Start new subscription
        start_date = now
        end_date = now + timedelta(days=days)

    await subscriptions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "subscribed": True,
                "start_date": ensure_aware_utc(start_date) or now,
                "end_date": ensure_aware_utc(end_date) or now
            }
        },
        upsert=True
    )

    existing = await subscriptions.find_one({"user_id": user_id})
    if not existing:
        await subscriptions.insert_one({
            "user_id": user_id,
            "free_ai_requests": 3  # or adjust to your default
        })


async def is_subscription_valid(user_id: int) -> bool:
    """Check if the user's subscription is still valid based on end date."""
    record = await subscriptions.find_one({"user_id": user_id, "subscribed": True})
    if not record:
        return False
    end_date = ensure_aware_utc(record.get("end_date"))
    return not_expired(end_date)


async def remove_expired_subscriptions():
    """Mark expired subscriptions as inactive based on end date."""
    result = await subscriptions.update_many(
        {"end_date": {"$lt": utc_now()}, "subscribed": True},
        {"$set": {"subscribed": False}}
    )
    print(f"Marked {result.modified_count} subscriptions as inactive.")


async def get_subscription_stats():
    """Return statistics about total and active subscriptions."""
    total = await subscriptions.count_documents({})
    active = await subscriptions.count_documents({"subscribed": True})
    return total, active
