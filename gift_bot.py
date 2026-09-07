"""
Отдельный минимальный бот: ТОЛЬКО джекпот (777 на слот-машине 🎰) и игра
с 30 ячейками-призами. Больше ничего — ни Ludo, ни Перебива, ни модерации.

Установка:
    pip install aiogram

Запуск:
    python gift_bot.py

Токен бота — переменная окружения BOT_TOKEN.
Никогда не вписывай токен прямо в этот файл.

Картинка jackpot.jpg должна лежать РЯДОМ с этим файлом — бот отправляет
её вместе с текстом джекпота (как в примере со скриншота).
"""

import asyncio
import logging
import os
import random
import uuid

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ==== НАСТРОЙКИ ====
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ОТ_BOTFATHER")

# Юзернейм, который тегаем в сообщениях (без @, сама @ добавляется в тексте)
TAG_USERNAME = "PenguinLudka"

# Путь к картинке, которую бот шлёт вместе с джекпотом (должна лежать рядом с файлом)
JACKPOT_PHOTO_PATH = os.path.join(os.path.dirname(__file__), "jackpot.jpg")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Значение dice.value == 64 соответствует комбинации 777 на слот-машине.
JACKPOT_VALUE = 64

# ---------------------------------------------------------------------------
# ПРИЗЫ: ровно 30 штук на 30 ячеек (перемешиваются случайно при каждом джекпоте)
#   NFT — 1
#   100 — 1
#   50  — 3
#   25  — 7
#   15  — 18
# ---------------------------------------------------------------------------
PRIZE_POOL = (
    ["NFT"] * 1
    + ["100⭐️"] * 1
    + ["50⭐️"] * 3
    + ["25⭐️"] * 7
    + ["15⭐️"] * 18
)
TOTAL_GIFTS = len(PRIZE_POOL)  # 30
GIFTS_PER_ROW = 5

# ID премиум-эмодзи (используются через тег <tg-emoji>).
# Напоминание: реально отображаются с анимацией только если у ВЛАДЕЛЬЦА
# этого бота есть активная подписка Telegram Premium (или куплен
# дополнительный username через Fragment) — так требует сам Telegram.
# Без этого условия у всех, включая тебя, будет виден обычный fallback-смайлик.
EMOJI_CELL_CHOSEN = '<tg-emoji emoji-id="5247230282179847168">😀</tg-emoji>'
EMOJI_BLUE_DOT = '<tg-emoji emoji-id="5235484233820050502">🔵</tg-emoji>'
EMOJI_SMILE_TAG = '<tg-emoji emoji-id="5249091686646195297">😀</tg-emoji>'
EMOJI_RABBIT = '<tg-emoji emoji-id="5235576098875549171">🐰</tg-emoji>'
EMOJI_SHY = '<tg-emoji emoji-id="5247112342377898639">😅</tg-emoji>'

# Активные игры: game_id -> {"values": [...], "winner_id": int, "finished": bool, "chosen_index": int|None}
active_games: dict[str, dict] = {}


def build_gift_keyboard(game_id: str, game: dict) -> InlineKeyboardMarkup:
    """Закрытая ячейка — 🎁. После выбора — показывает приз под каждой ячейкой."""
    buttons = []
    row = []
    for i in range(TOTAL_GIFTS):
        if game["finished"]:
            prefix = "✅" if i == game["chosen_index"] else ""
            text = f"{prefix}{game['values'][i]}"
            callback_data = "gift:closed"
        else:
            text = "🎁"
            callback_data = f"gift:{game_id}:{i}"
        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        if len(row) == GIFTS_PER_ROW:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(F.dice)
async def handle_dice(message: Message):
    dice = message.dice
    if dice.emoji != "🎰" or dice.value != JACKPOT_VALUE:
        return  # реагируем ТОЛЬКО на джекпот 777, больше ни на что

    game_id = uuid.uuid4().hex[:12]
    values = list(PRIZE_POOL)
    random.shuffle(values)

    active_games[game_id] = {
        "values": values,
        "winner_id": message.from_user.id,
        "finished": False,
        "chosen_index": None,
        "chat_id": message.chat.id,
        "original_message_id": message.message_id,
        "has_photo": False,  # обновится ниже, если фото отправится успешно
    }

    caption = (
        f"{EMOJI_RABBIT}<b>ДЖЕКПОТ! ПОБЕДА!</b>\n\n"
        f"{EMOJI_SHY}Пингвин поздравляет тебя, а теперь выбери одну из 30 "
        f"доступных ячеек ниже, чтобы получить свой приз\n\n"
        f"{EMOJI_SMILE_TAG}<b>@{TAG_USERNAME}</b>"
    )
    keyboard = build_gift_keyboard(game_id, active_games[game_id])

    # Явно проверяем, что картинка вообще есть и не пустая — это самая
    # частая причина TelegramBadRequest: DOCUMENT_INVALID на проде
    # (файл не попал в деплой / регистр имени отличается / 0 байт).
    photo_ok = os.path.isfile(JACKPOT_PHOTO_PATH) and os.path.getsize(JACKPOT_PHOTO_PATH) > 0
    if not photo_ok:
        logging.error(
            "jackpot.jpg не найден или пустой по пути %s — отправляю без фото",
            JACKPOT_PHOTO_PATH,
        )

    try:
        if not photo_ok:
            raise FileNotFoundError(JACKPOT_PHOTO_PATH)
        photo = FSInputFile(JACKPOT_PHOTO_PATH)
        await message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=keyboard,
        )
        active_games[game_id]["has_photo"] = True
    except Exception:
        # Никогда не даём этой ошибке "съесть" весь хендлер — пользователь
        # должен получить сообщение с призами в любом случае, даже без фото.
        logging.exception("Не удалось отправить jackpot.jpg, отправляю текстом")
        await message.reply(
            caption,
            reply_markup=keyboard,
        )


@dp.callback_query(F.data.startswith("gift:"))
async def handle_gift_click(callback: CallbackQuery):
    if callback.data == "gift:closed":
        await callback.answer("Эта игра уже завершена.", show_alert=True)
        return

    _, game_id, idx_str = callback.data.split(":")
    idx = int(idx_str)

    game = active_games.get(game_id)
    if game is None or game["finished"]:
        await callback.answer("Эта игра уже завершена.", show_alert=True)
        return

    if callback.from_user.id != game["winner_id"]:
        await callback.answer("Это приз не для тебя 🙂", show_alert=True)
        return

    prize = game["values"][idx]
    game["finished"] = True
    game["chosen_index"] = idx

    result_text = (
        f"{EMOJI_CELL_CHOSEN}<b>Ячейка выбрана! Ты получаешь — {prize}</b>\n\n"
        f"{EMOJI_BLUE_DOT}В течение пары минут мы отправим тебе его на аккаунт\n\n"
        f"{EMOJI_SMILE_TAG}<b>@{TAG_USERNAME}</b>"
    )

    updated_keyboard = build_gift_keyboard(game_id, game)
    if game.get("has_photo"):
        await callback.message.edit_caption(
            caption=result_text,
            reply_markup=updated_keyboard,
        )
    else:
        await callback.message.edit_text(
            text=result_text,
            reply_markup=updated_keyboard,
        )

    # Дополнительно шлём то же самое отдельным сообщением-реплаем
    # на исходный бросок 🎰, где выпало 777.
    await bot.send_message(
        chat_id=game["chat_id"],
        text=result_text,
        reply_to_message_id=game["original_message_id"],
    )

    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
