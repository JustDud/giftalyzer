from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Reply keyboard
reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Option 1")],
        [KeyboardButton(text="Option 2"), KeyboardButton(text="Option 3")]
    ],
    resize_keyboard=True
)

# Inline keyboard
inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Google", url="https://google.com")],
    [InlineKeyboardButton(text="Say Hello", callback_data="say_hello")]
])

# Remove inline keyboard
remove_inline_kb = InlineKeyboardMarkup(inline_keyboard=[])