from datetime import datetime, timedelta, UTC
from mongo import subscriptions_collection as subscriptions


async def add_subscription(user_id: int, days: int = 30):
    """Extend subscription if already active, otherwise start new."""
    now = datetime.now(UTC)
    record = await subscriptions.find_one({"user_id": user_id})

    if record and record.get("subscribed") and record.get("end_date") and record["end_date"] > now:
        # Extend from the current end_date if active
        end_date = record["end_date"] + timedelta(days=days)
        start_date = record.get("start_date", now)
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
                "start_date": start_date,
                "end_date": end_date
            }
        },
        upsert=True
    )

    existing = await subscriptions.find_one({"user_id": user_id})
    if not existing:
        await subscriptions.insert_one({
            "user_id": user_id,
            "free_ai_requests": 10  # or adjust to your default
        })


async def is_subscription_valid(user_id: int) -> bool:
    """Check if the user's subscription is still valid based on end date."""
    record = await subscriptions.find_one({"user_id": user_id, "subscribed": True})
    if not record:
        return False
    end_date = record.get("end_date")
    if not end_date:
        return False
    return datetime.now(UTC) <= end_date


async def remove_expired_subscriptions():
    """Mark expired subscriptions as inactive based on end date."""
    result = await subscriptions.update_many(
        {"end_date": {"$lt": datetime.now(UTC)}, "subscribed": True},
        {"$set": {"subscribed": False}}
    )
    print(f"Marked {result.modified_count} subscriptions as inactive.")


async def run_daily_check():
    print(f"[{datetime.now(UTC)}] Running daily subscription check...")
    await remove_expired_subscriptions()
    print(f"[{datetime.now(UTC)}] Check complete.")


async def get_subscription_stats():
    """Return statistics about total and active subscriptions."""
    total = await subscriptions.count_documents({})
    active = await subscriptions.count_documents({"subscribed": True})
    return total, active
