import os
import logging
import requests
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "mistralai/devstarl-small:free"
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

USER_STATE = {}
QUESTIONS = [
    "Представь, что ты проснулся миллионером. Чем займёшься первым делом?",
    "Что бы ты сделал, если бы тебе не нужно было работать ради денег?",
    "Какие страхи тебе мешают действовать?"
]

def generate_prediction(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Ошибка генерации: {e}")
        return "Произошла ошибка при генерации предсказания. Попробуй позже."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE[update.effective_user.id] = {"step": 0, "answers": []}
    keyboard = [[InlineKeyboardButton("Начать заново", callback_data="restart")]]
    await update.message.reply_text(QUESTIONS[0], reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "restart":
        USER_STATE[query.from_user.id] = {"step": 0, "answers": []}
        keyboard = [[InlineKeyboardButton("Начать заново", callback_data="restart")]]
        await query.message.reply_text(QUESTIONS[0], reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in USER_STATE:
        await update.message.reply_text("Нажми /start, чтобы начать тест.")
        return

    state = USER_STATE[user_id]
    state["answers"].append(update.message.text)
    state["step"] += 1

    if state["step"] < len(QUESTIONS):
        keyboard = [[InlineKeyboardButton("Начать заново", callback_data="restart")]]
        await update.message.reply_text(QUESTIONS[state["step"]], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        prompt = "\n".join([f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(zip(QUESTIONS, state['answers']))])
        await update.message.reply_text("Секунду... Я думаю...")
        response = generate_prediction(prompt)
        await update.message.reply_text(f"🧠 Предсказание:\n{response}")
        keyboard = [[InlineKeyboardButton("Начать заново", callback_data="restart")]]
        await update.message.reply_text("Хочешь попробовать ещё раз?", reply_markup=InlineKeyboardMarkup(keyboard))

app = Flask(__name__)
@app.route("/")
def home():
    return "Бот работает!"

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    application.run_polling()
