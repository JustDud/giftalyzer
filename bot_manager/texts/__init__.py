from . import ru, en
from mongo import db


def set_language(user_id: int, lang: str) -> bool:
    if lang not in ["ru", "en"]:
        return False
    db.users.update_one({"user_id": user_id}, {"$set": {"language": lang}}, upsert=True)
    return True


def get_texts(user_id: int):
    user = db.users.find_one({"user_id": user_id})
    lang = user.get("language", "ru") if user else "ru"
    from . import ru, en
    return en.texts if lang == "en" else ru.texts