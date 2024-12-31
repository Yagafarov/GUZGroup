import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import random
import re

# .env faylini yuklash
load_dotenv()

# Bot tokenini olish
TOKEN = os.getenv("BOT_TOKEN")

# So‘zlar ro‘yxati
WORD_LIST = ["olma", "nok", "uzum","gilos"]

# Xonalar ro‘yxati
room_sessions = {}

# So‘zni yashirish funksiyasi
def hide_word(word, guessed_letters):
    return " ".join([char if char in guessed_letters else "_" for char in word])

# Tasdiqlash tugmasi
def generate_confirmation_keyboard(room_id: str, user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Qo‘shish", callback_data=f"accept_{room_id}_{user_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{room_id}_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start: Yangi o'yin yoki mavjud o'yinga ulanish
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or f"Foydalanuvchi-{user_id}"

    # Agar foydalanuvchi xona ID ni kiritgan bo'lsa
    if context.args:
        room_id = context.args[0]
        if room_id in room_sessions:
            session = room_sessions[room_id]
            # Xona yaratuvchisi uchun tasdiqlash yuborish
            creator_id = session["players"][0]["id"]  # Xona yaratuvchisi
            if user_id != creator_id:
                # Foydalanuvchi xonaga qo‘shilmoqchi
                await context.bot.send_message(
                    creator_id,
                    f"Do‘stingiz {username} xonaga qo‘shilmoqchi. Qo‘shishni xohlaysizmi?",
                    reply_markup=generate_confirmation_keyboard(room_id, user_id)
                )
                await update.message.reply_text(f"Sizning taklifingiz yuborildi. Kutilmoqda...")
            else:
                await update.message.reply_text("Siz allaqachon xonani yaratdingiz.")
            return
        else:
            await update.message.reply_text("Bunday xona topilmadi. Yangi o‘yin yaratish uchun: /start buyrug‘ini yuboring.")
            return

    # Yangi xona yaratish
    room_id = str(random.randint(1000, 9999))  # Tasodifiy xona ID
    word = random.choice(WORD_LIST)
    room_sessions[room_id] = {
        "word": word,
        "guessed_letters": [],
        "remaining_attempts": 5,
        "players": [{"id": user_id, "username": f"{username}", "correct_guesses": 0}],  # Player 1 sifatida saqlash
        "current_turn": 0,
    }
    hidden_word = hide_word(word, [])
    await update.message.reply_text(
        f"🎮 <b>Yangi o‘yin yaratildi!</b>\n\n"
        f"<b>🔑 Xona ID:</b> <code>{room_id}</code>\n"
        f"<b>📨 Qo'shilish uchun:</b> <code>/start {room_id}</code>\n"
        f"Qo‘shilish uchun do‘stingizni taklif qiling yoki boshqa xonaga qo‘shiling! 😉",
        parse_mode="HTML"
    )

# Harfni tanlash
async def guess_letter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # O'yinchining xonasini topish
    room_id = None
    for rid, session in room_sessions.items():
        for player in session["players"]:
            if player["id"] == user_id:
                room_id = rid
                break
        if room_id:
            break

    if not room_id:
        await update.message.reply_text("Siz hech qanday o‘yin o‘ynamayapsiz. Yangi o‘yin boshlash uchun /start.")
        return

    session = room_sessions[room_id]

    # Faqat navbatdagi o‘yinchi harf tanlay oladi
    current_player = session["players"][session["current_turn"]]
    if user_id != current_player["id"]:
        await update.message.reply_text("Hozir navbat sizda emas. Kuting!")
        return

    letter = update.message.text.lower()
    if len(letter) != 1 or not letter.isalpha():
        await update.message.reply_text("Faqat bitta harf yuboring!")
        return

    if letter in session["guessed_letters"]:
        await update.message.reply_text(f"'{letter}' harfini oldin tanlagansiz. Boshqa harf tanlang.")
        return

    session["guessed_letters"].append(letter)
    if letter in session["word"]:
        current_player["correct_guesses"] += 1
        hidden_word = hide_word(session["word"], session["guessed_letters"])
        if "_" not in hidden_word:
            # To'plangan to'g'ri javoblar sonini tekshirish
            player_scores = [player["correct_guesses"] for player in session["players"]]
            max_score = max(player_scores)
            if player_scores.count(max_score) > 1:
                message = f"Durrang! Har ikkala o'yinchi teng to'plagan. So'z: {session['word']}"
            else:
                # G'olibni topish
                winner = max(session["players"], key=lambda p: p["correct_guesses"])
                message = f"Tabriklaymiz! {winner['username']} g‘olib bo‘ldi! So‘z: {session['word']}"

            for player in session["players"]:
                await context.bot.send_message(player["id"], message)
            del room_sessions[room_id]
            return
        else:
            message = f"To‘g‘ri! So‘z: {hidden_word}"
            # Navbatni boshqa o'yinchiga o'tkazish
            # session["current_turn"] = (session["current_turn"] + 1) % len(session["players"])
    else:
        session["remaining_attempts"] -= 1
        if session["remaining_attempts"] <= 0:
            for player in session["players"]:
                await context.bot.send_message(player["id"], f"Afsus! Urinishlar tugadi. So‘z: {session['word']}")
            del room_sessions[room_id]
            return
        else:
            message = f"Noto‘g‘ri! Urinishlar qoldi: {session['remaining_attempts']}"

            session["current_turn"] = (session["current_turn"] + 1) % len(session["players"])

    # Xabarnoma barcha o'yinchilarga yuboriladi
    for player in session["players"]:
        await context.bot.send_message(player["id"], message)

    # Navbatdagi o'yinchi haqida xabar yuborish
    next_player = session["players"][session["current_turn"]]["username"]
    for player in session["players"]:
        await context.bot.send_message(player["id"], f"Navbatdagi o‘yinchi: <b>{next_player}</b>", parse_mode="HTML")

# /status: Hozirgi holatni ko‘rsatish
async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # O'yinchining xonasini topish
    room_id = None
    for rid, session in room_sessions.items():
        for player in session["players"]:
            if player["id"] == user_id:
                room_id = rid
                break
        if room_id:
            break

    if not room_id:
        await update.message.reply_text("Siz hech qanday o‘yin o‘ynamayapsiz. Yangi o‘yin boshlash uchun /start.")
        return

    session = room_sessions[room_id]
    hidden_word = hide_word(session["word"], session["guessed_letters"])
    remaining_attempts = session["remaining_attempts"]
    players = " 🧑‍🤝‍🧑 ".join(player["username"] for player in session["players"])
    await update.message.reply_text(
        f"<b>So‘z:</b> {hidden_word}\n"
        f"<b>Qoldiq urinishlar:</b> {remaining_attempts} 🔄\n"
        f"<b>O‘yinchilar:</b> {players} 👥\n"
        f"<b>Hozirgi navbatdagi o‘yinchi:</b> {session['players'][session['current_turn']]['username']} 🕹️",
        parse_mode="HTML"
    )

# Inline tugmalar orqali tasdiqlashni qabul qilish
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action, room_id, user_id = query.data.split("_")

    session = room_sessions.get(room_id)
    if not session:
        await query.edit_message_text("Xona topilmadi.")
        return

    if action == "accept":
        # Do'stingizni xonaga qo'shish
        user_name = update.effective_user.first_name  # To'liq ismi
        player_number = len(session["players"]) + 1  # Yangi o'yinchiga Player raqamini olish
        msg_text = update.callback_query.message.text
        match = re.search(r"Do‘stingiz (\w+) xonaga qo‘shilmoqchi", msg_text)
        if match:
            player_name = match.group(1)  # Do'stingiz ismini olish
        else:
            player_name = f"Player {player_number}"  # Agar topilmasa, default nom berish

        session["players"].append({"id": int(user_id), "username": player_name, "correct_guesses": 0})  # user_id ni integerga o'zgartirish

        # Do'stingizga xabar yuborish
        await context.bot.send_message(user_id, f"🎉 Siz {room_id}-xonaga qo‘shildingiz! 🎉")

        # Xona yaratuvchisiga xabar yuborish
        creator_id = session["players"][0]["id"]  # Xona yaratuvchisi
        await context.bot.send_message(
            creator_id,
            f"🎉 {player_name} do'stingiz {room_id}-xonaga qo‘shildi! Endi siz so'zni topishni boshlashingiz mumkin. 🕵️‍♂️"
        )

        # Xonadagi holatni yangilash
        hidden_word = hide_word(session["word"], session["guessed_letters"])
        await context.bot.send_message(creator_id, f"Endi so'zni topish vaqti keldi: {hidden_word}")

    elif action == "reject":
        await query.edit_message_text(f"❌ Do‘stingiz xonaga qo‘shilishdan rad etildi.")

# Asosiy funksiyani ishga tushirish
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Buyruqlarni sozlash
    application.add_handler(CommandHandler("start", start_game))
    application.add_handler(CommandHandler("status", game_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess_letter))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Botni ishga tushirish
    application.run_polling()


if __name__ == "__main__":
    main()
