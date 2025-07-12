from aiogram.types import Message


async def is_admin(message: Message) -> bool:
    if message.chat.type not in ["group", "supergroup"]:
        return False
    admins = await message.bot.get_chat_administrators(message.chat.id)
    return message.from_user.id in [admin.user.id for admin in admins]