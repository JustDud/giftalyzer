from datetime import datetime
from typing import Optional, Dict, Any
from mongo import promo_codes_collection, promo_usage_collection
import random
import string


def validate_promo_data(discount_percent: float, owner_profit_percent: float):
    if not (0 <= discount_percent <= 100):
        raise ValueError("Discount percent must be between 0 and 100")
    if not (0 <= owner_profit_percent <= 100):
        raise ValueError("Owner profit percent must be between 0 and 100")


def generate_promo_code(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_promo(code: str, owner_id: int, discount_percent: float,
                 owner_profit_percent: float, is_single_use: bool = False) -> Dict[str, Any]:
    """Create a new promo code in MongoDB."""
    validate_promo_data(discount_percent, owner_profit_percent)
    if not code:
        code = generate_promo_code()
    promo = {
        "code": code.upper(),
        "owner_id": owner_id,
        "discount_percent": discount_percent,
        "owner_profit_percent": owner_profit_percent,
        "is_single_use": is_single_use,
        "is_active": True,
        "usage_count": 0,
        "total_profit": 0.0,
        "created_at": datetime.utcnow()
    }
    promo_codes_collection.insert_one(promo)
    return promo


def get_promo_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Retrieve promo code by its code."""
    return promo_codes_collection.find_one({"code": code.upper()})


def disable_promo(code: str) -> bool:
    """Disable a promo code."""
    result = promo_codes_collection.update_one(
        {"code": code.upper()},
        {"$set": {"is_active": False}}
    )
    return result.modified_count > 0


def apply_promo(user_id: int, code: str, price: float) -> Dict[str, Any]:
    """Check promo code and calculate discounted price without updating stats."""
    promo = get_promo_by_code(code)
    if not promo or not promo.get("is_active"):
        return {"error": "Promo code is inactive or does not exist"}

    if promo.get("is_single_use"):
        already_used = promo_usage_collection.find_one({"promo_code": promo["code"], "user_id": user_id})
        if already_used:
            return {"error": "You have already used this promo code"}

    discount = price * (promo["discount_percent"] / 100)
    final_price = price - discount

    return {
        "final_price": final_price,
        "discount": discount,
        "promo_code": promo["code"],
        "owner_profit_percent": promo["owner_profit_percent"]
    }


def finalize_promo_usage(user_id: int, promo_code: str, paid_price: float):
    """Finalize promo code usage after successful payment."""
    promo = get_promo_by_code(promo_code)
    if not promo or not promo.get("is_active"):
        print(f"[ERROR] Promo not found or inactive during finalization: {promo_code}")
        return False

    owner_profit = round(paid_price * (promo["owner_profit_percent"] / 100), 2)
    print(f"[INFO] Finalizing promo usage: code={promo_code}, paid_price={paid_price}, profit={owner_profit}")

    try:
        promo_usage_collection.insert_one({
            "promo_code": promo_code,
            "user_id": user_id,
            "profit_to_owner": owner_profit,
            "discount_applied": promo["discount_percent"],
            "created_at": datetime.utcnow()
        })
    except Exception as e:
        print(f"[ERROR] Failed to insert promo usage record: {e}")

    try:
        update_result = promo_codes_collection.update_one(
            {"code": promo_code.upper()},
            {
                "$inc": {
                    "usage_count": 1,
                    "total_profit": owner_profit
                }
            }
        )
        print(f"[INFO] Promo update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
        return update_result.modified_count > 0
    except Exception as e:
        print(f"[ERROR] Failed to update promo stats: {e}")
        return False


def get_promo_stats(code: str) -> Optional[Dict[str, Any]]:
    """Return statistics of promo code usage."""
    promo = get_promo_by_code(code)
    if not promo:
        return None
    return {
        "usage_count": promo.get("usage_count", 0),
        "total_profit": promo.get("total_profit", 0.0),
        "is_active": promo.get("is_active", False)
    }


def list_all_promos(active_only: bool = False) -> list[Dict[str, Any]]:
    """List all promo codes, optionally filtering only active ones."""
    query = {"is_active": True} if active_only else {}
    return list(promo_codes_collection.find(query, {"_id": 0}))


def get_top_promos(limit: int = 10) -> list[Dict[str, Any]]:
    """Get top promo codes by total profit."""
    return list(
        promo_codes_collection.find({"usage_count": {"$gt": 0}})
        .sort("total_profit", -1)
        .limit(limit)
    )