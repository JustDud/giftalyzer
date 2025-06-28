from datetime import datetime, timedelta
from mongo import subscriptions_collection as subscriptions


def add_subscription(user_id: int):
    """Add or update a subscription with current timestamp."""
    now = datetime.utcnow()
    subscriptions.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "subscribed": True, "start_date": now}},
        upsert=True
    )


def is_subscription_valid(user_id: int) -> bool:
    """Check if the user's subscription is still valid."""
    record = subscriptions.find_one({"user_id": user_id, "subscribed": True})
    if not record:
        return False
    start_date = record.get("start_date")
    if not start_date:
        return False
    return (datetime.utcnow() - start_date) <= timedelta(days=30)


def remove_expired_subscriptions():
    """Mark expired subscriptions as inactive."""
    threshold = datetime.utcnow() - timedelta(days=30)
    subscriptions.update_many(
        {"start_date": {"$lt": threshold}, "subscribed": True},
        {"$set": {"subscribed": False}}
    )


def run_daily_check():
    print(f"[{datetime.utcnow()}] Running daily subscription check...")
    remove_expired_subscriptions()
    print(f"[{datetime.utcnow()}] Check complete.")
