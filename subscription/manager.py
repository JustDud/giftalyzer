from datetime import datetime, timedelta
from mongo import subscriptions_collection as subscriptions


def add_subscription(user_id: int, days: int = 30):
    """Extend subscription if already active, otherwise start new."""
    now = datetime.utcnow()
    record = subscriptions.find_one({"user_id": user_id})

    if record and record.get("subscribed") and record.get("end_date") and record["end_date"] > now:
        # Extend from the current end_date if active
        end_date = record["end_date"] + timedelta(days=days)
        start_date = record.get("start_date", now)
    else:
        # Start new subscription
        start_date = now
        end_date = now + timedelta(days=days)

    subscriptions.update_one(
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


def is_subscription_valid(user_id: int) -> bool:
    """Check if the user's subscription is still valid based on end date."""
    record = subscriptions.find_one({"user_id": user_id, "subscribed": True})
    if not record:
        return False
    end_date = record.get("end_date")
    if not end_date:
        return False
    return datetime.utcnow() <= end_date


def remove_expired_subscriptions():
    """Mark expired subscriptions as inactive based on end date."""
    result = subscriptions.update_many(
        {"end_date": {"$lt": datetime.utcnow()}, "subscribed": True},
        {"$set": {"subscribed": False}}
    )
    print(f"Marked {result.modified_count} subscriptions as inactive.")


def run_daily_check():
    print(f"[{datetime.utcnow()}] Running daily subscription check...")
    remove_expired_subscriptions()
    print(f"[{datetime.utcnow()}] Check complete.")


def get_subscription_stats():
    """Return statistics about total and active subscriptions."""
    total = subscriptions.count_documents({})
    active = subscriptions.count_documents({"subscribed": True})
    return total, active
